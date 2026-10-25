"""Job engine: isolation, timeout, cancel, crash handling."""

from __future__ import annotations

import sys
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from adminpdf.app import create_app
from adminpdf.config import Settings
from adminpdf.ops.base import REGISTRY, Context, Operation, register

from .conftest import LOCAL, Api, make_pdf


class _Sleep(Operation):
    name = "_test_sleep"
    category = "test"
    title_tr = title_en = "sleep"

    def run(self, ctx: Context, params: Any) -> None:
        time.sleep(30)


class _Crash(Operation):
    name = "_test_crash"
    category = "test"
    title_tr = title_en = "crash"

    def run(self, ctx: Context, params: Any) -> None:
        import os

        os._exit(3)


class _Boom(Operation):
    name = "_test_boom"
    category = "test"
    title_tr = title_en = "boom"

    def run(self, ctx: Context, params: Any) -> None:
        raise RuntimeError("/secret/internal/path exploded")


# The worker re-imports the registry in a fresh process, so test operations
# must be importable there too: register them from a module the worker loads.
for _op in (_Sleep, _Crash, _Boom):
    if _op.name not in REGISTRY:
        register(_op)


# These tests fork so the child inherits the test-only operations above.
needs_fork = pytest.mark.skipif(sys.platform != "linux", reason="fork start method is Linux-only here")


def _api(settings: Settings) -> tuple[TestClient, Api]:
    c = TestClient(create_app(settings), base_url="http://localhost", client=LOCAL)
    c.__enter__()
    return c, Api(c)


def test_internal_errors_are_not_leaked() -> None:
    # Run in-process via the worker entry point to keep the test registry.
    import multiprocessing as mp

    from adminpdf.jobs import worker

    parent, child = mp.Pipe(duplex=False)
    worker.run(child, "_test_boom", {}, [], "/tmp", 0)
    kind, payload = parent.recv()
    assert kind == "error"
    assert "secret" not in str(payload)


@needs_fork
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_crash_in_worker_is_reported(tmp_path: Any) -> None:
    import multiprocessing as mp

    from adminpdf.jobs import worker

    ctx = mp.get_context("fork")  # fork keeps the test-only registry
    parent, child = ctx.Pipe(duplex=False)
    p = ctx.Process(target=worker.run, args=(child, "_test_crash", {}, [], str(tmp_path), 0))
    p.start()
    child.close()
    p.join(10)
    assert p.exitcode == 3
    try:
        parent.recv()
        raise AssertionError("expected EOF")
    except EOFError:
        pass


@needs_fork
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_timeout_and_cancel_terminate_worker(settings: Settings) -> None:
    import multiprocessing as mp

    settings.job_timeout_seconds = 5
    c, api = _api(settings)
    # Fork instead of spawn so the worker inherits the test-only operations.
    c.app.state.engine._mp = mp.get_context("fork")  # type: ignore[attr-defined]
    try:
        f = api.upload(make_pdf(1))
        started = time.time()
        job = api.run("_test_sleep", [f["id"]])
        assert job["status"] == "failed"
        assert job["error"]["en"] == "The operation timed out."
        assert time.time() - started < 15

        r = api.start("_test_sleep", [f["id"]])
        jid = r.json()["id"]
        time.sleep(0.5)
        api.c.post(f"/api/jobs/{jid}/cancel")
        assert api.wait(jid)["status"] == "cancelled"

        crash = api.run("_test_crash", [f["id"]])
        assert crash["status"] == "failed"
        assert "unexpectedly" in crash["error"]["en"]
    finally:
        c.__exit__(None, None, None)


def test_sse_stream_reports_progress_until_done(api: Api) -> None:
    f = api.upload(make_pdf(3))
    jid = api.start("split", [f["id"]], {"mode": "each"}).json()["id"]
    events = []
    with api.c.stream("GET", f"/api/jobs/{jid}/events") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            if line.startswith("data: "):
                events.append(line)
    assert '"status": "done"' in events[-1]
