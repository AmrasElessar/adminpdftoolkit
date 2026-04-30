"""Unit tests for ``state.JobStore``.

The store is a thin wrapper over ``(jobs_dict, lock)`` that the four
worker functions (ocr / convert / batch_files / batch_convert) all use
in place of bare ``with X_lock: X_jobs[token][...] = ...`` blocks. These
tests pin its contract — race-safe updates, no-op on missing tokens,
locked snapshots, and the legacy ``.lock`` / ``.jobs`` accessors that the
batch worker's ``files_progress`` mutator still uses directly.
"""

from __future__ import annotations

import threading

from state import JobStore


def _new_store() -> JobStore:
    return JobStore({}, threading.Lock())


def test_create_then_snapshot_returns_copy() -> None:
    store = _new_store()
    store.create("tok", phase="starting", current=0, total=10)
    snap = store.snapshot("tok")
    assert snap == {"phase": "starting", "current": 0, "total": 10}
    # snapshot must be a copy — mutating it doesn't reach the store
    snap["phase"] = "tampered"
    assert store.snapshot("tok")["phase"] == "starting"


def test_snapshot_missing_token_returns_none() -> None:
    store = _new_store()
    assert store.snapshot("nope") is None


def test_update_merges_fields() -> None:
    store = _new_store()
    store.create("tok", phase="starting", current=0)
    store.update("tok", phase="processing", current=3)
    assert store.snapshot("tok") == {"phase": "processing", "current": 3}


def test_update_missing_token_is_silent() -> None:
    """The four workers race against the cleanup loop; they must not crash
    if the cleanup loop already purged their token before the final write."""
    store = _new_store()
    store.update("ghost", phase="done", done=True)  # no exception
    assert store.snapshot("ghost") is None


def test_pop_removes_and_returns() -> None:
    store = _new_store()
    store.create("tok", phase="done")
    popped = store.pop("tok")
    assert popped == {"phase": "done"}
    assert store.snapshot("tok") is None


def test_pop_missing_returns_none() -> None:
    store = _new_store()
    assert store.pop("ghost") is None


def test_get_field_with_default() -> None:
    store = _new_store()
    store.create("tok", phase="starting")
    assert store.get_field("tok", "phase") == "starting"
    assert store.get_field("tok", "nope", "fallback") == "fallback"
    assert store.get_field("ghost", "anything", "fallback") == "fallback"


def test_jobs_and_lock_are_exposed() -> None:
    """Some legacy paths (the batch worker's ``files_progress`` mutator,
    ``/health`` aggregate counts) read or take the lock directly. Removing
    these accessors would silently break them."""
    store = _new_store()
    store.create("tok", phase="x")
    assert "tok" in store.jobs
    with store.lock:
        store.jobs["tok"]["extra"] = "manual"
    assert store.snapshot("tok")["extra"] == "manual"


def test_concurrent_updates_do_not_lose_data() -> None:
    """Run 50 threads × 100 updates each; counter should land at 5000.

    The test isn't really proving lock-correctness (CPython's GIL would
    almost cover for missing locks here), but it does catch any regression
    that would obviously corrupt the dict — e.g. someone replacing the
    lock with a no-op."""
    store = _new_store()
    store.create("tok", count=0)

    def worker() -> None:
        for _ in range(100):
            with store.lock:
                store.jobs["tok"]["count"] += 1

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert store.snapshot("tok")["count"] == 5000
