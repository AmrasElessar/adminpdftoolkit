"""Job state — timeout flagging + on-disk persistence + snapshot lookup."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from state import (
    convert_jobs,
    batch_jobs,
    ocr_jobs,
    convert_lock,
    batch_lock,
    ocr_lock,
)

from .logging_setup import logger

# STATE_DIR and MAX_JOB_TIMEOUT_SECONDS are looked up off the `core` package
# at call time (tests monkeypatch ``core.STATE_DIR`` / ``core.MAX_JOB_...``).


def check_job_timeout(job: dict) -> dict:
    """Mark a job as errored if it has run past MAX_JOB_TIMEOUT_SECONDS."""
    import core
    if job.get("done") or job.get("error"):
        return job
    started = job.get("started_at")
    if started is None:
        return job
    if (time.time() - float(started)) > core.MAX_JOB_TIMEOUT_SECONDS:
        job["error"] = (
            f"İş zaman aşımına uğradı (>{core.MAX_JOB_TIMEOUT_SECONDS // 60} dk). "
            "Daha küçük bir dosya/parti deneyin."
        )
        job["done"] = True
    return job


def state_path(kind: str, token: str) -> Path:
    import core
    sub = core.STATE_DIR / kind
    sub.mkdir(parents=True, exist_ok=True)
    return sub / f"{token}.json"


def persist_job_state(kind: str, token: str, job: dict) -> None:
    """Atomically write a job's state to disk; never raises into the worker."""
    try:
        safe: dict[str, Any] = {}
        for k, v in job.items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                safe[k] = v
            elif isinstance(v, (list, dict)):
                try:
                    json.dumps(v)
                    safe[k] = v
                except TypeError:
                    safe[k] = str(v)
            else:
                safe[k] = str(v)
        path = state_path(kind, token)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(safe), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        logger.debug("failed to persist job state %s/%s: %s", kind, token, e)


def load_persisted_state(kind: str, token: str) -> dict | None:
    path = state_path(kind, token)
    if not path.exists():
        return None
    try:
        loaded: dict | None = json.loads(path.read_text(encoding="utf-8"))
        return loaded
    except Exception as e:
        logger.debug("failed to load job state %s/%s: %s", kind, token, e)
        return None


def drop_persisted_state(kind: str, token: str) -> None:
    try:
        state_path(kind, token).unlink(missing_ok=True)
    except Exception:
        pass


def job_snapshot(kind: str, token: str) -> dict | None:
    """Return a JSON-serialisable snapshot or None."""
    if kind == "convert":
        jobs, lock = convert_jobs, convert_lock
    elif kind == "batch":
        jobs, lock = batch_jobs, batch_lock
    elif kind == "ocr":
        jobs, lock = ocr_jobs, ocr_lock
    else:
        return None
    with lock:
        job = jobs.get(token)
        if job:
            check_job_timeout(job)
            return dict(job)
    return load_persisted_state(kind, token)
