"""Tests for the Section C (light) AI helpers added in v1.3.

Covers ``detect_blank_pages``, ``remove_blank_pages``, ``detect_signatures``
and ``classify_pdf`` plus their endpoints. No model downloads — these are
heuristic / pattern-based, so the suite stays fast and offline.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

import app
import core


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def blank_mixed_pdf(tmp_path: Path) -> Path:
    """3 pages: page 1 with text, page 2 blank, page 3 with text."""
    out = tmp_path / "mixed.pdf"
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 100), "Bu sayfada metin var.", fontsize=12, fontname="helv")
    doc.new_page()  # blank
    p3 = doc.new_page()
    p3.insert_text((72, 100), "Üçüncü sayfa.", fontsize=12, fontname="helv")
    doc.save(str(out))
    doc.close()
    return out


@pytest.fixture
def all_blank_pdf(tmp_path: Path) -> Path:
    out = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.save(str(out))
    doc.close()
    return out


@pytest.fixture
def invoice_pdf(tmp_path: Path) -> Path:
    out = tmp_path / "invoice.pdf"
    doc = fitz.open()
    page = doc.new_page()
    text = (
        "FATURA\n"
        "Fatura No: 2026-001\n"
        "Fatura Tarihi: 27.04.2026\n"
        "KDV %20\n"
        "Toplam Tutar: 1.500,00 TL\n"
        "Vergi No: 1234567890\n"
    )
    y = 80
    for line in text.splitlines():
        page.insert_text((72, y), line, fontsize=12, fontname="helv")
        y += 18
    doc.save(str(out))
    doc.close()
    return out


@pytest.fixture
def contract_pdf(tmp_path: Path) -> Path:
    out = tmp_path / "contract.pdf"
    doc = fitz.open()
    page = doc.new_page()
    text = (
        "SÖZLEŞME\n"
        "Taraflar arasında akdedilen iş bu sözleşme...\n"
        "Madde 1: Konu\n"
        "Madde 2: Yürürlük\n"
        "Hüküm ve koşullar imza tarafından kabul edilir.\n"
    )
    y = 80
    for line in text.splitlines():
        page.insert_text((72, y), line, fontsize=12, fontname="helv")
        y += 18
    doc.save(str(out))
    doc.close()
    return out


@pytest.fixture
def signed_pdf(tmp_path: Path) -> Path:
    """A PDF with a signature widget (unsigned)."""
    out = tmp_path / "sign.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "İmza alanı aşağıdadır:", fontsize=12, fontname="helv")
    widget = fitz.Widget()
    widget.field_name = "signature1"
    widget.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE
    widget.rect = fitz.Rect(72, 200, 300, 250)
    page.add_widget(widget)
    doc.save(str(out))
    doc.close()
    return out


@pytest.fixture
def plain_pdf(tmp_path: Path) -> Path:
    out = tmp_path / "plain.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Düz metin.", fontsize=12, fontname="helv")
    doc.save(str(out))
    doc.close()
    return out


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(core, "is_local_request", lambda req: True)
    monkeypatch.setattr("core.is_local_request", lambda req: True)
    return TestClient(app.app)


# ---------------------------------------------------------------------------
# detect_blank_pages
# ---------------------------------------------------------------------------
def test_detect_blank_finds_middle_blank(blank_mixed_pdf: Path) -> None:
    blanks = core.detect_blank_pages(blank_mixed_pdf)
    assert blanks == [2]


def test_detect_blank_all_blank(all_blank_pdf: Path) -> None:
    blanks = core.detect_blank_pages(all_blank_pdf)
    assert blanks == [1, 2]


def test_detect_blank_threshold_validation(plain_pdf: Path) -> None:
    with pytest.raises(ValueError):
        core.detect_blank_pages(plain_pdf, threshold=0.1)


# ---------------------------------------------------------------------------
# remove_blank_pages
# ---------------------------------------------------------------------------
def test_remove_blank_drops_middle(blank_mixed_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    kept, removed = core.remove_blank_pages(blank_mixed_pdf, out)
    assert kept == 2
    assert removed == 1
    with fitz.open(str(out)) as d:
        assert d.page_count == 2


def test_remove_blank_no_blanks_keeps_all(plain_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    kept, removed = core.remove_blank_pages(plain_pdf, out)
    assert removed == 0
    assert kept == 1


def test_remove_blank_all_blank_raises(all_blank_pdf: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        core.remove_blank_pages(all_blank_pdf, tmp_path / "x.pdf")


# ---------------------------------------------------------------------------
# detect_signatures
# ---------------------------------------------------------------------------
def test_detect_signatures_unsigned_pdf(plain_pdf: Path) -> None:
    out = core.detect_signatures(plain_pdf)
    assert out["is_signed"] is False
    assert out["field_count"] == 0
    assert out["digital_signature"] is False


def test_detect_signatures_with_field(signed_pdf: Path) -> None:
    out = core.detect_signatures(signed_pdf)
    assert out["field_count"] == 1
    assert len(out["fields"]) == 1
    assert out["fields"][0]["page"] == 1
    assert out["fields"][0]["name"] == "signature1"


# ---------------------------------------------------------------------------
# classify_pdf
# ---------------------------------------------------------------------------
def test_classify_invoice(invoice_pdf: Path) -> None:
    out = core.classify_pdf(invoice_pdf)
    assert out["category"] == "fatura"
    assert out["score"] >= 3
    assert out["confidence"] > 0


def test_classify_contract(contract_pdf: Path) -> None:
    out = core.classify_pdf(contract_pdf)
    assert out["category"] == "sözleşme"


def test_classify_no_keywords_returns_diger(plain_pdf: Path) -> None:
    out = core.classify_pdf(plain_pdf)
    assert out["category"] == "diğer"
    assert out["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Endpoint smoke tests
# ---------------------------------------------------------------------------
def test_endpoint_detect_blank(client: TestClient, blank_mixed_pdf: Path) -> None:
    r = client.post(
        "/pdf/detect-blank",
        files={"file": ("m.pdf", blank_mixed_pdf.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_pages"] == 3
    assert body["blank_pages"] == [2]
    assert body["blank_count"] == 1


def test_endpoint_remove_blank(client: TestClient, blank_mixed_pdf: Path) -> None:
    r = client.post(
        "/pdf/remove-blank",
        files={"file": ("m.pdf", blank_mixed_pdf.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers.get("X-Pages-Kept") == "2"
    assert r.headers.get("X-Pages-Removed") == "1"
    with fitz.open(stream=r.content, filetype="pdf") as d:
        assert d.page_count == 2


def test_endpoint_detect_signatures(client: TestClient, signed_pdf: Path) -> None:
    r = client.post(
        "/pdf/detect-signatures",
        files={"file": ("s.pdf", signed_pdf.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["field_count"] == 1
    assert "fields" in body


def test_endpoint_classify(client: TestClient, invoice_pdf: Path) -> None:
    r = client.post(
        "/pdf/classify",
        files={"file": ("i.pdf", invoice_pdf.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["category"] == "fatura"


def test_endpoint_classify_max_pages_validation(client: TestClient, invoice_pdf: Path) -> None:
    r = client.post(
        "/pdf/classify",
        files={"file": ("i.pdf", invoice_pdf.read_bytes(), "application/pdf")},
        data={"max_pages": "0"},
    )
    assert r.status_code == 400
