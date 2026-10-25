from __future__ import annotations

import io

import pikepdf
import pymupdf
import pytest

from adminpdf.core.pdf import unicode_font_path
from adminpdf.ops._ocrmypdf import find_ghostscript

from .conftest import Api, make_pdf

needs_gs = pytest.mark.skipif(find_ghostscript() is None, reason="Ghostscript not installed")


def pdfaid(data: bytes) -> tuple[str, str]:
    with pikepdf.open(io.BytesIO(data)) as pdf:
        meta = pdf.open_metadata()
        return str(meta.get("pdfaid:part")), str(meta.get("pdfaid:conformance"))


@needs_gs
@pytest.mark.parametrize(("level", "part"), [("2b", "2"), ("1b", "1"), ("3b", "3")])
def test_pdfa_declares_level(api: Api, level: str, part: str) -> None:
    f = api.upload(make_pdf(2, text="Arsiv"), "rapor.pdf")
    job = api.run("pdfa", [f["id"]], {"level": level})
    assert job["status"] == "done", job
    assert job["result"]["name"] == f"rapor_pdfa-{level}.pdf"
    data = api.download(job["result"]["id"])
    assert pdfaid(data) == (part, "B")
    with pymupdf.open("pdf", data) as doc:
        assert doc.page_count == 2
        assert "Arsiv 1" in doc[0].get_text()  # converted, not rasterised
    d = job["data"]
    assert d["validated"] is False
    assert d["declared"] == {"part": part, "conformance": "B"}
    assert d["text_changed_pages"] == []
    assert any("veraPDF" in n["en"] for n in d["notes"])


@needs_gs
def test_pdfa_default_level_and_encrypted_input(api: Api) -> None:
    with pymupdf.open("pdf", make_pdf(1)) as doc:
        data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="gizli", owner_pw="sahip")
    f = api.upload(data)
    job = api.run("pdfa", [f["id"]], password="gizli")
    assert job["status"] == "done", job
    assert pdfaid(api.download(job["result"]["id"])) == ("2", "B")


@needs_gs
def test_pdfa_reports_text_fidelity(api: Api) -> None:
    font = unicode_font_path()
    if font is None:
        pytest.skip("no Unicode font")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_font(fontname="uni", fontfile=font)
    page.insert_text((72, 100), "Şubat İstanbul ılık", fontsize=20, fontname="uni")
    before = "".join(doc[0].get_text().split())
    f = api.upload(doc.tobytes())
    job = api.run("pdfa", [f["id"]])
    assert job["status"] == "done", job
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as out:
        changed = "".join(out[0].get_text().split()) != before
    # Ghostscript may re-map some glyphs; the op must say so when it does.
    assert job["data"]["text_changed_pages"] == ([1] if changed else [])
    assert (len(job["data"]["notes"]) == 2) is changed


def test_pdfa_rejects_unknown_level(api: Api) -> None:
    f = api.upload(make_pdf(1))
    assert api.start("pdfa", [f["id"]], {"level": "4u"}).status_code == 422
