"""Periodic cleanup: orphan job dirs, stale in-memory entries, stale state files."""

from __future__ import annotations

import shutil
import threading
import time

from state import (
    WORK_DIR,
    STATE_DIR,
    WORK_TTL,
    JOB_MEMORY_TTL,
    CLEANUP_INTERVAL,
    MAX_JOB_TIMEOUT_SECONDS,
    convert_jobs,
    batch_jobs,
    ocr_jobs,
    convert_lock,
    batch_lock,
    ocr_lock,
)

from .jobs import drop_persisted_state
from .logging_setup import logger


def cleanup_orphan_dirs() -> None:
    """Delete stale subdirectories under WORK_DIR/{convert,batch,ocr,jobs}."""
    now = time.time()
    cutoff = now - WORK_TTL
    for sub in ("convert", "batch", "ocr", "jobs"):
        base = WORK_DIR / sub
        if not base.exists():
            continue
        for d in base.iterdir():
            if not d.is_dir():
                continue
            try:
                if d.stat().st_mtime < cutoff:
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                continue


def cleanup_job_memory() -> None:
    """Purge stale in-memory job entries + their persisted state files."""
    now = time.time()
    cutoff = now - JOB_MEMORY_TTL

    def _purge(kind: str, jobs: dict, lock: threading.Lock) -> None:
        try:
            with lock:
                stale = [t for t, j in jobs.items() if j.get("started_at", now) < cutoff]
                for t in stale:
                    jd = jobs[t].get("job_dir")
                    jobs.pop(t, None)
                    if jd:
                        shutil.rmtree(jd, ignore_errors=True)
                    drop_persisted_state(kind, t)
        except NameError:
            return

    _purge("convert", convert_jobs, convert_lock)
    _purge("batch", batch_jobs, batch_lock)
    _purge("ocr", ocr_jobs, ocr_lock)

    # Reap orphaned state files (process crashed before reaching the finally).
    try:
        orphan_cutoff = now - max(JOB_MEMORY_TTL, MAX_JOB_TIMEOUT_SECONDS * 2)
        for sub in STATE_DIR.iterdir():
            if not sub.is_dir():
                continue
            for f in sub.glob("*.json"):
                try:
                    if f.stat().st_mtime < orphan_cutoff:
                        f.unlink(missing_ok=True)
                except OSError:
                    continue
    except Exception:
        pass


def startup_cleanup() -> None:
    """One-shot cleanup at server boot — clears anything left over from the
    last process. Safer than waiting for the periodic loop."""
    cleanup_orphan_dirs()
    cleanup_job_memory()


def cleanup_loop(interval_seconds: int | None = None) -> None:
    """Background sweeper, started on a daemon thread at boot.

    interval_seconds defaults to state.CLEANUP_INTERVAL so callers that
    started the thread before the parameter existed (``threading.Thread(
    target=cleanup_loop)``) keep working.
    """
    if interval_seconds is None:
        interval_seconds = CLEANUP_INTERVAL
    while True:
        try:
            cleanup_orphan_dirs()
            cleanup_job_memory()
        except Exception as e:
            logger.warning("cleanup loop error: %s", e)
        time.sleep(interval_seconds)
