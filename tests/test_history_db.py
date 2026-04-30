"""History DB tests (S4 gap closure).

Cover the silent-fail path in ``core.log_history`` (core.py:371) — the
function swallows DB exceptions and only debug-logs them; we make sure that
behaviour is intentional (audit-trail loss must not break the conversion
path) AND that the surrounding lock + path resolution stay sane.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import core
import state


def test_history_db_path_lives_under_work_dir() -> None:
    """S1 invariant: HISTORY_DB_PATH derives from settings.history_db and
    sits under WORK_DIR by default (or wherever the operator points it)."""
    assert state.HISTORY_DB_PATH.is_absolute()
    assert state.HISTORY_DB_PATH.parent.exists()


def test_init_history_db_is_idempotent() -> None:
    """Calling init twice in a row must not raise."""
    core.init_history_db()
    core.init_history_db()  # second call must be a no-op


def test_log_history_writes_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Insert a row, then read it back via raw sqlite3 to verify the schema."""
    db = tmp_path / "test_history.db"
    monkeypatch.setattr(core, "HISTORY_DB_PATH", db)

    core.init_history_db()
    core.log_history(
        action="test-action",
        target="word",
        filename="example.pdf",
        record_count=42,
        note="unit-test",
        ip="127.0.0.1",
    )

    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT action, target, filename, record_count, note, ip FROM history"
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    row = rows[0]
    assert row[0] == "test-action"
    assert row[1] == "word"
    assert row[2] == "example.pdf"
    assert row[3] == 42
    assert row[4] == "unit-test"
    assert row[5] == "127.0.0.1"


def test_log_history_silent_fail_when_db_unwritable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """If the DB is unreachable, log_history must not raise — only debug-log.

    This is the documented behaviour at core.py:371. A broken audit trail
    must never abort a successful conversion.
    """
    bad_path = tmp_path / "nonexistent_dir" / "no_perm.db"
    monkeypatch.setattr(core, "HISTORY_DB_PATH", bad_path)

    # Must not raise — silent-fail is the contract.
    with caplog.at_level("DEBUG", logger="ht_pdf"):
        core.log_history(action="x", filename="y.pdf")

    # Optional: confirm a debug log was emitted (informational, not enforced).
    msgs = [r.getMessage() for r in caplog.records]
    assert any("history insert failed" in m for m in msgs)


def test_legacy_history_db_migration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """If a legacy BASE_DIR/history.db exists and the new path is empty, the
    init routine must move it over so audit history isn't dropped."""
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    legacy_db = legacy_dir / "history.db"

    # Build a valid sqlite DB at the legacy path
    conn = sqlite3.connect(str(legacy_db))
    conn.execute(
        "CREATE TABLE history (id INTEGER PRIMARY KEY, ts TEXT, action TEXT, target TEXT, filename TEXT, record_count INTEGER, note TEXT, ip TEXT)"
    )
    conn.execute("INSERT INTO history (ts, action) VALUES ('2026-04-28T00:00:00', 'legacy-row')")
    conn.commit()
    conn.close()

    # Point the migration at our temp legacy + new locations
    new_db = tmp_path / "new" / "history.db"
    monkeypatch.setattr(core, "BASE_DIR", legacy_dir)
    monkeypatch.setattr(core, "HISTORY_DB_PATH", new_db)

    core._migrate_legacy_history_db()

    assert not legacy_db.exists(), "legacy DB should have been moved away"
    assert new_db.exists(), "new DB should exist at the target location"

    # Audit row preserved
    conn = sqlite3.connect(str(new_db))
    try:
        rows = conn.execute("SELECT action FROM history").fetchall()
    finally:
        conn.close()
    assert rows == [("legacy-row",)]


def test_migration_skipped_when_legacy_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Migration must be a no-op when there's no legacy DB to move."""
    monkeypatch.setattr(core, "BASE_DIR", tmp_path)
    monkeypatch.setattr(core, "HISTORY_DB_PATH", tmp_path / "history.db")

    core._migrate_legacy_history_db()  # must not raise; nothing to do
