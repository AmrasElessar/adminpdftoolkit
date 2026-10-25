"""Clean-up for scanned PDFs (pages that are photos of paper)."""

from __future__ import annotations

from typing import Any

import pymupdf

from ..core.errors import UserError
from ..core.pdf import open_pdf, parse_page_spec, save_pdf
from .base import Context, Field, Operation, Params, register


class StraightenParams(Params):
    pages: str = Field("", tr="Sayfalar (boş = tümü)", en="Pages (empty = all)", max_length=2000)
    min_angle: float = Field(
        0.2,
        tr="En küçük düzeltme açısı (°)",
        en="Smallest correction (°)",
        help_tr="Bundan küçük eğimler olduğu gibi bırakılır.",
        help_en="Smaller tilts are left alone.",
        ge=0.05,
        le=5,
    )


@register
class StraightenPages(Operation):
    name = "straighten_pages"
    category = "ocr"
    title_tr, title_en = "Taranmış Sayfaları Düzelt", "Straighten Scanned Pages"
    description_tr = "Eğri taranmış sayfaların açısını otomatik bulur ve düzeltir; metin katmanı da birlikte döner."
    description_en = "Finds and fixes the tilt of crooked scanned pages; any text layer turns with them."
    Params = StraightenParams

    def run(self, ctx: Context, params: StraightenParams) -> None:
        from PIL import Image

        from ..core import imaging

        inp = ctx.inputs[0]
        fixed: list[dict[str, Any]] = []
        with open_pdf(inp.path, inp.password) as src:
            targets = set(parse_page_spec(params.pages, src.page_count))
            out = pymupdf.open()
            try:
                for pno in range(src.page_count):
                    page = src[pno]
                    angle = 0.0
                    if pno in targets:
                        pix = page.get_pixmap(dpi=100, alpha=False)
                        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                        angle = imaging.detect_skew(img)
                    if abs(angle) >= params.min_angle:
                        # Same page size; the content is turned around its centre.
                        new = out.new_page(width=page.rect.width, height=page.rect.height)
                        new.draw_rect(new.rect, color=None, fill=(1, 1, 1), width=0)
                        new.show_pdf_page(new.rect, src, pno, rotate=angle, keep_proportion=True)
                        fixed.append({"page": pno + 1, "degrees": angle})
                    else:
                        out.insert_pdf(src, from_page=pno, to_page=pno)
                    ctx.progress((pno + 1) / src.page_count, "")
                if not fixed:
                    raise UserError(
                        "Düzeltilecek eğik sayfa bulunamadı.",
                        "No tilted pages were found.",
                    )
                save_pdf(out, ctx.output(f"{inp.stem}_duz.pdf"))
            finally:
                out.close()
        ctx.data = {"straightened": fixed}
