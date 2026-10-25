"""Job engine.

Every job runs in its own spawned process, so:

* the asyncio event loop never executes PDF work;
* a timeout or a cancel really stops the work (``terminate``), which a thread
  or a ``ProcessPoolExecutor`` future cannot do;
* a crash or OOM in a hostile file takes down one worker, not the server.

Concurrency is bounded by a semaphore. Results are adopted into the
``FileStore`` so they can be downloaded or fed into the next tool, and they
expire with the same TTL as uploads.
"""

from __future__ import annotations

import asyncio
import contextlib
import multiprocessing as mp
import secrets
import shutil
import threading
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.files import FileStore, StoredFile
from . import worker

TERMINAL = frozenset({"done", "failed", "cancelled"})


@dataclass
class Job:
    id: str
    op: str
    status: str = "queued"  # queued | running | done | failed | cancelled
    progress: float = 0.0
    message: str = ""
    error: dict[str, str] | None = None
    outputs: list[StoredFile] = field(default_factory=list)
    result: StoredFile | None = None
    created: float = field(default_factory=time.time)
    finished: float | None = None
    version: int = 0

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "op": self.op,
            "status": self.status,
            "progress": round(self.progress, 4),
            "message": self.message,
            "error": self.error,
            "outputs": [o.public() for o in self.outputs],
            "result": self.result.public() if self.result else None,
        }


class JobEngine:
    def __init__(
        self,
        store: FileStore,
        work_dir: Path,
        *,
        max_workers: int,
        timeout_seconds: float,
        memory_mb: int,
    ) -> None:
        self.store = store
        self.work_dir = work_dir
        self.timeout = timeout_seconds
        self.memory_mb = memory_mb
        self._sem = asyncio.Semaphore(max_workers)
        self._jobs: dict[str, Job] = {}
        self._procs: dict[str, Any] = {}
        self._cancel_requested: set[str] = set()
        self._changed = asyncio.Condition()
        self._tasks: set[asyncio.Task[None]] = set()
        self._mp = mp.get_context("spawn")
        work_dir.mkdir(parents=True, exist_ok=True)

    # -- public API ------------------------------------------------------
    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def submit(self, op: str, params: dict[str, Any], inputs: list[tuple[Path, str, str]]) -> Job:
        job = Job(id=secrets.token_urlsafe(16), op=op)
        self._jobs[job.id] = job
        task = asyncio.create_task(self._run(job, params, inputs))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None or job.status in TERMINAL:
            return False
        self._cancel_requested.add(job_id)
        proc = self._procs.get(job_id)
        if proc is not None and proc.is_alive():
            proc.terminate()
        return True

    async def wait_change(self, job: Job, seen_version: int, timeout: float) -> None:
        """Block until ``job.version`` moves past ``seen_version`` (or timeout)."""
        async with self._changed:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    self._changed.wait_for(lambda: job.version != seen_version),
                    timeout,
                )

    def sweep(self, ttl_seconds: float, now: float | None = None) -> None:
        now = now or time.time()
        for jid, job in list(self._jobs.items()):
            if job.finished and now - job.finished > ttl_seconds:
                del self._jobs[jid]

    async def shutdown(self) -> None:
        for proc in list(self._procs.values()):
            if proc.is_alive():
                proc.terminate()
        for t in list(self._tasks):
            t.cancel()

    # -- internals ---------------------------------------------------------
    async def _update(self, job: Job, **changes: Any) -> None:
        for k, v in changes.items():
            setattr(job, k, v)
        job.version += 1
        async with self._changed:
            self._changed.notify_all()

    async def _run(self, job: Job, params: dict[str, Any], inputs: list[tuple[Path, str, str]]) -> None:
        job_dir = self.work_dir / job.id
        try:
            async with self._sem:
                if job.id in self._cancel_requested:
                    await self._update(job, status="cancelled", finished=time.time())
                    return
                job_dir.mkdir()
                await self._update(job, status="running")
                outcome = await self._execute(job, params, inputs, job_dir)
            await self._finish(job, outcome)
        except asyncio.CancelledError:
            raise
        except Exception:
            await self._update(
                job,
                status="failed",
                error={"tr": "İşlem başarısız oldu.", "en": "The operation failed."},
                finished=time.time(),
            )
        finally:
            self._procs.pop(job.id, None)
            self._cancel_requested.discard(job.id)
            shutil.rmtree(job_dir, ignore_errors=True)

    async def _execute(
        self, job: Job, params: dict[str, Any], inputs: list[tuple[Path, str, str]], job_dir: Path
    ) -> tuple[str, Any]:
        loop = asyncio.get_running_loop()
        parent, child = self._mp.Pipe(duplex=False)
        proc = self._mp.Process(
            target=worker.run,
            args=(child, job.op, params, [(str(p), n, pw) for p, n, pw in inputs], str(job_dir), self.memory_mb),
            daemon=True,
        )
        self._procs[job.id] = proc
        proc.start()
        child.close()

        final: asyncio.Future[tuple[str, Any]] = loop.create_future()

        def settle(value: tuple[str, Any]) -> None:
            if not final.done():
                final.set_result(value)

        def pump() -> None:
            # Runs in a plain thread: blocking recv() must stay off the loop.
            try:
                while True:
                    msg = parent.recv()
                    if msg[0] == "progress":
                        asyncio.run_coroutine_threadsafe(self._update(job, progress=msg[1], message=msg[2]), loop)
                    else:
                        loop.call_soon_threadsafe(settle, (msg[0], msg[1]))
                        return
            except (EOFError, OSError):
                loop.call_soon_threadsafe(settle, ("died", None))
            finally:
                parent.close()

        threading.Thread(target=pump, name=f"job-{job.id[:6]}", daemon=True).start()
        try:
            outcome = await asyncio.wait_for(asyncio.shield(final), self.timeout)
        except TimeoutError:
            proc.terminate()
            outcome = ("timeout", None)
        await loop.run_in_executor(None, proc.join, 5)
        if proc.is_alive():
            proc.kill()
        if job.id in self._cancel_requested:
            return ("cancelled", None)
        return outcome

    async def _finish(self, job: Job, outcome: tuple[str, Any]) -> None:
        kind, payload = outcome
        now = time.time()
        if kind == "done":
            loop = asyncio.get_running_loop()
            outputs = [
                await loop.run_in_executor(None, self.store.register_output, Path(p), name) for p, name in payload
            ]
            result = outputs[0] if len(outputs) == 1 else await self._bundle(job, payload)
            await self._update(job, status="done", progress=1.0, outputs=outputs, result=result, finished=now)
        elif kind == "cancelled":
            await self._update(job, status="cancelled", finished=now)
        elif kind == "error":
            await self._update(job, status="failed", error=payload, finished=now)
        elif kind == "timeout":
            await self._update(
                job,
                status="failed",
                error={"tr": "İşlem zaman aşımına uğradı.", "en": "The operation timed out."},
                finished=now,
            )
        else:
            await self._update(
                job,
                status="failed",
                error={
                    "tr": "İşlem beklenmedik şekilde sonlandı (bellek sınırı?).",
                    "en": "The operation ended unexpectedly (memory limit?).",
                },
                finished=now,
            )

    async def _bundle(self, job: Job, outputs: list[tuple[str, str]]) -> StoredFile:
        zip_path = self.work_dir / job.id / "_bundle.zip"

        stem = outputs[0][1].rsplit(".", 1)[0]

        def build() -> StoredFile:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for path, name in outputs:
                    zf.write(path, name)
            return self.store.register_output(zip_path, f"{stem}_sonuclar.zip")

        return await asyncio.get_running_loop().run_in_executor(None, build)
