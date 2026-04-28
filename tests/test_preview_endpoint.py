"""Tests for the ``/preview`` endpoint.

``/preview`` is the analysis endpoint the UI hits before any conversion —
it inspects the PDF, classifies it (``call_log`` / ``scanned`` /
``generic``), runs the safety scanner, and returns a recommendation.
The only assertions before this file were that ``/preview`` is mobile-
private; nothing exercised the actual classifier branches.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

import app
import core


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Loopback-equivalent client; the mobile-auth middleware lets it
    through to protected endpoints."""
    monkeypatch.setattr(core, "is_local_request", lambda req: True)
    return TestClient(app.app)


@pytest.fixture
def text_pdf(tmp_path: Path) -> Path:
    out = tmp_path / "text.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 80), "Birinci satır", fontsize=11, fontname="helv")
    page.insert_text((72, 110), "Ikinci satır", fontsize=11, fontname="helv")
    doc.save(str(out))
    doc.close()
    return out


def test_preview_rejects_non_pdf(client: TestClient) -> None:
    r = client.post(
        "/preview",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert r.status_code == 400


def test_preview_classifies_generic_text_pdf(client: TestClient, text_pdf: Path) -> None:
    r = client.post(
        "/preview",
        files={"file": ("text.pdf", text_pdf.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "generic"
    assert body["page_count"] == 1
    assert body["recommended_format"] == "word"
    # /preview always runs the safety scanner — confirm we got a verdict
    assert "safety" in body and "overall" in body["safety"]


def test_preview_classifies_scanned_pdf(monkeypatch: pytest.MonkeyPatch,
                                          client: TestClient,
                                          text_pdf: Path) -> None:
    """Force ``is_scanned_pdf`` to return True and confirm the JPG-recommend
    branch fires (we don't ship a real scanned-PDF fixture in the suite)."""
    from routers import convert as convert_router
    monkeypatch.setattr(convert_router, "is_scanned_pdf", lambda doc: True)

    r = client.post(
        "/preview",
        files={"file": ("scan.pdf", text_pdf.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "scanned"
    assert body["recommended_format"] == "jpg"
    assert body["scanned"] is True


def test_preview_classifies_call_log_pdf(monkeypatch: pytest.MonkeyPatch,
                                           client: TestClient,
                                           text_pdf: Path) -> None:
    """Stub ``is_call_log_pdf`` + ``parse_call_log`` so the call-log branch
    is exercised without a real call-log PDF fixture."""
    from routers import convert as convert_router

    fake_records = [
        {"#": 1, "Müşteri": "Ali Yılmaz", "Telefon": "5551112233",
         "Durum": "ended", "Tarih": "2024-05-01", "Süre": "00:42"},
        {"#": 2, "Müşteri": "Veli Demir", "Telefon": "5552223344",
         "Durum": "missed", "Tarih": "2024-05-02", "Süre": "00:00"},
    ]
    monkeypatch.setattr(convert_router, "is_scanned_pdf", lambda doc: False)
    monkeypatch.setattr(convert_router, "is_call_log_pdf", lambda doc: True)
    monkeypatch.setattr(convert_router, "parse_call_log", lambda doc: fake_records)

    r = client.post(
        "/preview",
        files={"file": ("calls.pdf", text_pdf.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "call_log"
    assert body["record_count"] == 2
    assert body["recommended_format"] == "excel"
    # First row preview includes the # column mapped onto "Kayıt No"
    assert body["rows"][0][1] == 1  # Kayıt No
    assert body["rows"][0][2] == "Ali Yılmaz"  # Müşteri
