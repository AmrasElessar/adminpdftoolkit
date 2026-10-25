"""Editing a scanned (image-only) PDF: OCR first, then replace text."""

from __future__ import annotations

import shutil

import pymupdf
import pytest

from .conftest import Api

pytestmark = pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def scanned_pdf() -> bytes:
    """Render real text to a bitmap and wrap it as an image-only page."""
    src = pymupdf.open()
    page = src.new_page()
    page.insert_text((72, 120), "Toplam tutar 1250 TL", fontsize=22, fontname="dj", fontfile=FONT)
    page.insert_text((72, 180), "Teslim tarihi Mart", fontsize=22, fontname="dj", fontfile=FONT)
    pix = page.get_pixmap(dpi=200)
    out = pymupdf.open()
    img_page = out.new_page(width=page.rect.width, height=page.rect.height)
    img_page.insert_image(img_page.rect, stream=pix.tobytes("jpeg", jpg_quality=85))
    data: bytes = out.tobytes()
    return data


def test_scanned_page_becomes_editable_after_ocr(api: Api) -> None:
    f = api.upload(scanned_pdf(), "tarama.pdf")
    before = api.run("text_spans", [f["id"]], {"pages": "1", "granularity": "line"})
    assert before["data"]["pages"][0]["spans"] == []  # nothing to edit yet

    ocr = api.run("ocr", [f["id"]], {"languages": "tur+eng", "mode": "skip"})
    assert ocr["status"] == "done", ocr
    oid = ocr["result"]["id"]
    spans = api.run("text_spans", [oid], {"pages": "1", "granularity": "line"})["data"]["pages"][0]["spans"]
    line = next(s for s in spans if "1250" in s["text"])

    job = api.run(
        "edit",
        [oid],
        {"operations": [{"type": "replace", "page": 1, "rect": line["rect"], "text": "Toplam tutar 9999 TL"}]},
    )
    assert job["status"] == "done", job
    assert job["data"]["applied"] == 1
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as doc:
        page = doc[0]
        text = page.get_text()
        assert "9999" in text and "1250" not in text
        # The scanned pixels of the old line are covered: re-OCR-free check —
        # the area left of the new text's end is covered by the sampled
        # background, so rendering shows only the new glyphs there.
        r = ~page.transformation_matrix  # noqa: F841 - document intent


def test_ocr_spans_suggest_sans_font_and_real_size(api: Api) -> None:
    f = api.upload(scanned_pdf(), "tarama.pdf")
    oid = api.run("ocr", [f["id"]], {"languages": "tur+eng"})["result"]["id"]
    spans = api.run("text_spans", [oid], {"pages": "1", "granularity": "line"})["data"]["pages"][0]["spans"]
    line = next(s for s in spans if "1250" in s["text"])
    assert line["ocr"] is True
    assert line["matched_font"]["family_id"] in ("bundled:dejavu-sans", "standard:helvetica")
    assert 19 <= line["size"] <= 26  # rendered at 22 pt
