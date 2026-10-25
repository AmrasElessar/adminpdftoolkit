from __future__ import annotations

import io
import zipfile

import pymupdf

from adminpdf.core.pdf import unicode_font_path

from .conftest import Api, make_pdf, make_png


def turkish_pdf() -> bytes:
    doc = pymupdf.open()
    font = unicode_font_path()
    for i in range(2):
        page = doc.new_page()
        if font:
            page.insert_font(fontname="uni", fontfile=font)
        kw = {"fontname": "uni"} if font else {}
        page.insert_text((72, 100), f"Çağrı kaydı {i + 1}", fontsize=14, **kw)
        page.insert_text((72, 118), "ikinci satır", fontsize=14, **kw)
        page.insert_text((72, 300), "Ayrı paragraf", fontsize=14, **kw)
    data: bytes = doc.tobytes()
    doc.close()
    return data


def make_jpeg(w: int, h: int) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), (20, 120, 200)).save(buf, "JPEG")
    return buf.getvalue()


def images_pdf() -> bytes:
    doc = pymupdf.open()
    png, jpg, icon = make_png(200, 100), make_jpeg(120, 90), make_png(8, 8)
    for i in range(2):
        page = doc.new_page()
        # The same PNG on both pages is stored once (one xref).
        page.insert_image(pymupdf.Rect(36, 36, 236, 136), stream=png)
        page.insert_image(pymupdf.Rect(300, 36, 316, 52), stream=icon)
        if i == 1:
            page.insert_image(pymupdf.Rect(36, 200, 156, 290), stream=jpg)
    data: bytes = doc.tobytes(garbage=3)
    doc.close()
    return data


def test_pdf_to_text_utf8_with_separators(api: Api) -> None:
    f = api.upload(turkish_pdf(), "kayit.pdf")
    job = api.run("pdf_to_text", [f["id"]])
    assert job["status"] == "done", job
    assert job["result"]["name"] == "kayit.txt"
    text = api.download(job["result"]["id"]).decode("utf-8")
    assert "===== Sayfa 1 / Page 1 =====" in text and "===== Sayfa 2 / Page 2 =====" in text
    if unicode_font_path():
        # Paragraph mode joins the two lines of the first block.
        assert "Çağrı kaydı 1 ikinci satır" in text
        assert "\n\nAyrı paragraf" in text


def test_pdf_to_text_layout_and_pages(api: Api) -> None:
    f = api.upload(turkish_pdf())
    job = api.run("pdf_to_text", [f["id"]], {"keep_layout": True, "page_separators": False, "pages": "2"})
    assert job["status"] == "done", job
    text = api.download(job["result"]["id"]).decode("utf-8")
    assert "=====" not in text
    assert "kaydı 1" not in text
    if unicode_font_path():
        assert "Çağrı kaydı 2\nikinci satır" in text


def test_pdf_to_text_without_text_fails(api: Api) -> None:
    doc = pymupdf.open()
    doc.new_page()
    f = api.upload(doc.tobytes())
    job = api.run("pdf_to_text", [f["id"]])
    assert job["status"] == "failed"
    assert "OCR" in job["error"]["en"]


def test_extract_images_dedupes_and_filters(api: Api) -> None:
    f = api.upload(images_pdf(), "gorsel.pdf")
    job = api.run("extract_images", [f["id"]])
    assert job["status"] == "done", job
    with zipfile.ZipFile(io.BytesIO(api.download(job["result"]["id"]))) as zf:
        names = sorted(zf.namelist())
        exts = sorted(n.rsplit(".", 1)[1] for n in names)
        assert len(names) == 2
        assert exts == ["jpeg", "png"]
        jpg = next(n for n in names if n.endswith(".jpeg"))
        assert zf.read(jpg).startswith(b"\xff\xd8\xff")  # original JPEG bytes, not re-encoded
    d = job["data"]
    assert d["images"] == 2
    assert d["skipped_small"] == 1
    assert d["duplicates"] >= 2
    assert d["truncated"] is False


def test_extract_images_min_size_and_none(api: Api) -> None:
    f = api.upload(images_pdf())
    job = api.run("extract_images", [f["id"]], {"min_size": 95})
    assert job["status"] == "done", job
    assert job["data"]["images"] == 1
    plain = api.upload(make_pdf(1))
    job = api.run("extract_images", [plain["id"]])
    assert job["status"] == "failed"
    assert "no embedded images" in job["error"]["en"]
