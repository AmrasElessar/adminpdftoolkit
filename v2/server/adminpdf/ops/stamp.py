"""Stamping: watermark, header/footer, page numbers."""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Literal

import pymupdf

from ..core.errors import UserError
from ..core.pdf import open_pdf, parse_page_spec, save_pdf, unicode_font, unicode_font_path
from .base import Context, Field, InputFile, Operation, Params, register

_TOKEN_RE = re.compile(r"\{(n|total|date|file)\}")


def parse_color(value: str) -> tuple[float, float, float]:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", value.strip())
    if not m:
        raise UserError("Renk #RRGGBB biçiminde olmalı.", "Colour must be #RRGGBB.")
    h = m.group(1)
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)


def render_template(template: str, *, n: int, total: int, inp: InputFile) -> str:
    """Substitute only known tokens. Never ``str.format`` — a user-supplied
    format spec like ``{n:>999999999}`` would allocate gigabytes."""
    values = {"n": str(n), "total": str(total), "date": _dt.date.today().strftime("%d.%m.%Y"), "file": inp.stem}
    return _TOKEN_RE.sub(lambda m: values[m.group(1)], template)


_COLOR: dict[str, Any] = {"pattern": r"^#?[0-9a-fA-F]{6}$", "ui": {"widget": "color"}}


class WatermarkParams(Params):
    text: str = Field(..., tr="Metin", en="Text", min_length=1, max_length=200)
    font_size: int = Field(60, tr="Yazı boyutu", en="Font size", ge=6, le=300)
    color: str = Field("#888888", tr="Renk", en="Colour", **_COLOR)
    opacity: float = Field(0.25, tr="Saydamlık", en="Opacity", ge=0.02, le=1.0, ui={"widget": "range", "step": 0.01})
    rotation: int = Field(45, tr="Açı", en="Angle", ge=-180, le=180)
    pages: str = Field("", tr="Sayfalar (boş = tümü)", en="Pages (empty = all)", max_length=2000)
    behind: bool = Field(False, tr="İçeriğin arkasına yerleştir", en="Place behind content")


@register
class Watermark(Operation):
    name = "watermark"
    category = "stamp"
    title_tr, title_en = "Filigran", "Watermark"
    description_tr = "Sayfaların ortasına istediğiniz açıda yarı saydam metin basar."
    description_en = "Stamp semi-transparent text across the centre of each page at any angle."
    Params = WatermarkParams

    def run(self, ctx: Context, params: WatermarkParams) -> None:
        color = parse_color(params.color)
        font = unicode_font()
        width = font.text_length(params.text, fontsize=params.font_size)
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            targets = sorted(set(parse_page_spec(params.pages, doc.page_count)))
            for k, i in enumerate(targets):
                page = doc[i]
                rect = page.rect
                center = pymupdf.Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
                tw = pymupdf.TextWriter(rect, color=color)
                tw.append(
                    pymupdf.Point(center.x - width / 2, center.y + params.font_size / 3),
                    params.text,
                    font=font,
                    fontsize=params.font_size,
                )
                # Undo the page's own rotation so the stamp reads the same
                # way the user sees the page.
                matrix = pymupdf.Matrix(-params.rotation) * page.derotation_matrix
                tw.write_text(page, opacity=params.opacity, morph=(center, matrix), overlay=not params.behind)
                ctx.progress((k + 1) / len(targets), "")
            save_pdf(doc, ctx.output(f"{inp.stem}_filigran.pdf"))


class HeaderFooterParams(Params):
    header_left: str = Field("", tr="Üst sol", en="Header left", max_length=200)
    header_center: str = Field("", tr="Üst orta", en="Header centre", max_length=200)
    header_right: str = Field("", tr="Üst sağ", en="Header right", max_length=200)
    footer_left: str = Field("", tr="Alt sol", en="Footer left", max_length=200)
    footer_center: str = Field(
        "{n} / {total}",
        tr="Alt orta",
        en="Footer centre",
        help_tr="Kullanılabilir: {n} sayfa no, {total} toplam, {date} tarih, {file} dosya adı",
        help_en="Available: {n} page no, {total} total, {date} date, {file} file name",
        max_length=200,
    )
    footer_right: str = Field("", tr="Alt sağ", en="Footer right", max_length=200)
    font_size: float = Field(10, tr="Yazı boyutu", en="Font size", ge=4, le=72)
    color: str = Field("#000000", tr="Renk", en="Colour", **_COLOR)
    margin: float = Field(24, tr="Kenar boşluğu (pt)", en="Margin (pt)", ge=0, le=200)
    start_at: int = Field(1, tr="İlk sayfa numarası", en="First page number", ge=-100_000, le=1_000_000)
    pages: str = Field("", tr="Sayfalar (boş = tümü)", en="Pages (empty = all)", max_length=2000)


def stamp_header_footer(ctx: Context, p: HeaderFooterParams, suffix: str) -> None:
    color = parse_color(p.color)
    font = unicode_font()
    inp = ctx.inputs[0]
    slots = {
        ("top", "left"): p.header_left,
        ("top", "center"): p.header_center,
        ("top", "right"): p.header_right,
        ("bottom", "left"): p.footer_left,
        ("bottom", "center"): p.footer_center,
        ("bottom", "right"): p.footer_right,
    }
    slots = {k: v for k, v in slots.items() if v.strip()}
    if not slots:
        raise UserError("En az bir alan doldurun.", "Fill in at least one field.")
    font_path = unicode_font_path()
    fontname = "apt-uni" if font_path else "helv"
    with open_pdf(inp.path, inp.password) as doc:
        total = doc.page_count
        targets = sorted(set(parse_page_spec(p.pages, total)))
        for k, i in enumerate(targets):
            page = doc[i]
            # ``page.rect`` is the frame the reader sees (after /Rotate). Lay
            # out there, then map each point back to unrotated page space.
            vis = page.rect
            for (vpos, hpos), template in slots.items():
                text = render_template(template, n=p.start_at + i, total=total, inp=inp)
                w = font.text_length(text, fontsize=p.font_size)
                x = {
                    "left": vis.x0 + p.margin,
                    "center": (vis.x0 + vis.x1 - w) / 2,
                    "right": vis.x1 - p.margin - w,
                }[hpos]
                y = vis.y0 + p.margin + p.font_size if vpos == "top" else vis.y1 - p.margin
                page.insert_text(
                    pymupdf.Point(x, y) * page.derotation_matrix,
                    text,
                    fontsize=p.font_size,
                    fontname=fontname,
                    fontfile=font_path,
                    color=color,
                    rotate=page.rotation,
                )
            ctx.progress((k + 1) / len(targets), "")
        save_pdf(doc, ctx.output(f"{inp.stem}_{suffix}.pdf"))


@register
class HeaderFooter(Operation):
    name = "header_footer"
    category = "stamp"
    title_tr, title_en = "Üst / Alt Bilgi", "Header & Footer"
    description_tr = "Sayfaların üstüne ve altına sayfa numarası, tarih veya metin ekler."
    description_en = "Add page numbers, dates or text to the top and bottom of pages."
    Params = HeaderFooterParams

    def run(self, ctx: Context, params: HeaderFooterParams) -> None:
        stamp_header_footer(ctx, params, "ust_alt_bilgi")


class PageNumberParams(Params):
    position: Literal["bottom-center", "bottom-right", "bottom-left", "top-center", "top-right", "top-left"] = Field(
        "bottom-center",
        tr="Konum",
        en="Position",
        ui={
            "options": {
                "bottom-center": {"tr": "Alt orta", "en": "Bottom centre"},
                "bottom-right": {"tr": "Alt sağ", "en": "Bottom right"},
                "bottom-left": {"tr": "Alt sol", "en": "Bottom left"},
                "top-center": {"tr": "Üst orta", "en": "Top centre"},
                "top-right": {"tr": "Üst sağ", "en": "Top right"},
                "top-left": {"tr": "Üst sol", "en": "Top left"},
            }
        },
    )
    template: str = Field(
        "{n}",
        tr="Biçim",
        en="Format",
        help_tr="{n} sayfa no, {total} toplam — örn: Sayfa {n} / {total}",
        help_en="{n} page no, {total} total — e.g. Page {n} of {total}",
        max_length=100,
    )
    start_at: int = Field(1, tr="İlk numara", en="Start at", ge=-100_000, le=1_000_000)
    font_size: float = Field(10, tr="Yazı boyutu", en="Font size", ge=4, le=72)
    pages: str = Field("", tr="Sayfalar (boş = tümü)", en="Pages (empty = all)", max_length=2000)


@register
class PageNumbers(Operation):
    name = "page_numbers"
    category = "stamp"
    title_tr, title_en = "Sayfa Numarası", "Page Numbers"
    description_tr = "Seçtiğiniz konuma sayfa numarası ekler."
    description_en = "Add page numbers at the position you choose."
    Params = PageNumberParams

    def run(self, ctx: Context, params: PageNumberParams) -> None:
        vpos, hpos = params.position.split("-")
        key = ("header_" if vpos == "top" else "footer_") + hpos
        fields: dict[str, Any] = {"footer_center": "", key: params.template}
        hf = HeaderFooterParams(font_size=params.font_size, start_at=params.start_at, pages=params.pages, **fields)
        stamp_header_footer(ctx, hf, "numarali")
