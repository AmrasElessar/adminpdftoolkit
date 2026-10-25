from __future__ import annotations

from fastapi.testclient import TestClient

from adminpdf.app import create_app
from adminpdf.config import Settings

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
    settings.pairing_key = "s3cret-key"
    with TestClient(create_app(settings), base_url="http://localhost", client=REMOTE) as c:
        assert c.get("/api/health").status_code == 401
        session = c.get("/api/session").json()
        assert session["paired"] is False
        c.headers["X-CSRF-Token"] = session["csrf"]
        assert c.post("/api/session/pair", json={"key": "wrong"}).status_code == 403
        assert c.post("/api/session/pair", json={"key": "s3cret-key"}).status_code == 200
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/session").json()["paired"] is True


def test_pairing_is_rate_limited(settings: Settings) -> None:
    settings.lan_enabled = True
    settings.pairing_key = "k"
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
