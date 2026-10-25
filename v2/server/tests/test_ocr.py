from __future__ import annotations

import os
import subprocess
import sys

import pymupdf
import pytest

from adminpdf.core.pdf import unicode_font_path
from adminpdf.ops._ocrmypdf import _descendants, _ProgressBar, forward_progress
from adminpdf.ops.ocr import find_tesseract, pages_option, tesseract_languages

from .conftest import Api, make_pdf

needs_tesseract = pytest.mark.skipif(
    find_tesseract() is None or not {"tur", "eng"} <= tesseract_languages(),
    reason="Tesseract with tur+eng not installed",
)


def make_scanned_pdf(
    lines: tuple[str, ...] = ("Toplantı 12 Şubat günü İstanbul'da", "Merhaba dünya"), *, password: str = ""
) -> bytes:
    """One page that carries text only as pixels — like a scanner output."""
    src = pymupdf.open()
    page = src.new_page(width=595, height=842)
    font = unicode_font_path()
    if font:
        page.insert_font(fontname="uni", fontfile=font)
    for k, line in enumerate(lines):
        page.insert_text((72, 160 + k * 80), line, fontsize=26, fontname="uni" if font else "helv")
    pix = page.get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
    out = pymupdf.open()
    scan = out.new_page(width=595, height=842)
    scan.insert_image(scan.rect, pixmap=pix)
    kw: dict[str, object] = {}
    if password:
        kw = {"encryption": pymupdf.PDF_ENCRYPT_AES_256, "user_pw": password, "owner_pw": password + "-owner"}
    data: bytes = out.tobytes(deflate=True, **kw)
    out.close()
    src.close()
    return data


def text_of(data: bytes, password: str = "") -> str:
    with pymupdf.open("pdf", data) as doc:
        if password:
            doc.authenticate(password)
        return "\n".join(p.get_text() for p in doc)


@pytest.mark.parametrize(
    ("indices", "expected"),
    [([0], "1"), ([0, 1, 2, 4], "1-3,5"), ([5, 3, 4, 4], "4-6"), ([9, 0, 2], "1,3,10")],
)
def test_pages_option(indices: list[int], expected: str) -> None:
    assert pages_option(indices) == expected


def test_progress_bar_forwards_scaled_progress() -> None:
    seen: list[tuple[float, str]] = []
    with forward_progress(lambda f, m: seen.append((f, m))), _ProgressBar(total=2, desc="OCR") as bar:
        bar.update()
        bar.update()
    fractions = [f for f, _ in seen]
    assert fractions == sorted(fractions)
    assert seen[-1] == (pytest.approx(0.80), "OCR")


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="uses /proc")
def test_descendants_found_for_reaping() -> None:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert child.pid in _descendants(os.getpid())
    finally:
        child.kill()
        child.wait()


def test_language_pattern_rejected(api: Api) -> None:
    f = api.upload(make_pdf(1))
    assert api.start("ocr", [f["id"]], {"languages": "tur; rm -rf"}).status_code == 422


@needs_tesseract
def test_unknown_language_is_user_error(api: Api) -> None:
    if "xyzq" in tesseract_languages():
        pytest.skip("odd language installed")
    f = api.upload(make_pdf(1))
    job = api.run("ocr", [f["id"]], {"languages": "tur+xyzq"})
    assert job["status"] == "failed"
    assert "xyzq" in job["error"]["en"] and "tur" in job["error"]["en"]


@needs_tesseract
def test_ocr_makes_scanned_pdf_searchable(api: Api) -> None:
    data = make_scanned_pdf()
    assert text_of(data).strip() == ""
    f = api.upload(data, "tarama.pdf")
    job = api.run("ocr", [f["id"]], {"languages": "tur+eng"})
    assert job["status"] == "done", job
    assert job["result"]["name"] == "tarama_ocr.pdf"
    text = text_of(api.download(job["result"]["id"]))
    assert "Şubat" in text and "İstanbul" in text, text
    assert "dünya" in text
    assert job["data"]["languages"] == ["tur", "eng"]


@needs_tesseract
def test_ocr_encrypted_input(api: Api) -> None:
    f = api.upload(make_scanned_pdf(("İstanbul",), password="gizli"), "sifreli.pdf")
    wrong = api.run("ocr", [f["id"]], password="yanlis")
    assert wrong["status"] == "failed" and "password" in wrong["error"]["en"]
    job = api.run("ocr", [f["id"]], password="gizli")
    assert job["status"] == "done", job
    assert "İstanbul" in text_of(api.download(job["result"]["id"]))


@needs_tesseract
def test_ocr_skip_keeps_existing_text(api: Api) -> None:
    f = api.upload(make_pdf(2, text="Mevcut"))
    job = api.run("ocr", [f["id"]], {"mode": "skip", "pages": "2"})
    assert job["status"] == "done", job
    text = text_of(api.download(job["result"]["id"]))
    assert "Mevcut 1" in text and "Mevcut 2" in text
    assert job["data"]["pages"] == 1
