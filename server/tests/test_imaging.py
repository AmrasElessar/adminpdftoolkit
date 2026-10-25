"""Photo / scan clean-up for images → PDF."""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf
import pytest
from PIL import Image, ImageDraw, ImageFont

import adminpdf
from adminpdf.core import imaging

from .conftest import Api

FONT = str(Path(adminpdf.__file__).parent / "assets" / "fonts" / "DejaVuSans.ttf")


def text_page(w: int = 1240, h: int = 1754) -> Image.Image:
    """A white A4-ish page with lines of text (150 DPI)."""
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT, 34)
    except OSError:
        font = ImageFont.load_default()
    for i in range(28):
        draw.text((110, 120 + i * 52), f"Satır {i + 1}: Sözleşme hükümleri ve ödeme koşulları", fill="black", font=font)
    return img


def png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


@pytest.mark.parametrize("tilt", [-7.0, -2.5, 3.0, 9.0])
def test_detect_skew_finds_the_tilt(tilt: float) -> None:
    tilted = text_page().rotate(-tilt, expand=True, fillcolor="white")  # turned clockwise by `tilt`
    angle = imaging.detect_skew(tilted)
    assert angle == pytest.approx(tilt, abs=0.4)  # counter-clockwise correction
    straight = imaging.rotate(tilted, angle)
    assert abs(imaging.detect_skew(straight)) <= 0.3


def test_detect_skew_ignores_blank_and_photos() -> None:
    assert imaging.detect_skew(Image.new("RGB", (800, 600), "white")) == 0.0
    assert imaging.detect_skew(Image.new("RGB", (800, 600), (30, 90, 160))) == 0.0


def photographed_document() -> tuple[Image.Image, float]:
    """A page photographed at an angle on a dark desk."""
    import cv2
    import numpy as np

    page = np.asarray(text_page(620, 877))
    desk = np.full((1200, 1000, 3), (60, 45, 35), np.uint8)
    src = np.array([[0, 0], [619, 0], [619, 876], [0, 876]], np.float32)
    dst = np.array([[180, 140], [820, 200], [860, 1060], [120, 1010]], np.float32)
    m = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(page, m, (1000, 1200), dst=desk.copy(), borderMode=cv2.BORDER_TRANSPARENT)
    return Image.fromarray(warped), 620 / 877


def test_find_and_warp_document() -> None:
    photo, aspect = photographed_document()
    corners = imaging.find_document(photo)
    assert corners is not None
    flat = imaging.warp_document(photo, corners)
    assert flat.width / flat.height == pytest.approx(aspect, rel=0.08)
    # The desk is gone: borders are paper-white.
    px = flat.convert("L").getpixel((flat.width // 2, 8))
    assert isinstance(px, int) and px > 180


def test_flat_scan_has_no_document_outline() -> None:
    assert imaging.find_document(text_page()) is None


def test_enhance_modes() -> None:
    page = text_page(600, 800)
    assert imaging.enhance(page, "bw").mode == "1"
    assert imaging.enhance(page, "gray").mode == "L"
    assert imaging.enhance(page, "auto").mode == "RGB"
    assert imaging.enhance(page, "none") is page


def test_images_to_pdf_straightens_and_orients(api: Api) -> None:
    tilted = text_page().rotate(-6, expand=True, fillcolor="white")
    # EXIF orientation 6 = the camera was turned; viewer must rotate 90° cw.
    sideways = text_page(600, 850).rotate(90, expand=True)
    exif = Image.Exif()
    exif[0x0112] = 6
    buf = io.BytesIO()
    sideways.save(buf, "JPEG", exif=exif)
    photo, _ = photographed_document()
    a = api.upload(png(tilted), "egik.png")
    b = api.upload(buf.getvalue(), "yan.jpg")
    c = api.upload(png(photo), "foto.png")
    job = api.run(
        "images_to_pdf",
        [a["id"], b["id"], c["id"]],
        {"page_size": "a4", "deskew": True, "crop_document": True, "enhance": "auto"},
    )
    assert job["status"] == "done", job
    assert job["data"]["pages"] == 3
    fixed = {s["file"]: s["degrees"] for s in job["data"]["straightened"]}
    assert fixed["egik.png"][0] == pytest.approx(6, abs=0.5)
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as doc:
        assert doc.page_count == 3
        for page in doc:
            info = page.get_image_info()[0]
            bbox = pymupdf.Rect(info["bbox"])
            assert bbox.height > bbox.width  # every page ends up upright (portrait)


def test_straighten_scanned_pdf(api: Api) -> None:
    tilted = text_page().rotate(-5, expand=True, fillcolor="white")
    buf = io.BytesIO()
    tilted.save(buf, "JPEG", quality=85)
    doc = pymupdf.open()
    page = doc.new_page(width=tilted.width * 72 / 150, height=tilted.height * 72 / 150)
    page.insert_image(page.rect, stream=buf.getvalue())
    straight = doc.new_page()
    straight.insert_text((72, 72), "Düz sayfa", fontsize=12)
    f = api.upload(doc.tobytes(), "egri_tarama.pdf")
    job = api.run("straighten_pages", [f["id"]])
    assert job["status"] == "done", job
    assert [s["page"] for s in job["data"]["straightened"]] == [1]
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as out:
        assert out.page_count == 2
        pix = out[0].get_pixmap(dpi=100, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        assert abs(imaging.detect_skew(img)) <= 0.4
