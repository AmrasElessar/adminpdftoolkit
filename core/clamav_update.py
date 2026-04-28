"""ClamAV signature-database update orchestration.

The portable bundle ships ``clamav/clamscan.exe`` + ``clamav/freshclam.exe``
but **not** the ~300 MB signature databases — they're downloaded on first
boot and refreshed periodically. Same pattern as the EasyOCR model lazy-load.

Lifecycle
---------
- App startup (``app.py:_lifespan``) spawns a daemon thread that calls
  :func:`maybe_update`.
- ``maybe_update()`` is a no-op when ClamAV isn't bundled (the binary
  doesn't exist), so a system-installed ``clamscan`` won't be touched —
  we don't manage updates for OS-managed installs.
- Otherwise it checks the on-disk DB age. Missing or older than
  ``UPDATE_INTERVAL_SECONDS`` (default 24 h) triggers a ``freshclam``
  subprocess. The throttle prevents back-to-back runs if the app is
  restarted often.
- A small JSON state file under ``_work/clamav_state.json`` records the
  last successful run + the last attempt + last error. Surfaces via the
  ``/admin/clamav`` endpoint.

Failure modes
-------------
- No internet / mirror down → freshclam exits non-zero; we record the
  error and keep the existing DB. The next attempt happens on the next
  app start (after the throttle expires).
- DB partial (download interrupted) → freshclam handles atomic replace
  on its own; we don't try to second-guess it.

Tests must NEVER reach the network. ``update_signatures`` is the
subprocess-runner; tests should monkeypatch ``subprocess.run`` and
``_clamav_dir`` to a tmp path.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from .logging_setup import logger

# 24 h is ClamAV's own recommended cadence; sigs are typically refreshed
# multiple times a day upstream but pulling more often is wasteful.
UPDATE_INTERVAL_SECONDS = 24 * 60 * 60

# Background freshclam may genuinely take a while on the first cold-fetch
# (~300 MB on slow connections). Cap the wait so a stuck network doesn't
# pin the daemon thread forever.
FRESHCLAM_TIMEOUT_SECONDS = 600  # 10 minutes

# DB filenames freshclam produces; their presence is our "DB ready" marker.
_DB_FILES = ("main.cvd", "main.cld", "daily.cvd", "daily.cld")


def _clamav_dir() -> Path:
    """Resolve the bundled ClamAV folder. Read at call time so tests can
    monkeypatch ``core.BASE_DIR`` and have it picked up."""
    import core
    return core.BASE_DIR / "clamav"


def _database_dir() -> Path:
    return _clamav_dir() / "database"


def _state_file() -> Path:
    """Per-install state — lives under WORK_DIR so portable installs can
    keep the bundle dir read-only if they want."""
    import core
    p = core.WORK_DIR / "clamav_state.json"
    return p


def _freshclam_exe() -> Path | None:
    """Bundled freshclam binary. Returns None if not present (i.e. ClamAV
    isn't bundled in this install — likely a dev / Linux setup using the
    system's clamscan instead)."""
    cd = _clamav_dir()
    for name in ("freshclam.exe", "freshclam"):
        cand = cd / name
        if cand.exists():
            return cand
    return None


def _read_state() -> dict[str, Any]:
    sf = _state_file()
    if not sf.exists():
        return {}
    try:
        return json.loads(sf.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug("clamav state read failed: %s", e)
        return {}


def _write_state(state: dict[str, Any]) -> None:
    sf = _state_file()
    try:
        sf.parent.mkdir(parents=True, exist_ok=True)
        tmp = sf.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(sf)
    except Exception as e:
        logger.debug("clamav state write failed: %s", e)


def _db_present() -> bool:
    """At least one signature DB file exists in the database dir."""
    dd = _database_dir()
    if not dd.is_dir():
        return False
    return any((dd / name).exists() for name in _DB_FILES)


def _db_age_seconds() -> float | None:
    """Age (s) of the freshest DB file, or None if no DB present."""
    dd = _database_dir()
    if not dd.is_dir():
        return None
    mtimes = []
    for name in _DB_FILES:
        f = dd / name
        if f.exists():
            try:
                mtimes.append(f.stat().st_mtime)
            except OSError:
                pass
    if not mtimes:
        return None
    return time.time() - max(mtimes)


def should_update(*, force: bool = False) -> bool:
    """Decide whether to run freshclam now.

    True when:
      - ClamAV is bundled (freshclam exists), AND
      - either the DB is missing, OR the freshest DB file is older than
        ``UPDATE_INTERVAL_SECONDS``, OR ``force`` is set.

    False when ClamAV isn't bundled — caller should fall back to whatever
    system-installed clamscan finds on its own.
    """
    if _freshclam_exe() is None:
        return False
    if force:
        return True
    if not _db_present():
        return True
    age = _db_age_seconds()
    if age is None:
        return True
    return age > UPDATE_INTERVAL_SECONDS


def update_signatures(*, timeout: int = FRESHCLAM_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Invoke freshclam to refresh the signature databases.

    Returns a result dict ``{"ok": bool, "took_s": float, "error": str|None,
    "stdout_tail": str}``. Always records to the state file regardless of
    outcome so ``status()`` can report failures to the admin UI.
    """
    exe = _freshclam_exe()
    started = time.time()
    state = _read_state()
    state["last_attempt_ts"] = started

    if exe is None:
        result = {"ok": False, "took_s": 0.0,
                  "error": "freshclam not bundled (no ./clamav/freshclam.exe)",
                  "stdout_tail": ""}
        state["last_error"] = result["error"]
        _write_state(state)
        return result

    db_dir = _database_dir()
    db_dir.mkdir(parents=True, exist_ok=True)
    cwd = exe.parent

    # Use the bundled freshclam.conf if present; otherwise pass DatabaseDirectory
    # via CLI so freshclam knows where to land the .cvd files.
    conf = cwd / "freshclam.conf"
    cmd = [str(exe)]
    if conf.exists():
        cmd += ["--config-file", str(conf)]
    cmd += [f"--datadir={db_dir}", "--no-warnings"]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        took = time.time() - started
        out = (proc.stdout or "") + (proc.stderr or "")
        # freshclam exits 0 on success or 1 when DB is already up-to-date
        # (also treated as ok). Anything else is a failure.
        ok = proc.returncode in (0, 1)
        tail = "\n".join(out.splitlines()[-15:])
        result = {"ok": ok, "took_s": round(took, 2),
                  "error": None if ok else f"exit={proc.returncode}",
                  "stdout_tail": tail}
        if ok:
            state["last_success_ts"] = time.time()
            state.pop("last_error", None)
        else:
            state["last_error"] = f"freshclam exit={proc.returncode}; tail: {tail[:500]}"
        _write_state(state)
        if ok:
            logger.info("clamav signatures refreshed in %.1fs", took)
        else:
            logger.warning("freshclam failed (exit=%s)", proc.returncode)
        return result
    except subprocess.TimeoutExpired:
        took = time.time() - started
        result = {"ok": False, "took_s": round(took, 2),
                  "error": f"timeout after {timeout}s",
                  "stdout_tail": ""}
        state["last_error"] = result["error"]
        _write_state(state)
        logger.warning("freshclam timed out after %ss", timeout)
        return result
    except Exception as e:
        took = time.time() - started
        result = {"ok": False, "took_s": round(took, 2),
                  "error": str(e), "stdout_tail": ""}
        state["last_error"] = str(e)
        _write_state(state)
        logger.warning("freshclam failed: %s", e)
        return result


def maybe_update() -> dict[str, Any] | None:
    """Throttled helper for the lifespan thread. No-op when bundled
    ClamAV isn't present or DB is fresh enough."""
    if not should_update():
        return None
    return update_signatures()


def status() -> dict[str, Any]:
    """Snapshot for the ``/admin/clamav`` endpoint."""
    exe = _freshclam_exe()
    age = _db_age_seconds()
    state = _read_state()
    return {
        "bundled": exe is not None,
        "freshclam_path": str(exe) if exe else None,
        "database_dir": str(_database_dir()),
        "database_present": _db_present(),
        "database_age_s": round(age, 1) if age is not None else None,
        "database_age_human": _format_age(age),
        "needs_update": should_update(),
        "last_success_ts": state.get("last_success_ts"),
        "last_attempt_ts": state.get("last_attempt_ts"),
        "last_error": state.get("last_error"),
        "update_interval_s": UPDATE_INTERVAL_SECONDS,
    }


def _format_age(age_s: float | None) -> str:
    if age_s is None:
        return "no database"
    if age_s < 60:
        return f"{age_s:.0f} s"
    if age_s < 3600:
        return f"{age_s / 60:.0f} min"
    if age_s < 86400:
        return f"{age_s / 3600:.1f} h"
    return f"{age_s / 86400:.1f} d"
