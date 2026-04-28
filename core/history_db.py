"""SQLite history log of every conversion / batch / OCR / distribute action."""

from __future__ import annotations

import shutil
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .logging_setup import logger

# Read BASE_DIR / HISTORY_DB_PATH off the `core` package at call time so
# tests that monkeypatch ``core.HISTORY_DB_PATH`` / ``core.BASE_DIR`` keep
# working (the alternative — binding them at import time — would freeze the
# values inside this module's namespace).
_history_lock = threading.Lock()

# Single process-wide connection cached by path. The lock above already
# serialises every access, so ``check_same_thread=False`` is safe — pyflakes
# will complain about the global, that's fine.
_conn_cache: tuple[Path, sqlite3.Connection] | None = None


def _get_conn() -> sqlite3.Connection:
    """Return a cached SQLite connection for the current ``HISTORY_DB_PATH``.

    Opens lazily on first use and re-opens if the path was monkeypatched
    (tests do this). Sets WAL journal mode so reader processes (CLI tools,
    other test fixtures) can see committed rows without a checkpoint roundtrip.
    """
    global _conn_cache
    import core
    path = core.HISTORY_DB_PATH
    if _conn_cache is not None and _conn_cache[0] == path:
        return _conn_cache[1]
    if _conn_cache is not None:
        try:
            _conn_cache[1].close()
        except Exception:
            pass
        _conn_cache = None
    conn = sqlite3.connect(str(path), check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        pass
    _conn_cache = (path, conn)
    return conn


def _migrate_legacy_history_db() -> None:
    """One-shot move of the historical BASE_DIR/history.db into its new home.

    Pre-S1 versions kept history.db in the project root; S1 moved it under
    _work/. If the operator upgrades in place we don't want to silently drop
    their audit trail — move it across once on first init, idempotent.
    """
    import core
    legacy = core.BASE_DIR / "history.db"
    if legacy == core.HISTORY_DB_PATH:
        return
    if legacy.exists() and not core.HISTORY_DB_PATH.exists():
        try:
            core.HISTORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy), str(core.HISTORY_DB_PATH))
            logger.info("history.db migrated from %s to %s", legacy, core.HISTORY_DB_PATH)
        except OSError as e:
            logger.warning("history.db migration skipped: %s", e)


def init_history_db() -> None:
    """Create the history table if missing; idempotent."""
    _migrate_legacy_history_db()
    with _history_lock:
        conn = _get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                filename TEXT,
                record_count INTEGER,
                note TEXT,
                ip TEXT
            )
            """
        )
        conn.commit()


def log_history(
    action: str,
    *,
    target: str | None = None,
    filename: str | None = None,
    record_count: int | None = None,
    note: str | None = None,
    ip: str | None = None,
) -> None:
    """Append one row to the history log; failures are swallowed (debug-logged)."""
    try:
        with _history_lock:
            conn = _get_conn()
            conn.execute(
                "INSERT INTO history (ts, action, target, filename, record_count, note, ip) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now().isoformat(timespec="seconds"),
                    action,
                    target,
                    filename,
                    record_count,
                    note,
                    ip,
                ),
            )
            conn.commit()
    except Exception as e:
        logger.debug("history insert failed: %s", e)
