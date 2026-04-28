"""Security-patch regression tests (Sprint 0).

Covers:
  - client_ip() XFF guard via HT_TRUSTED_PROXIES (audit log integrity)
  - url_to_pdf SSRF guard (private/loopback/link-local/reserved IP rejection)
  - safe_filename strips both / and \\
  - make_job_dir / assert_under_work symlink-escape defense
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import core


# ---------------------------------------------------------------------------
# client_ip — X-Forwarded-For honoured only from trusted proxies
# ---------------------------------------------------------------------------
def _fake_request(peer: str | None, xff: str | None = None):
    headers: dict[str, str] = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    return SimpleNamespace(
        client=SimpleNamespace(host=peer) if peer else None,
        headers=headers,
    )


def test_client_ip_ignores_xff_without_trusted_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HT_TRUSTED_PROXIES", raising=False)
    req = _fake_request(peer="192.168.1.5", xff="127.0.0.1")
    assert core.client_ip(req) == "192.168.1.5"


def test_client_ip_ignores_xff_when_peer_not_in_whitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HT_TRUSTED_PROXIES", "10.0.0.1, 10.0.0.2")
    req = _fake_request(peer="192.168.1.5", xff="127.0.0.1")
    assert core.client_ip(req) == "192.168.1.5"


def test_client_ip_honors_xff_from_trusted_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HT_TRUSTED_PROXIES", "10.0.0.1")
    req = _fake_request(peer="10.0.0.1", xff="8.8.8.8")
    assert core.client_ip(req) == "8.8.8.8"


def test_client_ip_handles_xff_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """First IP in the comma-separated chain is the original client."""
    monkeypatch.setenv("HT_TRUSTED_PROXIES", "10.0.0.1")
    req = _fake_request(peer="10.0.0.1", xff="8.8.8.8, 10.0.0.1")
    assert core.client_ip(req) == "8.8.8.8"


def test_client_ip_returns_question_mark_when_peer_missing() -> None:
    req = _fake_request(peer=None)
    assert core.client_ip(req) == "?"


# ---------------------------------------------------------------------------
# url_to_pdf — SSRF guard
# ---------------------------------------------------------------------------
def test_url_to_pdf_blocks_loopback(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="İç ağ|loopback"):
        core.url_to_pdf("http://127.0.0.1:8000/", tmp_path / "x.pdf")


def test_url_to_pdf_blocks_localhost(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="İç ağ|loopback"):
        core.url_to_pdf("http://localhost/", tmp_path / "x.pdf")


def test_url_to_pdf_blocks_metadata_ip(tmp_path: Path) -> None:
    """169.254.169.254 is the cloud-metadata service IP — must be refused."""
    with pytest.raises(ValueError, match="İç ağ|loopback"):
        core.url_to_pdf("http://169.254.169.254/latest/meta-data/", tmp_path / "x.pdf")


@pytest.mark.parametrize(
    "url",
    [
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
    ],
)
def test_url_to_pdf_blocks_rfc1918(tmp_path: Path, url: str) -> None:
    with pytest.raises(ValueError, match="İç ağ|loopback"):
        core.url_to_pdf(url, tmp_path / "x.pdf")


def test_url_to_pdf_rejects_non_http_scheme(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        core.url_to_pdf("file:///etc/passwd", tmp_path / "x.pdf")


def test_url_to_pdf_rejects_empty_url(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        core.url_to_pdf("", tmp_path / "x.pdf")


def test_assert_public_url_rejects_unspecified() -> None:
    """0.0.0.0 should also be rejected (is_unspecified)."""
    from urllib.parse import urlparse
    with pytest.raises(ValueError):
        core._assert_public_url(urlparse("http://0.0.0.0/"))


# ---------------------------------------------------------------------------
# safe_filename — / and \ are both stripped
# ---------------------------------------------------------------------------
def test_safe_filename_strips_forward_slash() -> None:
    assert "/" not in core.safe_filename("foo/bar.pdf")


def test_safe_filename_strips_backslash() -> None:
    assert "\\" not in core.safe_filename("foo\\bar.pdf")


def test_safe_filename_strips_traversal() -> None:
    out = core.safe_filename("../../../etc/passwd")
    assert "/" not in out
    assert "\\" not in out


def test_safe_filename_strips_reserved_chars() -> None:
    out = core.safe_filename('a:b*c?d"e<f>g|h')
    for ch in ':*?"<>|':
        assert ch not in out


def test_safe_filename_truncates_to_120() -> None:
    long_name = "a" * 500
    assert len(core.safe_filename(long_name)) <= 120


def test_safe_filename_returns_default_for_empty() -> None:
    assert core.safe_filename("") == "output"
    assert core.safe_filename("///") == "_"  # only separators -> single _


# ---------------------------------------------------------------------------
# make_job_dir / assert_under_work — symlink escape defense
# ---------------------------------------------------------------------------
def test_make_job_dir_creates_under_work() -> None:
    job_dir = core.make_job_dir()
    try:
        assert job_dir.exists()
        assert job_dir.is_dir()
        assert job_dir.resolve().is_relative_to(core.WORK_DIR.resolve())
    finally:
        job_dir.rmdir()


def test_make_job_dir_with_subkind() -> None:
    from uuid import uuid4
    tok = uuid4().hex
    job_dir = core.make_job_dir("convert", tok)
    try:
        assert job_dir.exists()
        assert job_dir.parent.name == "convert"
        assert job_dir.name == tok
    finally:
        job_dir.rmdir()


def test_assert_under_work_accepts_normal_path(tmp_path: Path) -> None:
    """Paths physically under WORK_DIR pass cleanly."""
    inside = core.WORK_DIR / "test_assert_inside"
    inside.mkdir(exist_ok=True)
    try:
        core.assert_under_work(inside)  # must not raise
    finally:
        inside.rmdir()


@pytest.mark.skipif(os.name == "nt", reason="Symlink creation needs admin on Windows")
def test_assert_under_work_rejects_symlink_escape(tmp_path: Path) -> None:
    """A symlink inside WORK_DIR pointing outside must be refused."""
    target = tmp_path / "outside"
    target.mkdir()
    link = core.WORK_DIR / "_test_escape_link"
    if link.exists() or link.is_symlink():
        link.unlink()
    try:
        link.symlink_to(target)
        with pytest.raises(HTTPException) as exc_info:
            core.assert_under_work(link)
        assert exc_info.value.status_code == 500
    finally:
        if link.is_symlink():
            link.unlink()


# ---------------------------------------------------------------------------
# defence-in-depth: zip arcname doesn't contain path separators
# ---------------------------------------------------------------------------
def test_safe_filename_pipeline_never_yields_path_sep() -> None:
    """Replaying the convert() endpoint's stem-handling for hostile filenames."""
    hostile = ["../foo.pdf", "..\\foo.pdf", "a/b/c.pdf", "a\\b\\c.pdf"]
    for filename in hostile:
        stem = Path(filename).stem
        # endpoint pattern: final_stem = safe_custom or _safe_filename(stem)
        final_stem = core.safe_filename(stem)
        assert "/" not in final_stem
        assert "\\" not in final_stem
        assert ".." not in final_stem or final_stem == "_"
