"""Page-level operations: merge, split, extract, rotate, delete, reorder."""

from __future__ import annotations

from typing import Literal

import pymupdf

from ..core.errors import UserError
from ..core.pdf import open_pdf, parse_page_spec, save_pdf
from .base import Context, Field, Operation, Params, register


class MergeParams(Params):
    bookmarks: bool = Field(
        True,
        tr="Her dosya için yer imi ekle",
        en="Add a bookmark per file",
    )


@register
class Merge(Operation):
    name = "merge"
    category = "pages"
    title_tr, title_en = "PDF Birleştir", "Merge PDFs"
    description_tr = "Birden fazla PDF'i seçtiğiniz sırayla tek dosyada birleştirir."
    description_en = "Combine several PDFs into one, in the order you choose."
    min_inputs, max_inputs = 2, 200
    Params = MergeParams

    def run(self, ctx: Context, params: MergeParams) -> None:
        out = pymupdf.open()
        toc: list[list[object]] = []
        try:
            for i, inp in enumerate(ctx.inputs):
                with open_pdf(inp.path, inp.password) as src:
                    start = out.page_count
                    out.insert_pdf(src)
                    if params.bookmarks:
                        toc.append([1, inp.stem, start + 1])
                    # Keep each source's own outline, nested under its file.
                    for level, title, page, *_ in src.get_toc(simple=True) if params.bookmarks else []:
                        toc.append([level + 1, title, start + page])
                ctx.progress((i + 1) / len(ctx.inputs), inp.name)
            if toc:
                out.set_toc(toc)
            save_pdf(out, ctx.output(f"{ctx.inputs[0].stem}_birlesik.pdf"))
        finally:
            out.close()


class SplitParams(Params):
    mode: Literal["ranges", "every", "each"] = Field(
        "ranges",
        tr="Bölme şekli",
        en="Split mode",
        ui={
            "options": {
                "ranges": {"tr": "Aralıklara göre", "en": "By ranges"},
                "every": {"tr": "Her N sayfada", "en": "Every N pages"},
                "each": {"tr": "Her sayfa ayrı", "en": "One file per page"},
            }
        },
    )
    ranges: str = Field(
        "",
        tr="Aralıklar",
        en="Ranges",
        help_tr="Her virgül ayrı dosya: 1-3, 4-6, 7-",
        help_en="Each comma is a separate file: 1-3, 4-6, 7-",
        max_length=2000,
        ui={"show_if": {"mode": "ranges"}},
    )
    every: int = Field(
        1, tr="Sayfa sayısı (N)", en="Pages per file (N)", ge=1, le=10_000, ui={"show_if": {"mode": "every"}}
    )


@register
class Split(Operation):
    name = "split"
    category = "pages"
    title_tr, title_en = "PDF Böl", "Split PDF"
    description_tr = "Bir PDF'i aralıklara, sabit sayfa sayısına veya tek tek sayfalara böler."
    description_en = "Split a PDF by ranges, every N pages, or into single pages."
    Params = SplitParams

    def run(self, ctx: Context, params: SplitParams) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as src:
            n = src.page_count
            groups: list[list[int]]
            if params.mode == "ranges":
                parts = [p for p in params.ranges.split(",") if p.strip()]
                if not parts:
                    raise UserError("En az bir aralık girin.", "Enter at least one range.")
                groups = [parse_page_spec(p, n) for p in parts]
            else:
                step = 1 if params.mode == "each" else params.every
                groups = [list(range(i, min(i + step, n))) for i in range(0, n, step)]
            if len(groups) > 5000:
                raise UserError("Çok fazla parça (en çok 5000).", "Too many parts (max 5000).")
            for gi, pages in enumerate(groups):
                part = pymupdf.open()
                try:
                    for p in pages:
                        part.insert_pdf(src, from_page=p, to_page=p)
                    label = f"{pages[0] + 1}" if len(pages) == 1 else f"{pages[0] + 1}-{pages[-1] + 1}"
                    save_pdf(part, ctx.output(f"{inp.stem}_s{label}.pdf"))
                finally:
                    part.close()
                ctx.progress((gi + 1) / len(groups), "")


class PagesParams(Params):
    pages: str = Field(
        "",
        tr="Sayfalar",
        en="Pages",
        help_tr="Örn: 1-3,5,8-son",
        help_en="e.g. 1-3,5,8-last",
        max_length=2000,
    )


def _select(ctx: Context, spec: str, *, keep: bool, suffix: str) -> None:
    inp = ctx.inputs[0]
    with open_pdf(inp.path, inp.password) as doc:
        chosen = parse_page_spec(spec, doc.page_count)
        if keep:
            doc.select(chosen)
        else:
            drop = set(chosen)
            remaining = [i for i in range(doc.page_count) if i not in drop]
            if not remaining:
                raise UserError("Tüm sayfalar silinemez.", "You cannot delete every page.")
            doc.select(remaining)
        save_pdf(doc, ctx.output(f"{inp.stem}_{suffix}.pdf"))


@register
class Extract(Operation):
    name = "extract_pages"
    category = "pages"
    title_tr, title_en = "Sayfa Çıkar", "Extract Pages"
    description_tr = "Seçtiğiniz sayfalardan yeni bir PDF oluşturur."
    description_en = "Create a new PDF from the pages you pick."
    Params = PagesParams

    def run(self, ctx: Context, params: PagesParams) -> None:
        if not params.pages.strip():
            raise UserError("Sayfa seçin.", "Choose pages.")
        _select(ctx, params.pages, keep=True, suffix="sayfalar")


@register
class Delete(Operation):
    name = "delete_pages"
    category = "pages"
    title_tr, title_en = "Sayfa Sil", "Delete Pages"
    description_tr = "Seçtiğiniz sayfaları PDF'ten kaldırır."
    description_en = "Remove the pages you pick from the PDF."
    Params = PagesParams

    def run(self, ctx: Context, params: PagesParams) -> None:
        if not params.pages.strip():
            raise UserError("Silinecek sayfaları seçin.", "Choose pages to delete.")
        _select(ctx, params.pages, keep=False, suffix="silindi")


class ReorderParams(Params):
    order: str = Field(
        ...,
        tr="Yeni sıra",
        en="New order",
        help_tr="Tüm sayfaları yeni sırayla yazın, örn: 3,1,2,4-son. Tekrar = kopya.",
        help_en="List pages in the new order, e.g. 3,1,2,4-last. Repeats duplicate a page.",
        min_length=1,
        max_length=2000,
    )


@register
class Reorder(Operation):
    name = "reorder"
    category = "pages"
    title_tr, title_en = "Sayfa Sırala", "Reorder Pages"
    description_tr = "Sayfaların sırasını değiştirir; tekrar eden sayfa kopyalanır."
    description_en = "Change page order; a repeated page is duplicated."
    Params = ReorderParams

    def run(self, ctx: Context, params: ReorderParams) -> None:
        _select(ctx, params.order, keep=True, suffix="sirali")


class RotateParams(Params):
    angle: Literal[90, 180, 270] = Field(
        90,
        tr="Açı",
        en="Angle",
        ui={
            "options": {
                "90": {"tr": "90° saat yönü", "en": "90° clockwise"},
                "180": {"tr": "180°", "en": "180°"},
                "270": {"tr": "90° saat yönü tersi", "en": "90° counter-clockwise"},
            }
        },
    )
    pages: str = Field("", tr="Sayfalar (boş = tümü)", en="Pages (empty = all)", max_length=2000)


@register
class Rotate(Operation):
    name = "rotate"
    category = "pages"
    title_tr, title_en = "Döndür", "Rotate"
    description_tr = "Sayfaları 90° adımlarla döndürür."
    description_en = "Rotate pages in 90° steps."
    Params = RotateParams

    def run(self, ctx: Context, params: RotateParams) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            for i in set(parse_page_spec(params.pages, doc.page_count)):
                page = doc[i]
                page.set_rotation((page.rotation + params.angle) % 360)
            save_pdf(doc, ctx.output(f"{inp.stem}_donduruldu.pdf"))
