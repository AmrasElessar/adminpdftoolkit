"""Conversions. M1 ships images → PDF and PDF → images; Office formats and
OCR arrive in M5."""

from __future__ import annotations

import io
import zipfile
from typing import Any, Literal

import pymupdf

from ..core.errors import UserError
from ..core.pdf import open_pdf, parse_page_spec, save_pdf
from .base import Context, Field, Operation, Params, register

# Hard ceiling on a rendered page, independent of DPI: 40 MP ≈ A3 at 400 DPI.
MAX_RENDER_PIXELS = 40_000_000

PAGE_SIZES = {"a4": (595.28, 841.89), "letter": (612, 792), "a3": (841.89, 1190.55)}


class ImagesParams(Params):
    page_size: Literal["fit", "a4", "letter", "a3"] = Field(
        "a4",
        tr="Sayfa boyutu",
        en="Page size",
        ui={
            "options": {
                "fit": {"tr": "Görsel boyutunda", "en": "Same as image"},
                "a4": {"tr": "A4", "en": "A4"},
                "letter": {"tr": "Letter", "en": "Letter"},
                "a3": {"tr": "A3", "en": "A3"},
            }
        },
    )
    margin: float = Field(18, tr="Kenar boşluğu (pt)", en="Margin (pt)", ge=0, le=144)
    auto_orient: bool = Field(
        True, tr="Telefon fotoğrafı yönünü düzelt (EXIF)", en="Fix phone photo orientation (EXIF)"
    )
    crop_document: bool = Field(
        False,
        tr="Kâğıdı bul, kırp ve perspektifi düzelt",
        en="Find the sheet, crop and flatten perspective",
        help_tr="Masada çekilmiş belge fotoğrafları için.",
        help_en="For photos of documents lying on a desk.",
    )
    deskew: bool = Field(True, tr="Eğikliği otomatik düzelt", en="Straighten automatically")
    enhance: Literal["none", "auto", "gray", "bw"] = Field(
        "none",
        tr="Görüntü iyileştirme",
        en="Enhancement",
        ui={
            "options": {
                "none": {"tr": "Yok (özgün)", "en": "None (original)"},
                "auto": {"tr": "Gölge ve arka planı temizle", "en": "Remove shadows / clean background"},
                "gray": {"tr": "Gri tonlama", "en": "Grayscale"},
                "bw": {"tr": "Siyah-beyaz (tarama)", "en": "Black & white (scan)"},
            }
        },
    )
    quality: int = Field(85, tr="JPEG kalitesi", en="JPEG quality", ge=30, le=100)


def _prepare(path: Any, params: ImagesParams) -> tuple[list[tuple[bytes, int, int]], list[float]]:
    """Clean up every frame of one image file; returns encoded frames
    (bytes, width, height) and the skew angles that were corrected."""
    from PIL import Image, ImageSequence, UnidentifiedImageError

    from ..core import imaging

    frames: list[tuple[bytes, int, int]] = []
    angles: list[float] = []
    try:
        src = Image.open(path)
    except (UnidentifiedImageError, OSError) as e:
        raise UserError("Görsel okunamadı.", "Cannot read the image.") from e
    with src:
        for frame in ImageSequence.Iterator(src):
            img = frame.copy()
            if img.width * img.height > MAX_RENDER_PIXELS:
                raise UserError("Görsel çok büyük (40 MP sınırı).", "The image is too large (40 MP limit).")
            if params.auto_orient:
                img = imaging.auto_orient(img)
            if params.crop_document:
                corners = imaging.find_document(img)
                if corners is not None:
                    img = imaging.warp_document(img, corners)
            if params.deskew:
                angle = imaging.detect_skew(img)
                if abs(angle) >= 0.2:
                    img = imaging.rotate(img, angle)
                    angles.append(angle)
            img = imaging.enhance(img, params.enhance)
            buf = io.BytesIO()
            if img.mode == "1":
                img.save(buf, "PNG", optimize=True)  # bilevel compresses best losslessly
            elif img.mode in ("RGBA", "LA", "P") and params.enhance == "none" and not params.deskew:
                img.save(buf, "PNG")
            else:
                img.convert("L" if img.mode == "L" else "RGB").save(buf, "JPEG", quality=params.quality, optimize=True)
            frames.append((buf.getvalue(), img.width, img.height))
    return frames, angles


@register
class ImagesToPdf(Operation):
    name = "images_to_pdf"
    category = "convert"
    title_tr, title_en = "Görselden PDF", "Images to PDF"
    description_tr = (
        "JPG, PNG, TIFF, WebP… görsellerini sırasıyla tek PDF yapar; yönü ve eğikliği düzeltir, "
        "fotoğraftaki belgeyi kırpıp düzleştirir, gölgeyi temizler."
    )
    description_en = (
        "Combine JPG, PNG, TIFF, WebP… images in order into one PDF; fixes orientation and tilt, "
        "crops and flattens photographed documents, removes shadows."
    )
    accepts = frozenset({"image"})
    max_inputs = 500
    Params = ImagesParams

    def run(self, ctx: Context, params: ImagesParams) -> None:
        out = pymupdf.open()
        straightened: list[dict[str, Any]] = []
        try:
            for k, inp in enumerate(ctx.inputs):
                frames, angles = _prepare(inp.path, params)
                if angles:
                    straightened.append({"file": inp.name, "degrees": angles})
                for data, w_px, h_px in frames:
                    # 150 DPI nominal size for "fit"; scaled to the page otherwise.
                    w, h = w_px * 72 / 150, h_px * 72 / 150
                    if params.page_size == "fit":
                        pw, ph = w + 2 * params.margin, h + 2 * params.margin
                    else:
                        pw, ph = PAGE_SIZES[params.page_size]
                        if w > h:
                            pw, ph = ph, pw
                    page = out.new_page(width=pw, height=ph)
                    box = pymupdf.Rect(params.margin, params.margin, pw - params.margin, ph - params.margin)
                    page.insert_image(box, stream=data, keep_proportion=True)
                ctx.progress((k + 1) / len(ctx.inputs), inp.name)
            pages = out.page_count
            save_pdf(out, ctx.output(f"{ctx.inputs[0].stem}.pdf"))
        finally:
            out.close()
        ctx.data = {"pages": pages, "straightened": straightened}


class ToImagesParams(Params):
    format: Literal["png", "jpg"] = Field(
        "png",
        tr="Biçim",
        en="Format",
        ui={"options": {"png": {"tr": "PNG", "en": "PNG"}, "jpg": {"tr": "JPG", "en": "JPG"}}},
    )
    dpi: int = Field(150, tr="Çözünürlük (DPI)", en="Resolution (DPI)", ge=36, le=600)
    quality: int = Field(85, tr="JPG kalitesi", en="JPG quality", ge=10, le=100, ui={"show_if": {"format": "jpg"}})
    pages: str = Field("", tr="Sayfalar (boş = tümü)", en="Pages (empty = all)", max_length=2000)


@register
class PdfToImages(Operation):
    name = "pdf_to_images"
    category = "convert"
    title_tr, title_en = "PDF'ten Görsele", "PDF to Images"
    description_tr = "Her sayfayı PNG veya JPG görsel olarak dışa aktarır (ZIP)."
    description_en = "Export each page as a PNG or JPG image (ZIP)."
    Params = ToImagesParams

    def run(self, ctx: Context, params: ToImagesParams) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            targets = parse_page_spec(params.pages, doc.page_count)
            zip_path = ctx.output(f"{inp.stem}_gorseller.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
                for k, i in enumerate(targets):
                    page = doc[i]
                    zoom = params.dpi / 72
                    pixels = page.rect.width * zoom * page.rect.height * zoom
                    if pixels > MAX_RENDER_PIXELS:
                        zoom *= (MAX_RENDER_PIXELS / pixels) ** 0.5
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                    if params.format == "jpg":
                        data = pix.tobytes("jpeg", jpg_quality=params.quality)
                    else:
                        data = pix.tobytes("png")
                    zf.writestr(f"{inp.stem}_{i + 1:04d}.{params.format}", data)
                    ctx.progress((k + 1) / len(targets), "")
