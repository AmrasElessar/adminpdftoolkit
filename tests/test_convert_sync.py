"""Sync ``/convert`` endpoint coverage — exercises the S5.3 collapse.

Before S5.3 the sync endpoint had three near-identical Excel / Word / JPG
branches; the refactor pushed each one into a dedicated renderer behind
a ``_SYNC_RENDERERS`` dispatch table. These tests pin both the table's
shape and the per-format end-to-end behaviour so a regression in any one
branch fails loudly.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

import app
import core
from routers import convert as convert_router


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(core, "is_local_request", lambda req: True)
    return TestClient(app.app)


@pytest.fixture
def small_pdf(tmp_path: Path) -> Path:
    """One-page PDF with a heading and a body paragraph — minimal content
    that all three renderers accept."""
    out = tmp_path / "doc.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 80), "Başlık", fontsize=18, fontname="helv")
    page.insert_text((72, 130), "Birinci paragraf metnidir.",
                     fontsize=11, fontname="helv")
    doc.save(str(out))
    doc.close()
    return out


# ---------------------------------------------------------------------------
# _SYNC_RENDERERS dispatch table contract
# ---------------------------------------------------------------------------
def test_sync_renderers_table_covers_all_formats() -> None:
    """The sync endpoint passes ``target`` straight into this dict —
    a missing key would 500 the request, an extra key would mount a
    silently dead format. Pin the exact set."""
    assert set(convert_router._SYNC_RENDERERS) == {"excel", "word", "jpg"}


def test_sync_renderers_table_suffixes() -> None:
    """Every entry pairs the on-disk suffix used to name the output file
    with a callable that knows how to materialise it."""
    table = convert_router._SYNC_RENDERERS
    assert table["excel"][0] == ".xlsx"
    assert table["word"][0] == ".docx"
    assert table["jpg"][0] == ".zip"
    for _, render in table.values():
        assert callable(render)


# ---------------------------------------------------------------------------
# End-to-end per format
# ---------------------------------------------------------------------------
def test_sync_convert_excel_returns_xlsx(client: TestClient, small_pdf: Path) -> None:
    r = client.post(
        "/convert",
        files={"file": ("doc.pdf", small_pdf.read_bytes(), "application/pdf")},
        data={"target": "excel"},
    )
    assert r.status_code == 200, r.text
    ct = r.headers["content-type"]
    assert "spreadsheetml" in ct
    # Load it as openpyxl to confirm we got a real workbook
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.active is not None


def test_sync_convert_word_returns_docx(client: TestClient, small_pdf: Path) -> None:
    r = client.post(
        "/convert",
        files={"file": ("doc.pdf", small_pdf.read_bytes(), "application/pdf")},
        data={"target": "word"},
    )
    assert r.status_code == 200, r.text
    ct = r.headers["content-type"]
    assert "wordprocessingml" in ct
    # .docx is a zip — header bytes start with PK
    assert r.content[:2] == b"PK"


def test_sync_convert_jpg_returns_zip_of_pages(client: TestClient, small_pdf: Path) -> None:
    r = client.post(
        "/convert",
        files={"file": ("doc.pdf", small_pdf.read_bytes(), "application/pdf")},
        data={"target": "jpg"},
    )
    assert r.status_code == 200, r.text
    assert "application/zip" in r.headers["content-type"]
    # Extract the ZIP and confirm at least one .jpg page is inside
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert names, "ZIP is empty — JPG renderer produced nothing"
    assert any(n.lower().endswith(".jpg") for n in names)


# ---------------------------------------------------------------------------
# Validation + branch guards
# ---------------------------------------------------------------------------
def test_sync_convert_rejects_invalid_target(client: TestClient, small_pdf: Path) -> None:
    r = client.post(
        "/convert",
        files={"file": ("doc.pdf", small_pdf.read_bytes(), "application/pdf")},
        data={"target": "html"},  # not in ALLOWED_FORMATS
    )
    assert r.status_code == 400


def test_sync_convert_rejects_non_pdf_filename(client: TestClient) -> None:
    r = client.post(
        "/convert",
        files={"file": ("notes.exe", io.BytesIO(b"MZ\x90"), "application/octet-stream")},
        data={"target": "word"},
    )
    assert r.status_code == 400


def test_sync_convert_word_rejects_scanned_pdf(monkeypatch: pytest.MonkeyPatch,
                                                 client: TestClient,
                                                 small_pdf: Path) -> None:
    """Word/Excel against a scanned PDF would yield empty output — the
    endpoint must short-circuit with a clear 400 instead."""
    monkeypatch.setattr(convert_router, "is_scanned_pdf", lambda doc: True)

    r = client.post(
        "/convert",
        files={"file": ("scan.pdf", small_pdf.read_bytes(), "application/pdf")},
        data={"target": "word"},
    )
    assert r.status_code == 400
    assert "OCR" in r.json()["detail"]


def test_sync_convert_jpg_does_not_block_on_scanned(monkeypatch: pytest.MonkeyPatch,
                                                      client: TestClient,
                                                      small_pdf: Path) -> None:
    """JPG render is image-only; a scanned PDF is fine through that path."""
    monkeypatch.setattr(convert_router, "is_scanned_pdf", lambda doc: True)

    r = client.post(
        "/convert",
        files={"file": ("scan.pdf", small_pdf.read_bytes(), "application/pdf")},
        data={"target": "jpg"},
    )
    assert r.status_code == 200
    assert "application/zip" in r.headers["content-type"]
