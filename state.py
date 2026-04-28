"""Shared mutable state and configuration constants.

Lives in its own module so both ``app.py`` and any router module can import
the same dict / lock objects without creating an import cycle through
``app.py``.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from settings import settings

# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent
TEMPLATES_DIR: Path = BASE_DIR / "templates"
STATIC_DIR: Path = BASE_DIR / "static"
WORK_DIR: Path = BASE_DIR / settings.work_dir
WORK_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

STATE_DIR: Path = WORK_DIR / "_state"
STATE_DIR.mkdir(exist_ok=True)

# Single source of truth for the history DB path. Settings field is relative
# by default; if the operator provides an absolute path it's honoured as-is.
HISTORY_DB_PATH: Path = (
    settings.history_db
    if settings.history_db.is_absolute()
    else BASE_DIR / settings.history_db
)
HISTORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------
# Kept as plain int (not Settings ref) so existing code that reads it inline
# stays trivial. Override via env var HT_MAX_UPLOAD_MB or MAX_UPLOAD_MB.
MAX_UPLOAD_MB: int = int(os.environ.get("MAX_UPLOAD_MB", str(settings.max_upload_mb)))
MAX_JOB_TIMEOUT_SECONDS: int = int(
    os.environ.get("MAX_JOB_TIMEOUT_SECONDS", str(settings.max_job_timeout_seconds))
)

ALLOWED_FORMATS: set[str] = {"excel", "word", "jpg"}

# Cleanup TTLs
WORK_TTL: int = settings.work_ttl_seconds
JOB_MEMORY_TTL: int = settings.job_memory_ttl_seconds
CLEANUP_INTERVAL: int = settings.cleanup_interval_seconds

# ---------------------------------------------------------------------------
# In-memory job tracking — shared across endpoints.
# ---------------------------------------------------------------------------
convert_jobs: dict[str, dict[str, Any]] = {}
batch_jobs: dict[str, dict[str, Any]] = {}
ocr_jobs: dict[str, dict[str, Any]] = {}

convert_lock = threading.Lock()
batch_lock = threading.Lock()
ocr_lock = threading.Lock()

# ---------------------------------------------------------------------------
# JobStore — wraps a (dict, lock) pair with the small handful of patterns
# every worker needs: create, locked update, locked snapshot, pop. Removes
# the four near-identical "with X_lock: X_jobs[token][...] = ..." blocks
# that lived in the four worker functions.
# ---------------------------------------------------------------------------


class JobStore:
    """Thread-safe store for in-flight job state.

    Workers call ``update`` for each phase change instead of writing through
    the bare dict + lock; readers (progress endpoints) call ``snapshot`` to
    get a consistent locked dict copy.
    """

    __slots__ = ("_jobs", "_lock")

    def __init__(self, jobs: dict[str, dict[str, Any]], lock: threading.Lock) -> None:
        self._jobs = jobs
        self._lock = lock

    @property
    def jobs(self) -> dict[str, dict[str, Any]]:
        return self._jobs

    @property
    def lock(self) -> threading.Lock:
        return self._lock

    def create(self, token: str, **fields: Any) -> None:
        with self._lock:
            self._jobs[token] = dict(fields)

    def update(self, token: str, **fields: Any) -> None:
        """Set one or more fields on an existing job. Silently no-ops if the
        token has been purged — callers don't need to guard around races
        between cleanup and the worker's final write."""
        with self._lock:
            job = self._jobs.get(token)
            if job is None:
                return
            for k, v in fields.items():
                job[k] = v

    def snapshot(self, token: str) -> dict[str, Any] | None:
        """Locked dict copy or None if missing."""
        with self._lock:
            job = self._jobs.get(token)
            return dict(job) if job else None

    def pop(self, token: str) -> dict[str, Any] | None:
        with self._lock:
            return self._jobs.pop(token, None)

    def get_field(self, token: str, key: str, default: Any = None) -> Any:
        with self._lock:
            job = self._jobs.get(token)
            return default if job is None else job.get(key, default)


convert_store = JobStore(convert_jobs, convert_lock)
batch_store = JobStore(batch_jobs, batch_lock)
ocr_store = JobStore(ocr_jobs, ocr_lock)


# ---------------------------------------------------------------------------
# Mobile / LAN access control
# ---------------------------------------------------------------------------
# When None, the server only accepts requests from 127.0.0.1 (the host PC's
# own browser). When the user clicks "Mobil Aç" on the local UI, a
# secrets.token_urlsafe(32) is generated and stored here; remote clients must
# present that token (X-Mobile-Key header or ?key= URL param) to talk to any
# protected endpoint. Lives in RAM only — server restart wipes it.
mobile_token: str | None = None
mobile_token_lock = threading.Lock()
