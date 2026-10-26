from __future__ import annotations

import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adminpdf.app import create_app
from adminpdf.config import Settings
from adminpdf.core.files import MissingFileError

from .conftest import LOCAL, Api, make_pdf

REMOTE = ("192.168.1.50", 40000)


def test_security_headers_present(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_unknown_host_is_rejected_dns_rebinding(settings: Settings) -> None:
    with TestClient(create_app(settings), base_url="http://evil.example", client=LOCAL) as c:
        assert c.get("/api/health").status_code == 400


def test_mutation_without_csrf_token_is_rejected(client: TestClient) -> None:
    r = client.put("/api/files", content=make_pdf(), headers={"X-Filename": "a.pdf"})
    assert r.status_code == 403


def test_csrf_token_must_match_cookie(client: TestClient) -> None:
    client.get("/api/session")
    r = client.put("/api/files", content=make_pdf(), headers={"X-Filename": "a.pdf", "X-CSRF-Token": "forged"})
    assert r.status_code == 403


def test_cross_origin_post_is_rejected_even_with_token(api: Api) -> None:
    r = api.c.put(
        "/api/files",
        content=make_pdf(),
        headers={"X-Filename": "a.pdf", "Origin": "http://localhost:9999"},
    )
    assert r.status_code == 403


def test_same_origin_post_is_accepted(api: Api) -> None:
    r = api.c.put("/api/files", content=make_pdf(), headers={"X-Filename": "a.pdf", "Origin": "http://localhost"})
    assert r.status_code == 201


def test_remote_client_blocked_when_lan_disabled(settings: Settings) -> None:
    with TestClient(create_app(settings), base_url="http://localhost", client=REMOTE) as c:
        assert c.get("/api/health").status_code == 403


def test_lan_pairing_flow(settings: Settings) -> None:
    settings.lan_enabled = True
    settings.pairing_key = "s3cret-key-long"
    with TestClient(create_app(settings), base_url="http://localhost", client=REMOTE) as c:
        assert c.get("/api/health").status_code == 401
        session = c.get("/api/session").json()
        assert session["paired"] is False
        c.headers["X-CSRF-Token"] = session["csrf"]
        assert c.post("/api/session/pair", json={"key": "wrong"}).status_code == 403
        assert c.post("/api/session/pair", json={"key": "s3cret-key-long"}).status_code == 200
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/session").json()["paired"] is True


def test_pairing_is_rate_limited(settings: Settings) -> None:
    settings.lan_enabled = True
    settings.pairing_key = "k" * 16
    remote = ("192.168.1.77", 40000)
    with TestClient(create_app(settings), base_url="http://localhost", client=remote) as c:
        c.headers["X-CSRF-Token"] = c.get("/api/session").json()["csrf"]
        codes = [c.post("/api/session/pair", json={"key": "nope"}).status_code for _ in range(7)]
        assert codes[:5] == [403] * 5
        assert codes[5:] == [429, 429]


def test_trusted_network_skips_pairing(settings: Settings) -> None:
    settings.trusted_networks = "172.16.0.0/12"
    with TestClient(create_app(settings), base_url="http://localhost", client=("172.17.0.1", 5000)) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/session").json()["paired"] is True
    with TestClient(create_app(settings), base_url="http://localhost", client=REMOTE) as c:
        assert c.get("/api/health").status_code == 403


# -- isolation between devices ----------------------------------------------------
def test_paired_devices_cannot_reach_each_others_files_or_jobs(settings: Settings) -> None:
    settings.lan_enabled = True
    settings.pairing_key = "pairing-key-0123"
    app = create_app(settings)
    with (
        TestClient(app, base_url="http://localhost", client=("192.168.1.10", 1)) as a,
        TestClient(app, base_url="http://localhost", client=("192.168.1.11", 1)) as b,
        TestClient(app, base_url="http://localhost", client=LOCAL) as local,
    ):
        for c in (a, b, local):
            c.headers["X-CSRF-Token"] = c.get("/api/session").json()["csrf"]
        for c in (a, b):
            assert c.post("/api/session/pair", json={"key": "pairing-key-0123"}).status_code == 200

        up = a.put("/api/files", content=make_pdf(1), headers={"X-Filename": "gizli.pdf"})
        assert up.status_code == 201
        fid = up.json()["id"]
        assert "owner" not in up.json()
        assert a.get(f"/api/files/{fid}").status_code == 200
        for other in (b, local):
            responses = [
                other.get(f"/api/files/{fid}"),
                other.get(f"/api/files/{fid}/meta"),
                other.delete(f"/api/files/{fid}"),
                other.post("/api/ops/info", json={"inputs": [{"id": fid}]}),
            ]
            assert [r.status_code for r in responses] == [404] * 4

        job = a.post("/api/ops/info", json={"inputs": [{"id": fid}]})
        assert job.status_code == 202
        jid = job.json()["id"]
        assert b.get(f"/api/jobs/{jid}").status_code == 404
        assert b.post(f"/api/jobs/{jid}/cancel").status_code == 404
        assert a.get(f"/api/jobs/{jid}").status_code == 200


def test_proxied_loopback_request_is_not_local(settings: Settings) -> None:
    # A reverse proxy on this machine must not make every LAN client "local".
    with TestClient(create_app(settings), base_url="http://localhost", client=LOCAL) as c:
        assert c.get("/api/health", headers={"X-Forwarded-For": "192.168.1.9"}).status_code == 403
        assert c.get("/api/health", headers={"Forwarded": "for=192.168.1.9"}).status_code == 403
        assert c.get("/api/health").status_code == 200


def test_weak_pairing_key_is_refused(settings: Settings) -> None:
    settings.lan_enabled = True
    settings.pairing_key = "change-me"
    with pytest.raises(RuntimeError, match="at least"):
        create_app(settings).build_middleware_stack()


def test_gateway_keyword(monkeypatch: pytest.MonkeyPatch) -> None:
    from adminpdf.core import security

    monkeypatch.setattr(security, "default_gateway", lambda: "172.17.0.1")
    assert [str(n) for n in security.parse_networks("gateway")] == ["172.17.0.1/32"]
    # LAN mode: every device pairs, the gateway is not trusted blindly.
    assert security.parse_networks("gateway", lan_enabled=True) == []


def test_pairing_global_limit_defeats_address_rotation() -> None:
    from adminpdf.core.security import SessionRegistry

    reg = SessionRegistry()
    results = [reg.allow_attempt(f"2001:db8::{i:x}") for i in range(40)]
    assert results[: SessionRegistry.PAIR_MAX_GLOBAL] == [True] * SessionRegistry.PAIR_MAX_GLOBAL
    assert not any(results[SessionRegistry.PAIR_MAX_GLOBAL :])


def test_sessions_expire(monkeypatch: pytest.MonkeyPatch) -> None:
    from adminpdf.core import security

    reg = security.SessionRegistry()
    sid = reg.create()
    assert reg.valid(sid)
    later = security.time.monotonic() + security.SESSION_TTL_SECONDS + 1
    monkeypatch.setattr(security.time, "monotonic", lambda: later)
    assert not reg.valid(sid)


def test_api_responses_are_not_cached(api: Api) -> None:
    f = api.upload(make_pdf(1))
    assert api.c.get(f"/api/files/{f['id']}").headers["cache-control"] == "no-store"
    assert api.c.get("/api/session").headers["cache-control"] == "no-store"


def test_api_docs_off_by_default(client: TestClient) -> None:
    assert client.get("/api/openapi.json").status_code == 404
    assert client.get("/api/docs").status_code == 404


def test_storage_cap(settings: Settings) -> None:
    settings.max_storage_mb = 1
    with TestClient(create_app(settings), base_url="http://localhost", client=LOCAL) as c:
        api = Api(c)
        api.upload(b"%PDF-1.4\n" + b"0" * 700_000, "a.pdf")
        r = c.put("/api/files", content=b"%PDF-1.4\n" + b"0" * 700_000, headers={"X-Filename": "b.pdf"})
        assert r.status_code == 507


def test_pending_job_cap(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    from adminpdf.jobs import engine

    monkeypatch.setattr(engine, "MAX_PENDING_PER_OWNER", 0)
    f = api.upload(make_pdf(1))
    assert api.start("info", [f["id"]]).status_code == 429


def test_sweep_keeps_files_of_running_jobs(tmp_path: Path) -> None:
    import asyncio

    from adminpdf.core.files import FileStore

    store = FileStore(tmp_path, max_bytes=1000, ttl_seconds=1)

    async def chunks() -> AsyncIterator[bytes]:
        yield b"%PDF-1.4 x"

    a = asyncio.run(store.save_stream("a.pdf", chunks(), owner="local"))
    b = asyncio.run(store.save_stream("b.pdf", chunks(), owner="local"))
    assert store.sweep(now=time.time() + 10, keep=frozenset({a.id})) == 1
    assert store.get(a.id, owner="local")
    with pytest.raises(MissingFileError):
        store.get(b.id, owner="local")


# -- local network only -------------------------------------------------------------
@pytest.mark.parametrize("addr", ["8.8.8.8", "100.64.1.2", "2001:4860::8888", "::ffff:8.8.8.8", "testclient"])
def test_public_addresses_are_never_served(settings: Settings, addr: str) -> None:
    settings.lan_enabled = True
    settings.pairing_key = "pairing-key-0123"
    with TestClient(create_app(settings), base_url="http://localhost", client=(addr, 1)) as c:
        assert c.get("/api/session").status_code == 403
        assert c.get("/api/session/ca.crt").status_code == 403
        assert c.get("/").status_code == 403


@pytest.mark.parametrize("addr", ["192.168.1.5", "10.2.3.4", "172.20.0.9", "169.254.10.1", "fe80::1", "fd00::5"])
def test_local_network_addresses_may_pair(settings: Settings, addr: str) -> None:
    settings.lan_enabled = True
    settings.pairing_key = "pairing-key-0123"
    with TestClient(create_app(settings), base_url="http://localhost", client=(addr, 1)) as c:
        assert c.get("/api/session").status_code == 200
        assert c.get("/api/health").status_code == 401


def test_trusted_networks_must_be_local(settings: Settings) -> None:
    settings.trusted_networks = "0.0.0.0/0"
    with pytest.raises(ValueError, match="local-network"):
        create_app(settings).build_middleware_stack()


def test_ca_download_and_device_links(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from adminpdf.core import security, tls

    monkeypatch.setattr(security, "local_addresses", lambda: {"192.168.1.20", "127.0.0.1"})
    tls.ensure(settings.tls_dir)
    settings.lan_enabled = True
    settings.pairing_key = "pairing-key-0123"
    app = create_app(settings)
    with TestClient(app, base_url="http://localhost", client=("192.168.1.30", 1)) as phone:
        r = phone.get("/api/session/ca.crt")  # before pairing: needed to trust the server
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/x-x509-ca-cert"
        assert b"BEGIN CERTIFICATE" in r.content and b"PRIVATE" not in r.content
        assert phone.get("/api/session/devices").status_code == 401  # pairing link stays on the server PC
    with TestClient(app, base_url="http://localhost", client=LOCAL) as pc:
        info = pc.get("/api/session/devices").json()
        assert info["urls"] == ["https://192.168.1.20:8000/#pair=pairing-key-0123"]
        assert len(info["fingerprint"]) == 95
        qr = pc.get("/api/session/devices/qr.svg?i=0")
        assert qr.status_code == 200 and qr.headers["content-type"].startswith("image/svg+xml")
        assert b"<script" not in qr.content
        assert pc.get("/api/session/devices/qr.svg?i=5").status_code == 404


def test_hsts_only_for_dns_names(settings: Settings) -> None:
    settings.allowed_hosts = "pdf.ofis.lan"
    app = create_app(settings)
    with TestClient(app, base_url="https://pdf.ofis.lan", client=LOCAL) as c:
        assert c.get("/api/health").headers["strict-transport-security"] == "max-age=31536000"
    with TestClient(app, base_url="https://localhost", client=LOCAL) as c:
        assert "strict-transport-security" not in c.get("/api/health").headers
