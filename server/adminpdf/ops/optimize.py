"""Size optimisation."""

from __future__ import annotations

import contextlib
from typing import Literal

from ..core.pdf import open_pdf, save_pdf
from .base import Context, Field, Operation, Params, register

# preset → (downsample images above this DPI, target DPI, JPEG quality)
PRESETS: dict[str, tuple[int, int, int] | None] = {
    "lossless": None,
    "print": (300, 200, 85),
    "ebook": (200, 150, 70),
    "screen": (110, 96, 55),
}


class CompressParams(Params):
    preset: Literal["lossless", "print", "ebook", "screen"] = Field(
        "ebook",
        tr="Kalite",
        en="Quality",
        ui={
            "options": {
                "lossless": {"tr": "Kayıpsız (yalnızca yapı)", "en": "Lossless (structure only)"},
                "print": {"tr": "Baskı (yüksek)", "en": "Print (high)"},
                "ebook": {"tr": "Dengeli", "en": "Balanced"},
                "screen": {"tr": "Ekran (en küçük)", "en": "Screen (smallest)"},
            }
        },
    )
    grayscale: bool = Field(False, tr="Görselleri griye çevir", en="Convert images to grayscale")
    subset_fonts: bool = Field(True, tr="Fontları alt kümele", en="Subset embedded fonts")


@register
class Compress(Operation):
    name = "compress"
    category = "optimize"
    title_tr, title_en = "PDF Sıkıştır", "Compress PDF"
    description_tr = "Görselleri yeniden örnekleyip yapıyı sadeleştirerek dosya boyutunu küçültür."
    description_en = "Shrink file size by resampling images and cleaning up the structure."
    Params = CompressParams

    def run(self, ctx: Context, params: CompressParams) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            preset = PRESETS[params.preset]
            if preset is not None or params.grayscale:
                threshold, target, quality = preset or (10_000, 0, 90)
                ctx.progress(0.1, "images")
                doc.rewrite_images(
                    dpi_threshold=threshold if preset else None,
                    dpi_target=target,
                    quality=quality,
                    set_to_gray=params.grayscale,
                )
            if params.subset_fonts:
                ctx.progress(0.6, "fonts")
                # Subsetting needs fontTools and can fail on exotic fonts; the
                # file is still valid without it.
                with contextlib.suppress(Exception):
                    doc.subset_fonts()
            ctx.progress(0.8, "save")
            save_pdf(doc, ctx.output(f"{inp.stem}_sikistirilmis.pdf"), compression_effort=9)
