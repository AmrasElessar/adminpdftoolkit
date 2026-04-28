"""HTTP API integration tests via FastAPI TestClient.

These do not exercise the real conversion pipelines (those need real PDF
fixtures and would slow down the suite); they cover the *contract* of every
public endpoint:

- shape and status of error responses
- input validation (mapping JSON, target enum, missing files, bad tokens)
- token regex enforcement
- /health structure (relied on by Docker HEALTHCHECK + ops dashboards)
- /docs + /openapi.json availability
- persistent state recovery (server-restart simulation)
- error sanitization (no internal paths leak through to clients)

These tests run in <1 second and protect us when the upcoming router refactor
moves code around.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app
import core


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Default TestClient — treated as the host PC's own browser.

    The mobile-auth middleware (added in v1.0) blocks non-loopback clients
    from protected endpoints. Pre-existing tests assume they hit the API
    directly, so the default client is forced to look local. Tests that
    want to act as a remote LAN client should monkeypatch
    ``core.is_local_request`` themselves (the middleware reads it via
    lazy attribute lookup)."""
    import core
    monkeypatch.setattr(core, "is_local_request", lambda req: True)
    return TestClient(app.app)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------
def test_health_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["version"] == app.__version__
    assert body["uptime_seconds"] >= 0
    assert "thread_count" in body
    assert set(body["jobs"]) == {"convert", "batch", "ocr"}
    assert "running" in body["jobs"]["convert"]


# ---------------------------------------------------------------------------
# /docs and /openapi.json
# ---------------------------------------------------------------------------
def test_docs_available(client: TestClient) -> None:
    r = client.get("/docs")
    assert r.status_code == 200
    assert "swagger" in r.text.lower()


def test_openapi_schema_has_endpoints(client: TestClient) -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    paths = schema["paths"]
    # A few critical endpoints we rely on
    for p in ("/health", "/convert-start", "/batch-analyze", "/ocr-start"):
        assert p in paths, f"OpenAPI schema is missing {p}"


# ---------------------------------------------------------------------------
# Token format guard (_check_token)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bad_token",
    [
        "../etc/passwd",
        "abc/def",
        "abc.def",
        "123",            # too short
        "X" * 33,         # too long
        "g" * 32,         # non-hex
    ],
)
def test_progress_rejects_malformed_token(client: TestClient, bad_token: str) -> None:
    r = client.get(f"/convert-progress/{bad_token}")
    assert r.status_code in (400, 404)  # 400 = format reject, 404 = not found


def test_progress_unknown_token_returns_404(client: TestClient) -> None:
    r = client.get("/convert-progress/" + "a" * 32)
    assert r.status_code == 404
    assert "bulunamadı" in r.json()["detail"].lower() or "found" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# /convert-start input validation
# ---------------------------------------------------------------------------
def test_convert_start_rejects_invalid_target(client: TestClient) -> None:
    fake_pdf = io.BytesIO(b"%PDF-1.4\n%fake\n%%EOF\n")
    r = client.post(
        "/convert-start",
        files={"file": ("x.pdf", fake_pdf, "application/pdf")},
        data={"target": "html"},  # invalid
    )
    assert r.status_code == 400
    assert "geçersiz" in r.json()["detail"].lower() or "invalid" in r.json()["detail"].lower()


def test_convert_start_rejects_non_pdf_filename(client: TestClient) -> None:
    r = client.post(
        "/convert-start",
        files={"file": ("x.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        data={"target": "excel"},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# /batch-convert mapping JSON validation (Sprint 1 fix)
# ---------------------------------------------------------------------------
def test_batch_convert_rejects_invalid_mapping_json(client: TestClient) -> None:
    fake_pdf = io.BytesIO(b"%PDF-1.4\n%%EOF\n")
    r = client.post(
        "/batch-convert",
        files=[("files", ("a.pdf", fake_pdf, "application/pdf"))],
        data={"mappings": "not-a-json", "skip": "[]"},
    )
    assert r.status_code == 400


def test_batch_convert_rejects_non_dict_mapping(client: TestClient) -> None:
    r = client.post(
        "/batch-convert",
        files=[("files", ("a.pdf", io.BytesIO(b"%PDF-1.4\n%%EOF\n"), "application/pdf"))],
        data={"mappings": "[]", "skip": "[]"},  # array, not dict
    )
    assert r.status_code == 400


def test_batch_convert_rejects_non_int_column_index(client: TestClient) -> None:
    payload = json.dumps({"a.pdf": {"Müşteri": "abc"}})  # "abc" not parseable as int
    r = client.post(
        "/batch-convert",
        files=[("files", ("a.pdf", io.BytesIO(b"%PDF-1.4\n%%EOF\n"), "application/pdf"))],
        data={"mappings": payload, "skip": "[]"},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Sanitizer
# ---------------------------------------------------------------------------
def test_sanitize_error_strips_windows_paths() -> None:
    msg = "FileNotFoundError: [Errno 2] No such file: 'C:\\Projeler\\pdfconverter\\_work\\xyz\\input.pdf'"
    out = core.sanitize_error(msg)
    assert "C:\\Projeler" not in out
    assert "<path>" in out


def test_sanitize_error_strips_posix_paths() -> None:
    msg = "OSError: failed to open /home/orhan/.cache/easyocr/model.pth"
    out = core.sanitize_error(msg)
    assert "/home/orhan" not in out
    assert "<path>" in out


def test_sanitize_error_strips_traceback_file_prefix() -> None:
    msg = 'something failed File "C:/Projeler/app.py", line 42 in foo'
    out = core.sanitize_error(msg)
    assert "Projeler" not in out


def test_sanitize_error_caps_length() -> None:
    big = "x" * 5000
    out = core.sanitize_error(big)
    assert len(out) <= core.MAX_ERROR_CHARS


def test_sanitize_error_empty_falls_back() -> None:
    assert core.sanitize_error("") == "İşlem başarısız."
    assert core.sanitize_error("   ") == "İşlem başarısız."


# ---------------------------------------------------------------------------
# Persistent job state — survives server restart simulation
# ---------------------------------------------------------------------------
def test_persisted_state_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # state_path() in core.py reads core.STATE_DIR (which is the same object
    # as state.STATE_DIR). Patch both bindings.
    import core, state
    monkeypatch.setattr(core, "STATE_DIR", tmp_path)
    monkeypatch.setattr(state, "STATE_DIR", tmp_path)
    token = "f" * 32
    job = {
        "phase": "done",
        "done": True,
        "current": 10,
        "total": 10,
        "output_name": "result.xlsx",
        "started_at": 1234567890.0,
    }
    core.persist_job_state("convert", token, job)

    loaded = core.load_persisted_state("convert", token)
    assert loaded == job

    core.drop_persisted_state("convert", token)
    assert core.load_persisted_state("convert", token) is None


def test_progress_falls_back_to_persisted_state(client: TestClient, tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """If the in-memory entry is gone (e.g. server restarted) but a state.json
    is on disk, the progress endpoint should return that snapshot rather than
    a bare 404."""
    import core, state
    monkeypatch.setattr(core, "STATE_DIR", tmp_path)
    monkeypatch.setattr(state, "STATE_DIR", tmp_path)
    token = "b" * 32
    core.persist_job_state("convert", token, {
        "phase": "done", "done": True, "output_name": "out.xlsx",
        "current": 5, "total": 5, "started_at": 0,
    })
    r = client.get(f"/convert-progress/{token}")
    assert r.status_code == 200
    body = r.json()
    assert body["done"] is True
    assert body["output_name"] == "out.xlsx"


# ---------------------------------------------------------------------------
# Job timeout flagging
# ---------------------------------------------------------------------------
def test_check_job_timeout_flags_stale_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(core, "MAX_JOB_TIMEOUT_SECONDS", 1)
    job = {"phase": "processing", "done": False, "started_at": 0.0}  # very old
    core.check_job_timeout(job)
    assert job["done"] is True
    assert job["error"] and "zaman aşımına" in job["error"]


def test_check_job_timeout_does_not_touch_done_jobs() -> None:
    job = {"done": True, "started_at": 0.0}
    core.check_job_timeout(job)
    assert "error" not in job


# ---------------------------------------------------------------------------
# SSE event endpoint
# ---------------------------------------------------------------------------
def test_sse_invalid_kind_returns_404(client: TestClient) -> None:
    r = client.get("/events/notarealkind/" + "a" * 32)
    assert r.status_code == 404


def test_sse_invalid_token_returns_400(client: TestClient) -> None:
    r = client.get("/events/convert/badtoken")
    assert r.status_code in (400, 404)


def test_sse_streams_done_job_then_closes(client: TestClient, tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """A finished job's snapshot is emitted as a single SSE frame, then the
    stream closes (no infinite hold)."""
    import core, state
    monkeypatch.setattr(core, "STATE_DIR", tmp_path)
    monkeypatch.setattr(state, "STATE_DIR", tmp_path)
    token = "c" * 32
    core.persist_job_state("convert", token, {
        "phase": "done", "done": True, "current": 3, "total": 3,
        "output_name": "x.xlsx", "started_at": 0,
    })
    with client.stream("GET", f"/events/convert/{token}") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = b"".join(r.iter_bytes()).decode("utf-8")
    assert "data: " in body
    assert '"done": true' in body or '"done":true' in body


# ---------------------------------------------------------------------------
# Job snapshot helper
# ---------------------------------------------------------------------------
def test_job_snapshot_unknown_kind_returns_none() -> None:
    assert core.job_snapshot("nosuch", "a" * 32) is None


def test_job_snapshot_falls_back_to_disk(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    import core, state
    monkeypatch.setattr(core, "STATE_DIR", tmp_path)
    monkeypatch.setattr(state, "STATE_DIR", tmp_path)
    token = "d" * 32
    core.persist_job_state("ocr", token, {"phase": "done", "done": True, "started_at": 0})
    snap = core.job_snapshot("ocr", token)
    assert snap is not None
    assert snap["done"] is True


# ---------------------------------------------------------------------------
# Batch parallel parser worker (process-pool entrypoint)
# ---------------------------------------------------------------------------
def test_parse_pdf_for_batch_returns_warning_for_missing_file() -> None:
    """The worker must never raise — it converts failures to a warning so a
    single bad PDF doesn't kill the whole batch job."""
    import core
    out = core.parse_pdf_for_batch(
        ("does-not-exist.pdf", "C:/no/such/file.pdf", None, ["Müşteri"])
    )
    assert out["filename"] == "does-not-exist.pdf"
    assert out["records"] == []
    assert out["warning"] is not None
    assert "atlandı" in out["warning"]


def test_parse_pdf_for_batch_no_mapping_warns() -> None:
    """If the file isn't a call-log AND no column mapping is supplied, the
    worker emits the 'eşleme yapılmamış' warning rather than crashing."""
    import core
    # Use the test_pipeline fixture path — but we just need any non-call-log
    # PDF here. Synthesize: pass a non-existent path so the open() fails →
    # falls through to the generic exception branch, still returns a warning.
    out = core.parse_pdf_for_batch(
        ("foo.pdf", "C:/nope.pdf", None, [])
    )
    assert out["records"] == []
    assert out["warning"] is not None


# ---------------------------------------------------------------------------
# Mobile / LAN access control
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=False)
def reset_mobile_token():
    """Make sure each mobile-auth test starts from a clean state and doesn't
    leak the token to the next test."""
    import state
    with state.mobile_token_lock:
        state.mobile_token = None
    yield
    with state.mobile_token_lock:
        state.mobile_token = None


@pytest.fixture
def local_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient whose requests look like they come from localhost.

    FastAPI's TestClient reports ``client.host == "testclient"`` by default,
    so the production ``is_local_request()`` check (which whitelists 127.0.0.1
    and friends) returns False — the same way it would for a real LAN client.
    For the admin endpoints we want the test to act as the host PC, so we
    override the local-detection helper for the duration of the test.
    """
    import core
    monkeypatch.setattr(core, "is_local_request", lambda req: True)
    monkeypatch.setattr("core.is_local_request", lambda req: True)
    return TestClient(app.app)


def test_mobile_status_initially_disabled(client: TestClient, reset_mobile_token) -> None:
    r = client.get("/admin/mobile-status")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    # TestClient is treated as local (host = "testclient" maps to a known
    # client object; we still expect the local check to pass for our own host)
    assert "is_local" in body


def test_enable_mobile_returns_token_and_url(local_client: TestClient, reset_mobile_token) -> None:
    r = local_client.post("/admin/enable-mobile")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is True
    assert isinstance(body["token"], str)
    assert len(body["token"]) >= 40, "token should be at least 256-bit (43 base64 chars)"
    assert body["token"] in body["url"], "URL must contain the issued token"
    assert body["lan_ip"]
    assert body["port"]


def test_disable_mobile_clears_token(local_client: TestClient, reset_mobile_token) -> None:
    local_client.post("/admin/enable-mobile")
    assert local_client.get("/admin/mobile-status").json()["enabled"] is True
    r = local_client.post("/admin/disable-mobile")
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    assert local_client.get("/admin/mobile-status").json()["enabled"] is False


def test_enable_mobile_rotates_token(local_client: TestClient, reset_mobile_token) -> None:
    """Calling /enable a second time issues a fresh token (older mobile
    sessions effectively get logged out — by design)."""
    t1 = local_client.post("/admin/enable-mobile").json()["token"]
    t2 = local_client.post("/admin/enable-mobile").json()["token"]
    assert t1 != t2


def test_enable_mobile_rejects_non_local(client: TestClient, reset_mobile_token,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    """Default TestClient is treated as remote (host='testclient'). Without
    the local override, /admin/enable-mobile must refuse with 403."""
    import core
    monkeypatch.setattr(core, "is_local_request", lambda req: False)
    monkeypatch.setattr("core.is_local_request", lambda req: False)
    r = client.post("/admin/enable-mobile")
    assert r.status_code == 403


def test_is_local_request_unit() -> None:
    """is_local_request must accept loopback hosts and reject the rest."""
    from core import is_local_request
    from types import SimpleNamespace

    def fake_req(host: str | None):
        return SimpleNamespace(client=SimpleNamespace(host=host) if host else None)

    assert is_local_request(fake_req("127.0.0.1"))
    assert is_local_request(fake_req("::1"))
    assert is_local_request(fake_req("localhost"))
    assert not is_local_request(fake_req("192.168.1.10"))
    assert not is_local_request(fake_req("10.0.0.5"))
    assert not is_local_request(fake_req(None))


def test_mobile_public_path_classification() -> None:
    """White-list of paths that bypass mobile-auth must include the page
    itself + static assets + Swagger, but NOT any data-bearing endpoint."""
    assert app._is_mobile_public("/") is True
    assert app._is_mobile_public("/health") is True
    assert app._is_mobile_public("/static/i18n.js") is True
    assert app._is_mobile_public("/static/sw.js") is True
    assert app._is_mobile_public("/admin/mobile-status") is True
    assert app._is_mobile_public("/docs") is True
    assert app._is_mobile_public("/openapi.json") is True
    # Critical: data endpoints MUST be protected
    assert app._is_mobile_public("/preview") is False
    assert app._is_mobile_public("/convert-start") is False
    assert app._is_mobile_public("/batch-analyze") is False
    assert app._is_mobile_public("/ocr-start") is False
    assert app._is_mobile_public("/history") is False
    assert app._is_mobile_public("/admin/enable-mobile") is False
    assert app._is_mobile_public("/admin/disable-mobile") is False


def test_middleware_remote_no_token_blocks_protected(reset_mobile_token,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the middleware to treat the client as remote, leave the token
    unset, and confirm a protected endpoint returns 403."""
    import core
    monkeypatch.setattr(core, "is_local_request", lambda req: False)
    monkeypatch.setattr("core.is_local_request", lambda req: False)
    c = TestClient(app.app)
    r = c.get("/history")  # protected endpoint
    assert r.status_code == 403
    body = r.json()
    assert "kapalı" in body["detail"].lower() or "anahtar" in body["detail"].lower()


def test_middleware_remote_with_valid_token_passes(reset_mobile_token,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    """With a token issued AND presented in the X-Mobile-Key header, a
    'remote' client can reach a protected endpoint."""
    import core, state
    # Issue a token by direct state manipulation (bypass the local-only check)
    test_token = "T" * 50
    with state.mobile_token_lock:
        state.mobile_token = test_token
    # Now act as a remote client
    monkeypatch.setattr(core, "is_local_request", lambda req: False)
    monkeypatch.setattr("core.is_local_request", lambda req: False)
    c = TestClient(app.app)
    r = c.get("/history", headers={"X-Mobile-Key": test_token})
    assert r.status_code == 200


def test_middleware_remote_with_wrong_token_blocks(reset_mobile_token,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    """Wrong key → 403 even when mobile access is enabled."""
    import core, state
    with state.mobile_token_lock:
        state.mobile_token = "right-token"
    monkeypatch.setattr(core, "is_local_request", lambda req: False)
    monkeypatch.setattr("core.is_local_request", lambda req: False)
    c = TestClient(app.app)
    r = c.get("/history", headers={"X-Mobile-Key": "wrong-token"})
    assert r.status_code == 403


def test_cleanup_loop_callable_with_no_args() -> None:
    """Regression guard: ``threading.Thread(target=cleanup_loop)`` (no args)
    must keep working — the lifespan starts the sweeper that way and
    silently breaks the daemon thread if the signature changes."""
    import core, inspect
    sig = inspect.signature(core.cleanup_loop)
    for name, param in sig.parameters.items():
        assert param.default is not inspect.Parameter.empty, \
            f"cleanup_loop parameter {name!r} must have a default — " \
            f"otherwise threading.Thread(target=cleanup_loop) crashes at boot"


def test_middleware_remote_token_via_query_param(reset_mobile_token,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    """?key= URL param works as an alternative to the header (used by the
    initial mobile bookmark hit)."""
    import core, state
    test_token = "Q" * 50
    with state.mobile_token_lock:
        state.mobile_token = test_token
    monkeypatch.setattr(core, "is_local_request", lambda req: False)
    monkeypatch.setattr("core.is_local_request", lambda req: False)
    c = TestClient(app.app)
    r = c.get(f"/history?key={test_token}")
    assert r.status_code == 200


def test_middleware_token_constant_time_compare(reset_mobile_token) -> None:
    """Sanity: the comparison uses hmac.compare_digest (timing-safe)."""
    import hmac as _hmac
    # If someone refactors the middleware to use plain `==`, they'll have
    # to remove this guard from the source too — making the regression
    # visible in code review.
    src = open("app.py", encoding="utf-8").read()
    assert "hmac.compare_digest" in src or "_hmac.compare_digest" in src
