"""Conversions. M1 ships images → PDF and PDF → images; Office formats and
OCR arrive in M5."""

from __future__ import annotations

import zipfile
from typing import Literal

import pymupdf

from ..core.errors import UserError
from ..core.pdf import open_pdf, parse_page_spec, save_pdf
from .base import Context, Field, Operation, Params, register

# Hard ceiling on a rendered page, independent of DPI: 40 MP ≈ A3 at 400 DPI.
MAX_RENDER_PIXELS = 40_000_000

PAGE_SIZES = {"a4": (595.28, 841.89), "letter": (612, 792), "a3": (841.89, 1190.55)}


class ImagesParams(Params):
    page_size: Literal["fit", "a4", "letter", "a3"] = Field(
        "fit",
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
    margin: float = Field(0, tr="Kenar boşluğu (pt)", en="Margin (pt)", ge=0, le=144)


@register
class ImagesToPdf(Operation):
    name = "images_to_pdf"
    category = "convert"
    title_tr, title_en = "Görselden PDF", "Images to PDF"
    description_tr = "JPG, PNG, TIFF, WebP… görsellerini tek PDF'te birleştirir."
    description_en = "Combine JPG, PNG, TIFF, WebP… images into one PDF."
    accepts = frozenset({"image"})
    max_inputs = 500
    Params = ImagesParams

    def run(self, ctx: Context, params: ImagesParams) -> None:
        out = pymupdf.open()
        try:
            for k, inp in enumerate(ctx.inputs):
                try:
                    img = pymupdf.open(inp.path)
                except Exception as e:
                    raise UserError(f"Görsel okunamadı: {inp.name}", f"Cannot read image: {inp.name}") from e
                with img:
                    pdf_bytes = img.convert_to_pdf()
                with pymupdf.open("pdf", pdf_bytes) as frames:  # multi-page TIFF → many
                    for frame in frames:
                        w, h = frame.rect.width, frame.rect.height
                        if params.page_size == "fit":
                            pw, ph = w + 2 * params.margin, h + 2 * params.margin
                        else:
                            pw, ph = PAGE_SIZES[params.page_size]
                            if w > h:
                                pw, ph = ph, pw
                        page = out.new_page(width=pw, height=ph)
                        box = pymupdf.Rect(params.margin, params.margin, pw - params.margin, ph - params.margin)
                        page.show_pdf_page(box, frames, frame.number)
                ctx.progress((k + 1) / len(ctx.inputs), inp.name)
            save_pdf(out, ctx.output(f"{ctx.inputs[0].stem}.pdf"))
        finally:
            out.close()


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
