"""PDF editor operations: read text spans, list annotations, apply edits.

These are hidden tools driven by the editor UI. All coordinates are PDF user
space (see :mod:`adminpdf.core.editing`); pages are 1-based; colours are
``#RRGGBB``; opacity is 0–1.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import html
import io
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

import pymupdf
from pydantic import BaseModel, ConfigDict, model_validator
from pydantic import Field as PField

from ..core.editing import (
    BackgroundSampler,
    Char,
    FontCache,
    Line,
    PageGeom,
    Run,
    WriteFont,
    color_to_hex,
    dir_angle,
    embedded_font_names,
    extract_embedded_font,
    font_key,
    hex_to_rgb,
    int_to_hex,
    is_bold,
    is_italic,
    match_run,
    page_lines,
    union,
)
from ..core.errors import UserError
from ..core.fonts import Catalogue, get_catalogue
from ..core.pdf import open_pdf, parse_page_spec, save_pdf
from .base import Context, Field, Operation, Params, register

log = logging.getLogger("adminpdf.editor")

MAX_PAGES_PER_REQUEST = 200
MAX_SPANS = 200_000
MAX_ANNOTATIONS = 50_000
MAX_OPERATIONS = 20_000
MAX_TEXT = 20_000
MAX_INK_POINTS = 100_000
MAX_INK_POINTS_TOTAL = 500_000
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_DATA_URL_CHARS = MAX_IMAGE_BYTES * 4 // 3 + 64
MAX_DATA_URL_TOTAL = 64 * 1024 * 1024
MAX_REPLACE_CHARS_PER_PAGE = 100_000


# -- shared value types -----------------------------------------------------------------
Num = Annotated[float, PField(ge=-1e6, le=1e6, allow_inf_nan=False)]
PointT = tuple[Num, Num]
RectT = tuple[Num, Num, Num, Num]
QuadT = tuple[PointT, PointT, PointT, PointT]
Color = Annotated[str, PField(pattern=r"^#[0-9a-fA-F]{6}$")]
Opacity = Annotated[float, PField(ge=0.0, le=1.0, allow_inf_nan=False)]
PageNo = Annotated[int, PField(ge=1, le=1_000_000)]
Xref = Annotated[int, PField(ge=1, le=100_000_000)]
Rotation = Literal[0, 90, 180, 270]
Author = Annotated[str, PField(max_length=200)]
ShortId = Annotated[str, PField(max_length=200)]


class FontRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    family_id: ShortId
    weight: int = PField(400, ge=100, le=900)
    italic: bool = False


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, populate_by_name=True)
    page: PageNo


class TextOp(_Op):
    """New text box: wraps inside ``rect``; embeds (a subset of) the font."""

    type: Literal["text"]
    rect: RectT
    text: str = PField(min_length=1, max_length=MAX_TEXT)
    font: FontRef | None = None
    font_id: ShortId | None = None
    size: float = PField(12, ge=1, le=500, allow_inf_nan=False)
    color: Color = "#000000"
    align: Literal["left", "center", "right", "justify"] = "left"
    opacity: Opacity = 1.0
    rotation: Rotation = 0
    line_height: float = PField(1.2, ge=0.5, le=5, allow_inf_nan=False)
    shrink_to_fit: bool = True


class ReplaceOp(_Op):
    """Replace existing text: ``rect`` is the original text's bbox. Unset
    font/size/colour default to what was detected there."""

    type: Literal["replace"]
    rect: RectT
    text: str = PField("", max_length=MAX_TEXT)
    font: FontRef | None = None
    font_id: ShortId | None = None
    size: float | None = PField(None, ge=1, le=500, allow_inf_nan=False)
    color: Color | None = None
    background: Literal["auto", "none"] | Color = "auto"
    opacity: Opacity = 1.0
    shrink_to_fit: bool = True


class WhiteoutOp(_Op):
    type: Literal["whiteout"]
    rect: RectT
    color: Color = "#FFFFFF"


class ShapeOp(_Op):
    type: Literal["rect", "ellipse"]
    rect: RectT
    stroke: Color | None = "#000000"
    fill: Color | None = None
    width: float = PField(1.0, ge=0, le=100, allow_inf_nan=False)
    opacity: Opacity = 1.0
    author: Author = ""


class LineOp(_Op):
    type: Literal["line", "arrow"]
    from_: PointT = PField(alias="from")
    to: PointT
    color: Color = "#000000"
    width: float = PField(1.0, ge=0.1, le=100, allow_inf_nan=False)
    opacity: Opacity = 1.0
    head_start: bool | None = None  # default: line → no, arrow → no
    head_end: bool | None = None  # default: line → no, arrow → yes
    author: Author = ""


class InkOp(_Op):
    type: Literal["ink"]
    paths: list[list[PointT]] = PField(min_length=1, max_length=5000)
    color: Color = "#000000"
    width: float = PField(1.5, ge=0.1, le=100, allow_inf_nan=False)
    opacity: Opacity = 1.0
    author: Author = ""

    @model_validator(mode="after")
    def _points(self) -> InkOp:
        if any(not p for p in self.paths):
            raise ValueError("every path needs at least one point")
        if sum(len(p) for p in self.paths) > MAX_INK_POINTS:
            raise ValueError(f"at most {MAX_INK_POINTS} points per ink operation")
        return self


class MarkupOp(_Op):
    """Text markup. ``quads`` corners are upper-left, upper-right,
    lower-left, lower-right as the reader sees the text."""

    type: Literal["highlight", "underline", "strikeout", "squiggly"]
    rects: list[RectT] = PField(default_factory=list, max_length=10_000)
    quads: list[QuadT] = PField(default_factory=list, max_length=10_000)
    color: Color | None = None
    opacity: Opacity = 1.0
    author: Author = ""

    @model_validator(mode="after")
    def _some(self) -> MarkupOp:
        if not self.rects and not self.quads:
            raise ValueError("give rects or quads")
        return self


class NoteOp(_Op):
    type: Literal["note"]
    point: PointT
    text: str = PField(min_length=1, max_length=MAX_TEXT)
    color: Color = "#FFD400"
    author: Author = ""


class FreeTextOp(_Op):
    type: Literal["freetext"]
    rect: RectT
    text: str = PField(min_length=1, max_length=MAX_TEXT)
    size: float = PField(12, ge=4, le=200, allow_inf_nan=False)
    color: Color = "#000000"
    fill: Color | None = None
    border: Color | None = None
    border_width: float = PField(0, ge=0, le=20, allow_inf_nan=False)
    align: Literal["left", "center", "right"] = "left"
    opacity: Opacity = 1.0
    author: Author = ""


class ImageOp(_Op):
    type: Literal["image"]
    rect: RectT
    data_url: str = PField(max_length=MAX_DATA_URL_CHARS)
    opacity: Opacity = 1.0
    rotation: Rotation = 0


_URI_RE = re.compile(r"^(https?://|mailto:)[^\s\x00-\x1f\x7f]+$", re.IGNORECASE)


class LinkOp(_Op):
    type: Literal["link"]
    rect: RectT
    uri: str | None = PField(None, max_length=2048)
    target_page: int | None = PField(None, ge=1, le=1_000_000)

    @model_validator(mode="after")
    def _target(self) -> LinkOp:
        if (self.uri is None) == (self.target_page is None):
            raise ValueError("give exactly one of uri or target_page")
        if self.uri is not None and not _URI_RE.match(self.uri):
            raise ValueError("uri must be http://, https:// or mailto:")
        return self


class DeleteAnnotOp(_Op):
    type: Literal["delete_annot"]
    xref: Xref


class MoveAnnotOp(_Op):
    type: Literal["move_annot"]
    xref: Xref
    rect: RectT


class UpdateAnnotOp(_Op):
    type: Literal["update_annot"]
    xref: Xref
    rect: RectT | None = None
    color: Color | None = None
    fill: Color | None = None
    contents: str | None = PField(None, max_length=MAX_TEXT)
    opacity: Opacity | None = None
    author: Author | None = None


EditOp = Annotated[
    TextOp
    | ReplaceOp
    | WhiteoutOp
    | ShapeOp
    | LineOp
    | InkOp
    | MarkupOp
    | NoteOp
    | FreeTextOp
    | ImageOp
    | LinkOp
    | DeleteAnnotOp
    | MoveAnnotOp
    | UpdateAnnotOp,
    PField(discriminator="type"),
]


# -- text_spans ---------------------------------------------------------------------------
class TextSpansParams(Params):
    pages: str = Field("", tr="Sayfalar (boş = tümü)", en="Pages (empty = all)", max_length=2000)
    granularity: Literal["word", "line", "block"] = Field(
        "line",
        tr="Birim",
        en="Granularity",
        ui={
            "options": {
                "word": {"tr": "Kelime", "en": "Word"},
                "line": {"tr": "Satır", "en": "Line"},
                "block": {"tr": "Paragraf", "en": "Block"},
            }
        },
    )


def _target_pages(spec: str, page_count: int) -> list[int]:
    pages = list(dict.fromkeys(parse_page_spec(spec, page_count)))
    if len(pages) > MAX_PAGES_PER_REQUEST:
        raise UserError(
            f"Tek istekte en fazla {MAX_PAGES_PER_REQUEST} sayfa okunabilir.",
            f"At most {MAX_PAGES_PER_REQUEST} pages per request.",
        )
    return pages


@dataclass
class _SpanBuilder:
    page: pymupdf.Page
    geom: PageGeom
    cat: Catalogue
    sampler: BackgroundSampler
    embedded: set[str]
    matches: dict[tuple[str, int], dict[str, Any]] = field(default_factory=dict)

    def make(self, sid: str, chars: list[Char], run: Run, line: Line, text: str) -> dict[str, Any] | None:
        ink = [c for c in chars if not c.c.isspace()]
        text = text.strip()
        if not ink or not text:
            return None
        rect = union([c.bbox for c in ink])
        key = (run.font, run.flags)
        matched = self.matches.get(key)
        if matched is None:
            matched = self.matches[key] = match_run(self.cat, run)
        dx, dy = line.dir
        return {
            "id": sid,
            "text": text,
            "rect": self.geom.pdf_rect(rect),
            "origin": self.geom.pdf_point(ink[0].origin),
            "dir": [round(dx, 4), round(-dy, 4)],
            "font": run.font,
            "size": round(run.size, 2),
            "color": int_to_hex(run.color),
            "bold": is_bold(run.flags) or matched["weight"] >= 600,
            "italic": is_italic(run.flags) or bool(matched["italic"]),
            "matched_font": matched,
            "background": self.sampler.around(rect),
            "embedded": font_key(run.font) in self.embedded,
        }


def _dominant(runs: list[Run]) -> Run:
    return max(runs, key=lambda r: sum(1 for c in r.chars if not c.c.isspace()))


def _line_text(line: Line) -> str:
    return "".join(c.c for r in line.runs for c in r.chars)


def extract_spans(b: _SpanBuilder, pno: int, granularity: str, budget: int) -> list[dict[str, Any]]:
    lines = page_lines(b.page)
    out: list[dict[str, Any]] = []

    def add(span: dict[str, Any] | None) -> bool:
        if span is not None:
            out.append(span)
        return len(out) < budget

    if granularity == "block":
        blocks: dict[int, list[Line]] = {}
        for ln in lines:
            blocks.setdefault(ln.block, []).append(ln)
        for b_idx, group in blocks.items():
            chars = [c for ln in group for r in ln.runs for c in r.chars]
            text = "\n".join(_line_text(ln).strip() for ln in group if _line_text(ln).strip())
            run = _dominant([r for ln in group for r in ln.runs])
            if not add(b.make(f"{pno}-{b_idx}", chars, run, group[0], text)):
                break
        return out
    for ln in lines:
        if granularity == "line":
            chars = [c for r in ln.runs for c in r.chars]
            if not add(b.make(f"{pno}-{ln.block}-{ln.index}", chars, _dominant(ln.runs), ln, _line_text(ln))):
                return out
            continue
        for r_idx, run in enumerate(ln.runs):
            word: list[Char] = []
            w_idx = 0
            for ch in [*run.chars, Char(" ", pymupdf.Rect(), pymupdf.Point())]:
                if not ch.c.isspace():
                    word.append(ch)
                    continue
                if word:
                    sid = f"{pno}-{ln.block}-{ln.index}-{r_idx}-{w_idx}"
                    if not add(b.make(sid, word, run, ln, "".join(c.c for c in word))):
                        return out
                    w_idx += 1
                    word = []
    return out


def _page_spans(page: pymupdf.Page, cat: Catalogue, granularity: str, budget: int) -> dict[str, Any]:
    geom = PageGeom(page)
    spans: list[dict[str, Any]] = []
    if budget > 0:
        builder = _SpanBuilder(page, geom, cat, BackgroundSampler(page), embedded_font_names(page))
        spans = extract_spans(builder, page.number + 1, granularity, budget)
    return {"page": page.number + 1, **geom.page_info(), "spans": spans}


@register
class TextSpans(Operation):
    name = "text_spans"
    category = "edit"
    title_tr, title_en = "Metin Parçaları", "Text Spans"
    description_tr = "Düzenleyici için sayfalardaki metinleri konum, yazı tipi ve renk bilgisiyle listeler."
    description_en = "List the text on pages with position, font and colour for the editor."
    Params = TextSpansParams
    returns_data = True
    hidden = True

    def run(self, ctx: Context, params: TextSpansParams) -> None:
        cat = get_catalogue()
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            targets = _target_pages(params.pages, doc.page_count)
            pages: list[dict[str, Any]] = []
            total = 0
            truncated = False
            for k, i in enumerate(targets):
                entry = _page_spans(doc[i], cat, params.granularity, 0 if truncated else MAX_SPANS - total)
                total += len(entry["spans"])
                truncated = truncated or total >= MAX_SPANS
                pages.append(entry)
                ctx.progress((k + 1) / len(targets), "")
            ctx.data = {"pages": pages, "truncated": truncated}


# -- annotations ---------------------------------------------------------------------------
class AnnotationsParams(Params):
    pages: str = Field("", tr="Sayfalar (boş = tümü)", en="Pages (empty = all)", max_length=2000)


_PDF_DATE = re.compile(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?(?:([Zz+\-])(\d{2})?'?(\d{2})?'?)?")


def pdf_date_iso(value: str | None) -> str:
    """``D:20261025143000+03'00'`` → ``2026-10-25T14:30:00+03:00`` ("" if unparsable)."""
    m = _PDF_DATE.match((value or "").strip())
    if not m:
        return ""
    y, mo, d, h, mi, s, sign, tzh, tzm = m.groups()
    out = f"{y}-{mo or '01'}-{d or '01'}T{h or '00'}:{mi or '00'}:{s or '00'}"
    if sign in ("Z", "z"):
        out += "Z"
    elif sign:
        out += f"{sign}{tzh or '00'}:{tzm or '00'}"
    return out


_SKIP_ANNOTS = frozenset({"Popup", "Widget", "Link"})
_POINT_ANNOTS = frozenset({"Line", "Polygon", "PolyLine", "Highlight", "Underline", "StrikeOut", "Squiggly"})


def describe_annot(geom: PageGeom, annot: Any) -> dict[str, Any]:
    kind = str(annot.type[1])
    info = annot.info or {}
    colors = annot.colors or {}
    opacity = float(annot.opacity)
    entry: dict[str, Any] = {
        "xref": int(annot.xref),
        "type": kind,
        "rect": geom.pdf_rect(annot.rect),
        "color": color_to_hex(colors.get("stroke")),
        "fill": color_to_hex(colors.get("fill")),
        "opacity": round(opacity, 3) if 0 <= opacity <= 1 else 1.0,
        "contents": str(info.get("content") or "")[:MAX_TEXT],
        "author": str(info.get("title") or "")[:200],
        "subject": str(info.get("subject") or "")[:200],
        "modified": pdf_date_iso(info.get("modDate")),
        "created": pdf_date_iso(info.get("creationDate")),
    }
    if kind == "FreeText":
        # /C is the box background here; text colour and size live in /DA.
        entry["fill"] = color_to_hex(colors.get("stroke"))
        entry["color"] = None
        _typ, da = geom.page.parent.xref_get_key(annot.xref, "DA")
        rgb = re.search(r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+rg", da or "")
        gray = re.search(r"([\d.]+)\s+g(?:\s|$)", da or "")
        if rgb:
            entry["color"] = color_to_hex([float(v) for v in rgb.groups()])
        elif gray:
            entry["color"] = color_to_hex([float(gray.group(1))])
        size = re.search(r"([\d.]+)\s+Tf", da or "")
        if size:
            entry["size"] = float(size.group(1))
    vertices = annot.vertices or []
    if kind == "Ink":
        entry["paths"] = [[geom.pdf_point(p) for p in path] for path in vertices]
    elif kind in _POINT_ANNOTS:
        entry["points"] = [geom.pdf_point(p) for p in vertices]
    return entry


@register
class Annotations(Operation):
    name = "annotations"
    category = "edit"
    title_tr, title_en = "Açıklamalar", "Annotations"
    description_tr = "Sayfalardaki açıklamaları (vurgu, not, çizim…) konumlarıyla listeler."
    description_en = "List the annotations (highlights, notes, drawings…) on pages with their positions."
    Params = AnnotationsParams
    returns_data = True
    hidden = True

    def run(self, ctx: Context, params: AnnotationsParams) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            targets = list(dict.fromkeys(parse_page_spec(params.pages, doc.page_count)))
            pages: list[dict[str, Any]] = []
            count = 0
            truncated = False
            for i in targets:
                entry, more = _page_annotations(doc[i], MAX_ANNOTATIONS - count)
                if entry["annotations"]:
                    pages.append(entry)
                    count += len(entry["annotations"])
                if more:
                    truncated = True
                    break
            ctx.data = {"pages": pages, "truncated": truncated}


def _page_annotations(page: pymupdf.Page, budget: int) -> tuple[dict[str, Any], bool]:
    """One page's annotations. Kept in its own frame so no annotation object
    outlives the document (PyMuPDF can crash on such dangling handles)."""
    geom = PageGeom(page)
    annots: list[dict[str, Any]] = []
    more = False
    for annot in page.annots():
        if str(annot.type[1]) in _SKIP_ANNOTS:
            continue
        if len(annots) >= budget:
            more = True
            break
        annots.append(describe_annot(geom, annot))
    return {"page": page.number + 1, **geom.page_info(), "annotations": annots}, more


# -- edit --------------------------------------------------------------------------------------
class EditParams(Params):
    operations: list[EditOp] = Field(..., tr="İşlemler", en="Operations", min_length=1, max_length=MAX_OPERATIONS)

    @model_validator(mode="after")
    def _totals(self) -> EditParams:
        ink = sum(sum(len(p) for p in op.paths) for op in self.operations if isinstance(op, InkOp))
        if ink > MAX_INK_POINTS_TOTAL:
            raise ValueError(f"at most {MAX_INK_POINTS_TOTAL} ink points in total")
        images = sum(len(op.data_url) for op in self.operations if isinstance(op, ImageOp))
        if images > MAX_DATA_URL_TOTAL:
            raise ValueError("images are too large in total")
        return self


@dataclass
class _EditState:
    doc: pymupdf.Document
    fonts: FontCache
    used_fonts: bool = False
    # (page number, font key) → resource name registered on that page
    page_fonts: dict[tuple[int, str], str] = field(default_factory=dict)
    images: dict[str, tuple[bytes, int]] = field(default_factory=dict)

    def register_font(self, page: pymupdf.Page, wf: WriteFont) -> str:
        key = (int(page.number), wf.key)
        name = self.page_fonts.get(key)
        if name is None:
            name = f"APT{len(self.page_fonts) + 1}"
            page.insert_font(fontname=name, fontbuffer=wf.buffer)
            self.page_fonts[key] = name
        self.used_fonts = True
        return name


def _rgb(value: str | None) -> tuple[float, float, float] | None:
    return hex_to_rgb(value) if value else None


def _require_rgb(value: str) -> tuple[float, float, float]:
    return hex_to_rgb(value)


# ---- text -------------------------------------------------------------------------------------
def _text_font(state: _EditState, font: FontRef | None, font_id: str | None) -> WriteFont:
    wf = state.fonts.from_ref(
        font.family_id if font else None, font.weight if font else 400, font.italic if font else False, font_id
    )
    if wf is None:
        std = state.fonts.cat.style("std-helv")
        assert std is not None
        wf = state.fonts.from_style(std)
    return wf


def apply_text(state: _EditState, page: pymupdf.Page, op: TextOp) -> None:
    geom = PageGeom(page)
    rect = geom.rect(op.rect, min_size=1)
    wf = _text_font(state, op.font, op.font_id)
    # Every face — catalogue TTF/OTF or the base-14 builtins (CFF) — goes in
    # through @font-face: MuPDF's generic "serif" etc. are different fonts.
    ext = "cff" if wf.base14 else "otf" if wf.buffer[:4] == b"OTTO" else "ttf"
    archive = pymupdf.Archive()
    archive.add(wf.buffer, f"face.{ext}")
    css = (
        f"@font-face {{font-family: aptface; src: url(face.{ext});}}\n"
        f"* {{font-family: aptface; font-size: {op.size:.2f}px; color: {op.color}; "
        f"text-align: {op.align}; line-height: {op.line_height:.3f}; white-space: pre-wrap; "
        "font-weight: normal; font-style: normal; margin: 0; padding: 0;}"
    )
    body = html.escape(op.text).replace("\r\n", "\n")
    spare, _scale = page.insert_htmlbox(
        rect,
        f"<div>{body}</div>",
        css=css,
        archive=archive,
        rotate=(page.rotation - op.rotation) % 360,
        opacity=op.opacity,
        scale_low=0 if op.shrink_to_fit else 1,
    )
    if spare < 0:
        raise UserError(
            "Metin kutuya sığmadı — kutuyu büyütün ya da 'sığdır' seçeneğini açın.",
            "The text does not fit — enlarge the box or enable shrink-to-fit.",
        )
    state.used_fonts = True


# ---- replace ----------------------------------------------------------------------------------
@dataclass
class _ReplacePlan:
    index: int
    op: ReplaceOp
    rect: pymupdf.Rect
    first: tuple[Char, Run, Line] | None
    line_gap: float | None
    zap: list[pymupdf.Rect]
    fills: list[pymupdf.Rect]
    fill: tuple[float, float, float] | None
    embedded: WriteFont | None


def _glyph_box(ch: Char, run: Run, line: Line) -> pymupdf.Rect:
    """Where a glyph's ink lives (baseline −0.25 em … +0.8 em), so a fill
    never reaches the ascenders/descenders of neighbouring lines."""
    dx, dy = line.dir
    ux, uy = dy, -dx  # towards the ascender
    adv = abs(dx) * ch.bbox.width + abs(dy) * ch.bbox.height
    s = run.size
    pts = []
    for along in (0.0, adv):
        bx, by = ch.origin.x + dx * along, ch.origin.y + dy * along
        for up in (-0.25 * s, 0.8 * s):
            pts.append(pymupdf.Point(bx + ux * up, by + uy * up))
    return pymupdf.Rect(min(p.x for p in pts), min(p.y for p in pts), max(p.x for p in pts), max(p.y for p in pts))


def _zap_rect(ch: Char) -> pymupdf.Rect:
    """A small square at the glyph centre. MuPDF removes every glyph whose
    box touches a redaction, so redacting whole line boxes would also eat
    parts of the neighbouring lines (their boxes overlap)."""
    c = pymupdf.Point((ch.bbox.x0 + ch.bbox.x1) / 2, (ch.bbox.y0 + ch.bbox.y1) / 2)
    half = max(0.05, 0.2 * min(ch.bbox.width, ch.bbox.height))
    return pymupdf.Rect(c.x - half, c.y - half, c.x + half, c.y + half)


def _plan_replace(
    state: _EditState,
    page: pymupdf.Page,
    geom: PageGeom,
    lines: list[Line],
    sampler: Callable[[], BackgroundSampler],
    index: int,
    op: ReplaceOp,
) -> _ReplacePlan:
    rect = geom.rect(op.rect)
    matched: list[tuple[Char, Run, Line]] = []
    for ln in lines:
        for run in ln.runs:
            for ch in run.chars:
                center = pymupdf.Point((ch.bbox.x0 + ch.bbox.x1) / 2, (ch.bbox.y0 + ch.bbox.y1) / 2)
                if rect.contains(center):
                    matched.append((ch, run, ln))
    if len(matched) > MAX_REPLACE_CHARS_PER_PAGE:
        raise UserError("Seçilen alan çok fazla metin içeriyor.", "The selected area holds too much text.")
    ink = [m for m in matched if not m[0].c.isspace()]
    first = ink[0] if ink else None
    fills: list[pymupdf.Rect] = []
    origins: list[pymupdf.Point] = []
    by_line: dict[int, list[tuple[Char, Run, Line]]] = {}
    for m in ink:
        by_line.setdefault(id(m[2]), []).append(m)
    margin = pymupdf.Rect(rect.x0 - 1, rect.y0 - 1, rect.x1 + 1, rect.y1 + 1)
    for group in by_line.values():
        fills.append(union([_glyph_box(*m) for m in group]) & margin)
        origins.append(group[0][0].origin)
    line_gap = None
    if first is not None and len(origins) >= 2:
        dx, dy = first[2].dir
        ux, uy = dy, -dx
        gap = abs((origins[1].x - origins[0].x) * ux + (origins[1].y - origins[0].y) * uy)
        line_gap = gap if gap > 0.5 else None
    if not ink:
        fills = [rect]
    fill: tuple[float, float, float] | None = None
    if op.background == "auto":
        fill = hex_to_rgb(sampler().around(rect))
    elif op.background != "none":
        fill = hex_to_rgb(op.background)
    embedded = None
    if first is not None and op.font is None and op.font_id is None and op.text.strip():
        found = extract_embedded_font(state.doc, page, first[1].font)
        if found:
            embedded = state.fonts.from_buffer(*found)
    return _ReplacePlan(
        index=index,
        op=op,
        rect=rect,
        first=first,
        line_gap=line_gap,
        zap=[_zap_rect(m[0]) for m in matched],
        fills=fills,
        fill=fill,
        embedded=embedded,
    )


def _replacement_font(state: _EditState, plan: _ReplacePlan, text: str) -> WriteFont:
    op = plan.op
    candidates: list[Callable[[], WriteFont | None]] = []
    if op.font is not None or op.font_id is not None:
        explicit = _text_font(state, op.font, op.font_id)  # raises for unknown/restricted
        candidates.append(lambda: explicit)
    else:
        candidates.append(lambda: plan.embedded)
        if plan.first is not None:
            run = plan.first[1]

            def matched() -> WriteFont | None:
                m = match_run(state.fonts.cat, run)
                return state.fonts.from_ref(m["family_id"], int(m["weight"]), bool(m["italic"]), None)

            candidates.append(matched)
    candidates.append(state.fonts.unicode_fallback)
    first_ok: WriteFont | None = None
    for make in candidates:
        try:
            wf = make()
        except UserError:
            continue
        if wf is None:
            continue
        if wf.covers(text):
            return wf
        first_ok = first_ok or wf
    if first_ok is None:
        raise UserError("Uygun yazı tipi bulunamadı.", "No usable font was found.")
    return first_ok


def _draw_replacement(state: _EditState, page: pymupdf.Page, geom: PageGeom, plan: _ReplacePlan) -> None:
    op = plan.op
    text = op.text.replace("\r\n", "\n")
    if not text.strip():
        return
    wf = _replacement_font(state, plan, text)
    rect = plan.rect
    if plan.first is not None:
        ch, run, line = plan.first
        size = op.size or run.size or 12.0
        color = _rgb(op.color) or hex_to_rgb(int_to_hex(run.color))
        dx, dy = line.dir
        origin = ch.origin
    else:
        d = geom.upright_dir()
        dx, dy = d.x, d.y
        vis = pymupdf.Rect(rect * page.rotation_matrix).normalize()
        size = op.size or max(4.0, min(72.0, vis.height * 0.75))
        color = _rgb(op.color) or (0.0, 0.0, 0.0)
        origin = pymupdf.Point(vis.x0, vis.y1 - 0.25 * size) * page.derotation_matrix
    gap = plan.line_gap or size * 1.2
    lines = text.split("\n")
    if op.shrink_to_fit:
        avail = abs(dx) * rect.width + abs(dy) * rect.height
        widest = max(wf.width(t, size) for t in lines)
        if widest > avail * 1.02 and widest > 0:
            factor = avail / widest
            size = max(2.0, size * factor)
            gap = max(2.0, gap * factor)
    name = state.register_font(page, wf)
    angle = dir_angle((dx, dy))
    page.insert_text(
        origin,
        text,
        fontsize=size,
        lineheight=gap / size,
        fontname=name,
        color=color,
        fill_opacity=op.opacity,
        morph=(origin, pymupdf.Matrix(angle)) if abs(angle) > 0.01 else None,
    )


def apply_replaces(
    state: _EditState, page: pymupdf.Page, items: list[tuple[int, ReplaceOp]]
) -> dict[int, UserError | None]:
    """All replace ops of one page share a single redaction pass, done
    before anything else touches the page (so it can't wipe new content)."""
    geom = PageGeom(page)
    results: dict[int, UserError | None] = {}
    lines = page_lines(page)
    sampler_cache: list[BackgroundSampler] = []

    def sampler() -> BackgroundSampler:
        if not sampler_cache:
            sampler_cache.append(BackgroundSampler(page))
        return sampler_cache[0]

    plans: list[_ReplacePlan] = []
    for index, op in items:
        try:
            plans.append(_plan_replace(state, page, geom, lines, sampler, index, op))
        except UserError as e:
            results[index] = e
        except Exception:
            log.exception("replace #%d planning failed", index)
            results[index] = _GENERIC
    zaps = [r for p in plans for r in p.zap]
    if zaps:
        for r in zaps:
            page.add_redact_annot(r, fill=False, cross_out=False)
        # Remove glyphs only: never touch images (v1 blanked their pixels) or
        # vector art (v1 erased table borders next to the edited text).
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )
    for plan in plans:
        try:
            if plan.fill is not None:
                for r in plan.fills:
                    if not r.is_empty:
                        page.draw_rect(r, color=None, fill=plan.fill, width=0, overlay=True)
            _draw_replacement(state, page, geom, plan)
            results[plan.index] = None
        except UserError as e:
            results[plan.index] = e
        except Exception:
            log.exception("replace #%d failed", plan.index)
            results[plan.index] = _GENERIC
    return results


# ---- simple content ops -------------------------------------------------------------------
def apply_whiteout(state: _EditState, page: pymupdf.Page, op: WhiteoutOp) -> None:
    rect = PageGeom(page).rect(op.rect)
    page.draw_rect(rect, color=None, fill=_require_rgb(op.color), width=0, overlay=True)


def _stamp_info(annot: Any, author: str) -> None:
    now = pymupdf.get_pdf_now()
    annot.set_info(title=author or None, creationDate=now, modDate=now)


def _finish_annot(annot: Any, *, opacity: float | None = None, author: str = "") -> None:
    if opacity is not None and opacity < 1:
        annot.set_opacity(opacity)
    _stamp_info(annot, author)
    annot.update()


def apply_shape(state: _EditState, page: pymupdf.Page, op: ShapeOp) -> None:
    rect = PageGeom(page).rect(op.rect)
    annot = page.add_rect_annot(rect) if op.type == "rect" else page.add_circle_annot(rect)
    stroke = _rgb(op.stroke)
    annot.set_colors(stroke=list(stroke) if stroke else [], fill=list(_rgb(op.fill) or ()) or [])
    annot.set_border(width=op.width if stroke else 0)
    _finish_annot(annot, opacity=op.opacity, author=op.author)


def apply_line(state: _EditState, page: pymupdf.Page, op: LineOp) -> None:
    geom = PageGeom(page)
    p1, p2 = geom.point(op.from_), geom.point(op.to)
    if abs(p1.x - p2.x) < 0.1 and abs(p1.y - p2.y) < 0.1:
        raise UserError("Çizginin başı ve sonu aynı.", "The line starts and ends at the same point.")
    annot = page.add_line_annot(p1, p2)
    annot.set_colors(stroke=list(_require_rgb(op.color)))
    annot.set_border(width=op.width)
    start = op.head_start if op.head_start is not None else False
    end = op.head_end if op.head_end is not None else op.type == "arrow"
    arrow, none = pymupdf.PDF_ANNOT_LE_OPEN_ARROW, pymupdf.PDF_ANNOT_LE_NONE
    if start or end:
        annot.set_line_ends(arrow if start else none, arrow if end else none)
    _finish_annot(annot, opacity=op.opacity, author=op.author)


def apply_ink(state: _EditState, page: pymupdf.Page, op: InkOp) -> None:
    geom = PageGeom(page)
    paths = []
    for path in op.paths:
        pts = [geom.point(p) for p in path]
        if len(pts) == 1:  # a dot
            pts.append(pymupdf.Point(pts[0].x + 0.01, pts[0].y))
        paths.append([(p.x, p.y) for p in pts])
    annot = page.add_ink_annot(paths)
    annot.set_colors(stroke=list(_require_rgb(op.color)))
    annot.set_border(width=op.width)
    _finish_annot(annot, opacity=op.opacity, author=op.author)


def apply_markup(state: _EditState, page: pymupdf.Page, op: MarkupOp) -> None:
    geom = PageGeom(page)
    quads = [geom.visual_quad(geom.rect(r, min_size=0.1)) for r in op.rects]
    for q in op.quads:
        ul, ur, ll, lr = (geom.point(p) for p in q)
        quads.append(pymupdf.Quad(ul, ur, ll, lr))
    add = {
        "highlight": page.add_highlight_annot,
        "underline": page.add_underline_annot,
        "strikeout": page.add_strikeout_annot,
        "squiggly": page.add_squiggly_annot,
    }[op.type]
    annot = add(quads=quads)
    if annot is None:
        raise UserError("İşaretleme eklenemedi.", "Could not add the markup.")
    if op.color:
        annot.set_colors(stroke=list(hex_to_rgb(op.color)))
    _finish_annot(annot, opacity=op.opacity, author=op.author)


def apply_note(state: _EditState, page: pymupdf.Page, op: NoteOp) -> None:
    point = PageGeom(page).point(op.point)
    annot = page.add_text_annot(point, op.text, icon="Note")
    annot.set_colors(stroke=list(_require_rgb(op.color)))
    _finish_annot(annot, author=op.author)


def apply_freetext(state: _EditState, page: pymupdf.Page, op: FreeTextOp) -> None:
    rect = PageGeom(page).rect(op.rect, min_size=2)
    annot = page.add_freetext_annot(
        rect,
        op.text,
        fontsize=op.size,
        text_color=_require_rgb(op.color),
        fill_color=_rgb(op.fill),
        border_color=_rgb(op.border),
        border_width=op.border_width if op.border else 0,
        opacity=op.opacity,
        align={"left": 0, "center": 1, "right": 2}[op.align],
        rotate=page.rotation,
    )
    _stamp_info(annot, op.author)


# ---- image ------------------------------------------------------------------------------------------
_DATA_URL = re.compile(r"data:image/(png|jpeg|jpg|webp);base64,(.*)", re.DOTALL | re.IGNORECASE)


def decode_image(data_url: str, opacity: float) -> bytes:
    """Validate a ``data:`` URL image and re-encode it (opacity baked into
    the alpha channel) — the PDF never carries the client's raw bytes."""
    from PIL import Image, UnidentifiedImageError

    m = _DATA_URL.fullmatch(data_url.strip())
    if not m:
        raise UserError(
            "Görsel data:image/png|jpeg|webp;base64 biçiminde olmalı.",
            "The image must be a data:image/png|jpeg|webp;base64 URL.",
        )
    payload = re.sub(r"\s+", "", m.group(2))
    if len(payload) > MAX_DATA_URL_CHARS:
        raise UserError("Görsel çok büyük (en fazla 15 MB).", "The image is too large (15 MB max).")
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as e:
        raise UserError("Görsel verisi bozuk.", "The image data is corrupt.") from e
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise UserError("Görsel boş ya da çok büyük (en fazla 15 MB).", "The image is empty or too large (15 MB max).")
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format not in ("PNG", "JPEG", "WEBP"):
                raise UserError("Desteklenmeyen görsel türü.", "Unsupported image type.")
            if im.width * im.height > MAX_IMAGE_PIXELS:
                raise UserError("Görsel çok büyük.", "The image is too large.")
            im.load()
            fmt = im.format
            has_alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
            out = io.BytesIO()
            if has_alpha or opacity < 1:
                rgba = im.convert("RGBA")
                if opacity < 1:
                    rgba.putalpha(rgba.getchannel("A").point(lambda a: int(a * opacity)))
                rgba.save(out, "PNG", optimize=True)
            elif fmt == "JPEG":
                im.convert("RGB").save(out, "JPEG", quality=92)
            else:
                im.convert("RGB").save(out, "PNG", optimize=True)
            return out.getvalue()
    except UserError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as e:
        raise UserError("Görsel okunamadı.", "Cannot read the image.") from e


def apply_image(state: _EditState, page: pymupdf.Page, op: ImageOp) -> None:
    rect = PageGeom(page).rect(op.rect, min_size=1)
    key = hashlib.sha256(f"{op.opacity}\0{op.data_url}".encode()).hexdigest()
    cached = state.images.get(key)
    data, xref = cached if cached else (decode_image(op.data_url, op.opacity), 0)
    # One image object per distinct picture, however many pages carry it.
    xref = page.insert_image(
        rect,
        stream=None if xref else data,
        xref=xref,
        rotate=(page.rotation - op.rotation) % 360,
        keep_proportion=False,
        overlay=True,
    )
    state.images[key] = (data, int(xref))


def apply_link(state: _EditState, page: pymupdf.Page, op: LinkOp) -> None:
    rect = PageGeom(page).rect(op.rect)
    if op.uri is not None:
        page.insert_link({"kind": pymupdf.LINK_URI, "from": rect, "uri": op.uri})
        return
    assert op.target_page is not None
    if op.target_page > state.doc.page_count:
        raise UserError(
            f"Hedef sayfa {op.target_page} yok (1–{state.doc.page_count}).",
            f"Target page {op.target_page} does not exist (1–{state.doc.page_count}).",
        )
    page.insert_link({"kind": pymupdf.LINK_GOTO, "from": rect, "page": op.target_page - 1, "to": pymupdf.Point(0, 0)})


# ---- existing annotations ------------------------------------------------------------------------------
_VERTEX_KEYS = {
    "Ink": "InkList",
    "Line": "L",
    "Polygon": "Vertices",
    "PolyLine": "Vertices",
    "Highlight": "QuadPoints",
    "Underline": "QuadPoints",
    "StrikeOut": "QuadPoints",
    "Squiggly": "QuadPoints",
}
_TOKEN = re.compile(r"\[|\]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def find_annot(page: pymupdf.Page, xref: int) -> Any:
    for annot in page.annots():
        if int(annot.xref) == xref and str(annot.type[1]) not in _SKIP_ANNOTS:
            return annot
    raise UserError(
        f"Açıklama bulunamadı (xref {xref}, sayfa {page.number + 1}).",
        f"Annotation not found (xref {xref}, page {page.number + 1}).",
    )


def _transform_array(value: str, fx: Callable[[float], float], fy: Callable[[float], float]) -> str:
    out: list[str] = []
    n = 0
    for tok in _TOKEN.findall(value):
        if tok in "[]":
            out.append(tok)
            continue
        v = float(tok)
        out.append(f"{(fx(v) if n % 2 == 0 else fy(v)):.3f}")
        n += 1
    return " ".join(out)


def move_annot(state: _EditState, page: pymupdf.Page, geom: PageGeom, annot: Any, new: pymupdf.Rect) -> Any:
    kind = str(annot.type[1])
    key = _VERTEX_KEYS.get(kind)
    if key is None:
        annot.set_rect(new)
        return annot
    # Vertex-based annotations derive their rect from their coordinates:
    # map those (PDF space) from the old rect onto the new one.
    old = pymupdf.Rect(annot.rect * geom.itm).normalize()
    tgt = pymupdf.Rect(new * geom.itm).normalize()
    sx = tgt.width / old.width if old.width > 0.01 else 1.0
    sy = tgt.height / old.height if old.height > 0.01 else 1.0
    typ, value = state.doc.xref_get_key(annot.xref, key)
    if typ != "array" or len(value) > 5_000_000:
        raise UserError("Açıklama taşınamadı.", "Cannot move this annotation.")
    moved = _transform_array(value, lambda x: tgt.x0 + (x - old.x0) * sx, lambda y: tgt.y0 + (y - old.y0) * sy)
    state.doc.xref_set_key(annot.xref, key, moved)
    state.doc.xref_set_key(annot.xref, "Rect", f"[{tgt.x0:.3f} {tgt.y0:.3f} {tgt.x1:.3f} {tgt.y1:.3f}]")
    return page.load_annot(annot.xref)


def apply_delete_annot(state: _EditState, page: pymupdf.Page, op: DeleteAnnotOp) -> None:
    page.delete_annot(find_annot(page, op.xref))


def apply_move_annot(state: _EditState, page: pymupdf.Page, op: MoveAnnotOp) -> None:
    geom = PageGeom(page)
    annot = move_annot(state, page, geom, find_annot(page, op.xref), geom.rect(op.rect, min_size=0.1))
    _refresh(annot)


def _refresh(annot: Any) -> None:
    annot.set_info(modDate=pymupdf.get_pdf_now())
    annot.update()


def apply_update_annot(state: _EditState, page: pymupdf.Page, op: UpdateAnnotOp) -> None:
    geom = PageGeom(page)
    annot = find_annot(page, op.xref)
    if op.rect is not None:
        annot = move_annot(state, page, geom, annot, geom.rect(op.rect, min_size=0.1))
    free_text = str(annot.type[1]) == "FreeText"
    if op.contents is not None:
        annot.set_info(content=op.contents)
    if op.author is not None:
        annot.set_info(title=op.author)
    if op.opacity is not None:
        annot.set_opacity(op.opacity)
    annot.set_info(modDate=pymupdf.get_pdf_now())
    if free_text:
        annot.update(text_color=_rgb(op.color), fill_color=_rgb(op.fill))
        return
    if op.color is not None:
        annot.set_colors(stroke=list(hex_to_rgb(op.color)))
    if op.fill is not None:
        annot.set_colors(fill=list(hex_to_rgb(op.fill)))
    annot.update()


_APPLY: dict[str, Callable[[_EditState, pymupdf.Page, Any], None]] = {
    "text": apply_text,
    "whiteout": apply_whiteout,
    "rect": apply_shape,
    "ellipse": apply_shape,
    "line": apply_line,
    "arrow": apply_line,
    "ink": apply_ink,
    "highlight": apply_markup,
    "underline": apply_markup,
    "strikeout": apply_markup,
    "squiggly": apply_markup,
    "note": apply_note,
    "freetext": apply_freetext,
    "image": apply_image,
    "link": apply_link,
    "delete_annot": apply_delete_annot,
    "move_annot": apply_move_annot,
    "update_annot": apply_update_annot,
}

_GENERIC = UserError("Bu işlem uygulanamadı.", "This operation could not be applied.")


@register
class Edit(Operation):
    name = "edit"
    category = "edit"
    title_tr, title_en = "PDF Düzenle", "Edit PDF"
    description_tr = "Metin, şekil, görsel, imza, bağlantı ve açıklama düzenlemelerini tek seferde uygular."
    description_en = "Apply text, shape, image, signature, link and annotation edits in one save."
    Params = EditParams
    hidden = True

    def run(self, ctx: Context, params: EditParams) -> None:
        inp = ctx.inputs[0]
        ops = params.operations
        failed: dict[int, UserError] = {}
        applied = 0
        with open_pdf(inp.path, inp.password) as doc:
            state = _EditState(doc=doc, fonts=FontCache(get_catalogue()))
            replaces: dict[int, list[tuple[int, ReplaceOp]]] = {}
            others: list[tuple[int, Any]] = []
            for index, op in enumerate(ops):
                if op.page > doc.page_count:
                    failed[index] = UserError(
                        f"Sayfa {op.page} yok (1–{doc.page_count}).",
                        f"Page {op.page} does not exist (1–{doc.page_count}).",
                    )
                elif isinstance(op, ReplaceOp):
                    replaces.setdefault(op.page, []).append((index, op))
                else:
                    others.append((index, op))
            done, total = 0, max(1, len(ops))
            # Replacements first, page by page: their redaction pass must not
            # see (and wipe) anything added by this same save.
            for page_no, items in replaces.items():
                for index, err in apply_replaces(state, doc[page_no - 1], items).items():
                    if err is None:
                        applied += 1
                    else:
                        failed[index] = err
                done += len(items)
                ctx.progress(done / total, "")
            for index, op in others:
                try:
                    _APPLY[op.type](state, doc[op.page - 1], op)
                    applied += 1
                except UserError as e:
                    failed[index] = e
                except Exception:
                    log.exception("edit op #%d (%s) failed", index, op.type)
                    failed[index] = _GENERIC
                done += 1
                if done % 50 == 0 or done == total:
                    ctx.progress(done / total, "")
            if applied == 0:
                first = failed[min(failed)]
                raise UserError(f"Hiçbir düzenleme uygulanamadı: {first.tr}", f"No edit could be applied: {first.en}")
            if state.used_fonts:
                try:
                    doc.subset_fonts()
                except Exception:
                    log.warning("font subsetting failed; saving full fonts", exc_info=True)
            save_pdf(doc, ctx.output(f"{inp.stem}_duzenlenmis.pdf"))
        ctx.data = {
            "applied": applied,
            "failed": [{"index": i, "error_tr": e.tr, "error_en": e.en} for i, e in sorted(failed.items())],
        }
