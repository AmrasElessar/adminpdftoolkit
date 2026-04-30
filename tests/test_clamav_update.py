"""Tests for ``core.clamav_update`` — the freshclam orchestration layer.

We never reach the network here. ``update_signatures`` shells out to
freshclam via ``subprocess.run``; tests monkeypatch that, plus the
on-disk paths, so the orchestration logic is covered end-to-end without
needing the real binary.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

import core
from core import clamav_update


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_clamav_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``core.BASE_DIR`` + ``core.WORK_DIR`` at tmp paths so the
    module-under-test reads/writes inside the test sandbox."""
    base = tmp_path / "base"
    work = tmp_path / "work"
    base.mkdir()
    work.mkdir()
    monkeypatch.setattr(core, "BASE_DIR", base)
    monkeypatch.setattr(core, "WORK_DIR", work)
    return base / "clamav"


def _make_freshclam(clamav_dir: Path) -> Path:
    """Drop a stub ``freshclam.exe`` so ``_freshclam_exe()`` returns truthy."""
    clamav_dir.mkdir(parents=True, exist_ok=True)
    exe = clamav_dir / "freshclam.exe"
    exe.write_bytes(b"")
    return exe


def _make_db(clamav_dir: Path, *, age_seconds: float = 0) -> None:
    """Create a fake DB file with a controlled mtime."""
    db = clamav_dir / "database"
    db.mkdir(parents=True, exist_ok=True)
    sig = db / "main.cvd"
    sig.write_bytes(b"fake")
    if age_seconds > 0:
        old = time.time() - age_seconds
        import os

        os.utime(sig, (old, old))


# ---------------------------------------------------------------------------
# should_update()
# ---------------------------------------------------------------------------
def test_should_update_false_when_freshclam_missing(fake_clamav_dir: Path):
    # No freshclam binary at all → bundled ClamAV not installed → don't poke.
    assert clamav_update.should_update() is False


def test_should_update_true_when_db_missing(fake_clamav_dir: Path):
    _make_freshclam(fake_clamav_dir)
    assert clamav_update.should_update() is True


def test_should_update_false_when_db_fresh(fake_clamav_dir: Path):
    _make_freshclam(fake_clamav_dir)
    _make_db(fake_clamav_dir, age_seconds=60)  # 1 min old
    assert clamav_update.should_update() is False


def test_should_update_true_when_db_stale(fake_clamav_dir: Path):
    _make_freshclam(fake_clamav_dir)
    _make_db(fake_clamav_dir, age_seconds=clamav_update.UPDATE_INTERVAL_SECONDS + 60)
    assert clamav_update.should_update() is True


def test_should_update_force(fake_clamav_dir: Path):
    _make_freshclam(fake_clamav_dir)
    _make_db(fake_clamav_dir, age_seconds=10)
    assert clamav_update.should_update(force=True) is True


# ---------------------------------------------------------------------------
# update_signatures()
# ---------------------------------------------------------------------------
def test_update_signatures_skips_when_not_bundled(fake_clamav_dir: Path):
    result = clamav_update.update_signatures()
    assert result["ok"] is False
    assert "not bundled" in (result["error"] or "")


def test_update_signatures_success(fake_clamav_dir: Path, monkeypatch: pytest.MonkeyPatch):
    _make_freshclam(fake_clamav_dir)

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="ClamAV update process started\nmain.cvd updated\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = clamav_update.update_signatures()
    assert result["ok"] is True
    assert result["error"] is None
    assert "main.cvd updated" in result["stdout_tail"]


def test_update_signatures_treats_exit_1_as_ok(
    fake_clamav_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    """freshclam exits 1 when the DB is already up to date — that's not a failure."""
    _make_freshclam(fake_clamav_dir)

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout="DB up-to-date\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = clamav_update.update_signatures()
    assert result["ok"] is True


def test_update_signatures_failure_records_error(
    fake_clamav_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    _make_freshclam(fake_clamav_dir)

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=2,
            stdout="",
            stderr="Can't connect to mirror",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = clamav_update.update_signatures()
    assert result["ok"] is False
    assert "exit=2" in result["error"]
    # State file should record the error for the admin endpoint to surface.
    state = json.loads(clamav_update._state_file().read_text(encoding="utf-8"))
    assert state["last_error"]
    assert "exit=2" in state["last_error"]


def test_update_signatures_timeout(fake_clamav_dir: Path, monkeypatch: pytest.MonkeyPatch):
    _make_freshclam(fake_clamav_dir)

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = clamav_update.update_signatures(timeout=1)
    assert result["ok"] is False
    assert "timeout" in result["error"]


# ---------------------------------------------------------------------------
# maybe_update() — the lifespan hook
# ---------------------------------------------------------------------------
def test_maybe_update_noop_when_not_bundled(fake_clamav_dir: Path):
    assert clamav_update.maybe_update() is None


def test_maybe_update_runs_when_db_missing(fake_clamav_dir: Path, monkeypatch: pytest.MonkeyPatch):
    _make_freshclam(fake_clamav_dir)
    called = {"n": 0}

    def fake_run(cmd, **kwargs):
        called["n"] += 1
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="updated\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = clamav_update.maybe_update()
    assert result is not None
    assert result["ok"] is True
    assert called["n"] == 1


def test_maybe_update_skips_when_fresh(fake_clamav_dir: Path):
    _make_freshclam(fake_clamav_dir)
    _make_db(fake_clamav_dir, age_seconds=60)
    assert clamav_update.maybe_update() is None


# ---------------------------------------------------------------------------
# status()
# ---------------------------------------------------------------------------
def test_status_when_unbundled(fake_clamav_dir: Path):
    s = clamav_update.status()
    assert s["bundled"] is False
    assert s["database_present"] is False
    assert s["database_age_human"] == "no database"
    assert s["needs_update"] is False


def test_status_with_fresh_db(fake_clamav_dir: Path):
    _make_freshclam(fake_clamav_dir)
    _make_db(fake_clamav_dir, age_seconds=120)  # 2 min old
    s = clamav_update.status()
    assert s["bundled"] is True
    assert s["database_present"] is True
    assert s["database_age_s"] is not None and s["database_age_s"] >= 100
    assert "min" in s["database_age_human"]
    assert s["needs_update"] is False
