"""Building blocks of the PDF editor: coordinates, colours, text extraction,
background sampling and font resolution.

Coordinate contract: everything the UI sends or receives is **PDF user
space** of the page — origin bottom-left, unrotated, points, exactly what
pdf.js ``viewport.convertToPdfPoint`` returns. PyMuPDF works in its own
unrotated, top-left/y-down space; :class:`PageGeom` converts between the two
with ``page.transformation_matrix`` (which also absorbs a MediaBox offset).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import pymupdf

from .errors import UserError
from .fonts import Catalogue, FontStyle, match_pdf_font, name_key, strip_subset_prefix, style_bytes
from .pdf import unicode_font_path

# How far outside the page a rect/point may reach before it's rejected.
PAGE_MARGIN = 72.0
# Text extraction without image blocks (they'd carry the image bytes).
_DICT_FLAGS = pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_PRESERVE_IMAGES

RGB = tuple[float, float, float]


# -- colours ----------------------------------------------------------------------
def hex_to_rgb(value: str) -> RGB:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", value.strip())
    if not m:
        raise UserError("Renk #RRGGBB biçiminde olmalı.", "Colour must be #RRGGBB.")
    h = m.group(1)
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)


def rgb_to_hex(rgb: Sequence[float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb[:3])


def int_to_hex(value: int) -> str:
    return f"#{int(value) & 0xFFFFFF:06X}"


def color_to_hex(value: Sequence[float] | None) -> str | None:
    """PDF colour array (gray / RGB / CMYK) → ``#RRGGBB``; None if unset."""
    if not value:
        return None
    v = [float(c) for c in value]
    if len(v) == 1:
        return rgb_to_hex((v[0], v[0], v[0]))
    if len(v) == 3:
        return rgb_to_hex(v)
    if len(v) == 4:
        c, m, y, k = v
        return rgb_to_hex(((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k)))
    return None


# -- geometry ---------------------------------------------------------------------
def _r2(v: float) -> float:
    return round(float(v), 2)


class PageGeom:
    """PDF user space ⇄ PyMuPDF unrotated page space for one page."""

    def __init__(self, page: pymupdf.Page) -> None:
        self.page = page
        self.tm = page.transformation_matrix
        self.itm = ~self.tm
        # The page area in PyMuPDF's unrotated space.
        self.bounds = pymupdf.Rect(page.rect * page.derotation_matrix).normalize()
        self.allowed = pymupdf.Rect(
            self.bounds.x0 - PAGE_MARGIN,
            self.bounds.y0 - PAGE_MARGIN,
            self.bounds.x1 + PAGE_MARGIN,
            self.bounds.y1 + PAGE_MARGIN,
        )

    # UI → PyMuPDF
    def point(self, xy: Sequence[float]) -> pymupdf.Point:
        p = pymupdf.Point(float(xy[0]), float(xy[1])) * self.tm
        if not self.allowed.contains(p):
            raise UserError("Nokta sayfanın dışında.", "Point is outside the page.")
        return p

    def rect(self, r: Sequence[float], *, min_size: float = 0.5) -> pymupdf.Rect:
        out = pymupdf.Rect(pymupdf.Rect(*map(float, r)).normalize() * self.tm).normalize()
        if out.width < min_size or out.height < min_size:
            raise UserError("Alan çok küçük.", "The area is too small.")
        if not self.allowed.contains(out):
            raise UserError("Alan sayfanın dışında.", "The area is outside the page.")
        return out

    # PyMuPDF → UI
    def pdf_rect(self, r: Any) -> list[float]:
        out = pymupdf.Rect(pymupdf.Rect(r) * self.itm).normalize()
        return [_r2(out.x0), _r2(out.y0), _r2(out.x1), _r2(out.y1)]

    def pdf_point(self, p: Any) -> list[float]:
        q = pymupdf.Point(p) * self.itm
        return [_r2(q.x), _r2(q.y)]

    def page_info(self) -> dict[str, Any]:
        """``width``/``height`` are the unrotated page size; ``box`` is the
        page area in PDF user space (non-zero origin when the MediaBox is
        offset)."""
        return {
            "width": _r2(self.bounds.width),
            "height": _r2(self.bounds.height),
            "rotation": int(self.page.rotation),
            "box": self.pdf_rect(self.bounds),
        }

    def upright_dir(self) -> pymupdf.Point:
        """Unit vector, in unrotated space, that reads left→right for the viewer."""
        m = self.page.derotation_matrix
        return pymupdf.Point(m.a, m.b)

    def visual_quad(self, rect: pymupdf.Rect) -> pymupdf.Quad:
        """Quad of ``rect`` whose corners are named as the *viewer* sees
        them, so text markup (underline position…) follows page rotation."""
        vis = pymupdf.Rect(rect * self.page.rotation_matrix).normalize()
        inv = self.page.derotation_matrix
        return pymupdf.Quad(
            pymupdf.Point(vis.x0, vis.y0) * inv,
            pymupdf.Point(vis.x1, vis.y0) * inv,
            pymupdf.Point(vis.x0, vis.y1) * inv,
            pymupdf.Point(vis.x1, vis.y1) * inv,
        )


def dir_angle(d: Sequence[float]) -> float:
    """Counter-clockwise angle (degrees, as ``pymupdf.Matrix(angle)`` in a
    ``morph`` expects) of a text direction given in y-down page space."""
    return math.degrees(math.atan2(-float(d[1]), float(d[0])))


# -- background sampling -------------------------------------------------------------
class BackgroundSampler:
    """Render a page once (pixel-capped) and answer "what colour surrounds
    this rect?" — the mode of a ring of samples just outside it."""

    def __init__(self, page: pymupdf.Page, max_pixels: int = 2_500_000) -> None:
        r = page.rect
        area = max(1.0, r.width * r.height)
        self.zoom = max(0.05, min(1.0, math.sqrt(max_pixels / area)))
        pix = page.get_pixmap(matrix=pymupdf.Matrix(self.zoom, self.zoom), alpha=False, annots=False)
        if pix.n < 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        self.w, self.h, self.n, self.stride = pix.width, pix.height, pix.n, pix.stride
        self.samples = bytes(pix.samples)
        self.m = page.rotation_matrix * pymupdf.Matrix(self.zoom, self.zoom)

    def _px(self, x: float, y: float) -> tuple[int, int, int] | None:
        xi, yi = int(x), int(y)
        if not (0 <= xi < self.w and 0 <= yi < self.h):
            return None
        o = yi * self.stride + xi * self.n
        s = self.samples
        return (s[o], s[o + 1], s[o + 2])

    def around(self, rect: pymupdf.Rect) -> str:
        v = pymupdf.Rect(rect * self.m).normalize()
        pad = max(1.0, min(4.0, 0.2 * min(v.width, v.height) + 1))
        counter: Counter[tuple[int, int, int]] = Counter()
        steps = 6
        for i in range(steps + 1):
            t = i / steps
            x = v.x0 + t * v.width
            y = v.y0 + t * v.height
            for px in (
                self._px(x, v.y0 - pad),
                self._px(x, v.y1 + pad),
                self._px(v.x0 - pad, y),
                self._px(v.x1 + pad, y),
            ):
                if px is not None:
                    counter[px] += 1
        if not counter:
            return "#FFFFFF"
        (r, g, b), _ = counter.most_common(1)[0]
        return f"#{r:02X}{g:02X}{b:02X}"


# -- text extraction ------------------------------------------------------------------
@dataclass
class Char:
    c: str
    bbox: pymupdf.Rect
    origin: pymupdf.Point


@dataclass
class Run:
    """A span's style plus the characters it holds."""

    font: str
    size: float
    color: int
    flags: int
    chars: list[Char]


@dataclass
class Line:
    block: int
    index: int
    dir: tuple[float, float]
    runs: list[Run] = field(default_factory=list)


def page_lines(page: pymupdf.Page) -> list[Line]:
    """Character-level text of a page, grouped into lines."""
    out: list[Line] = []
    data = page.get_text("rawdict", flags=_DICT_FLAGS)
    for b_idx, block in enumerate(data.get("blocks", [])):
        if block.get("type") != 0:
            continue
        for l_idx, line in enumerate(block.get("lines", [])):
            d = line.get("dir") or (1.0, 0.0)
            ln = Line(block=b_idx, index=l_idx, dir=(float(d[0]), float(d[1])))
            for span in line.get("spans", []):
                chars = [
                    Char(ch["c"], pymupdf.Rect(ch["bbox"]), pymupdf.Point(ch["origin"]))
                    for ch in span.get("chars", [])
                    if ch.get("c")
                ]
                if chars:
                    ln.runs.append(
                        Run(
                            font=str(span.get("font") or ""),
                            size=float(span.get("size") or 0),
                            color=int(span.get("color") or 0),
                            flags=int(span.get("flags") or 0),
                            chars=chars,
                        )
                    )
            if ln.runs:
                out.append(ln)
    return out


def union(rects: Iterator[pymupdf.Rect] | list[pymupdf.Rect]) -> pymupdf.Rect:
    out = pymupdf.Rect()
    first = True
    for r in rects:
        out = pymupdf.Rect(r) if first else out | r
        first = False
    return out


_NEUTRAL_SUFFIXES = ("book", "regular", "normal", "roman", "psmt", "mt")


def font_key(name: str) -> str:
    """Comparable form of a font name. Text extraction reports the font
    program's own name (``DejaVuSans``) while the page resources carry the
    BaseFont (``ABCDEF+DejaVu Sans Book``); both reduce to ``dejavusans``."""
    k = name_key(strip_subset_prefix(name))
    changed = True
    while changed:
        changed = False
        for suffix in _NEUTRAL_SUFFIXES:
            if k.endswith(suffix) and len(k) > len(suffix) + 2:
                k = k[: -len(suffix)]
                changed = True
    return k


def embedded_font_names(page: pymupdf.Page) -> set[str]:
    """:func:`font_key` of every font actually embedded in the page."""
    return {font_key(str(f[3])) for f in page.get_fonts(full=True) if str(f[1]) != "n/a"}


def is_bold(flags: int) -> bool:
    return bool(flags & 16)


def is_italic(flags: int) -> bool:
    return bool(flags & 2)


def match_run(cat: Catalogue, run: Run) -> dict[str, Any]:
    return match_pdf_font(
        run.font,
        catalogue=cat,
        bold=is_bold(run.flags),
        italic=is_italic(run.flags),
        serif=bool(run.flags & 4),
        mono=bool(run.flags & 8),
    ).public()


# -- fonts for writing ---------------------------------------------------------------
@dataclass
class WriteFont:
    """A font ready to draw with: its program bytes and a PyMuPDF handle."""

    key: str
    buffer: bytes
    font: pymupdf.Font
    style: FontStyle | None = None  # catalogue face, if any
    base14: str = ""  # PDF standard font code, if any

    def covers(self, text: str) -> bool:
        return all(ch.isspace() or self.font.has_glyph(ord(ch)) for ch in text)

    def width(self, text: str, size: float) -> float:
        return float(self.font.text_length(text, fontsize=size))


class FontCache:
    """Loads catalogue faces / embedded fonts once per job."""

    def __init__(self, cat: Catalogue) -> None:
        self.cat = cat
        self._fonts: dict[str, WriteFont] = {}

    def _load(self, key: str, make: Any) -> WriteFont:
        wf = self._fonts.get(key)
        if wf is None:
            wf = make()
            self._fonts[key] = wf
        return wf

    def from_style(self, style: FontStyle) -> WriteFont:
        if style.restricted:
            raise UserError(
                "Bu yazı tipinin lisansı PDF'e gömülmesine izin vermiyor.",
                "This font's licence does not allow embedding it in a PDF.",
            )

        def make() -> WriteFont:
            if style.base14:
                f = pymupdf.Font(style.base14)
                return WriteFont(style.id, bytes(f.buffer), f, style=style, base14=style.base14)
            try:
                buf = style_bytes(style)
                return WriteFont(style.id, buf, pymupdf.Font(fontbuffer=buf), style=style)
            except Exception as e:
                raise UserError("Yazı tipi okunamadı.", "Cannot read the font.") from e

        return self._load(style.id, make)

    def from_ref(self, family_id: str | None, weight: int, italic: bool, font_id: str | None) -> WriteFont | None:
        if font_id:
            style = self.cat.style(font_id)
            if style is None:
                raise UserError("Yazı tipi bulunamadı.", "Font not found.")
            return self.from_style(style)
        if family_id:
            fam = self.cat.family(family_id)
            if fam is None:
                raise UserError("Yazı tipi ailesi bulunamadı.", "Font family not found.")
            return self.from_style(fam.resolve(weight, italic))
        return None

    def from_buffer(self, key: str, buf: bytes) -> WriteFont | None:
        try:
            return self._load(key, lambda: WriteFont(key, buf, pymupdf.Font(fontbuffer=buf)))
        except Exception:
            return None

    def unicode_fallback(self) -> WriteFont:
        path = unicode_font_path()
        if path:

            def make() -> WriteFont:
                with open(path, "rb") as fh:
                    buf = fh.read()
                return WriteFont("unicode", buf, pymupdf.Font(fontbuffer=buf))

            try:
                return self._load("unicode", make)
            except Exception:
                pass
        std = self.cat.style("std-helv")
        assert std is not None
        return self.from_style(std)


def extract_embedded_font(doc: pymupdf.Document, page: pymupdf.Page, name: str) -> tuple[str, bytes] | None:
    """The program of an embedded TrueType/OpenType/CFF font used on the
    page under ``name`` (subset prefix ignored), as ``(key, bytes)``."""
    want = font_key(name)
    if not want:
        return None
    for f in page.get_fonts(full=True):
        xref, ext = int(f[0]), str(f[1])
        if font_key(str(f[3])) != want or ext.lower() not in ("ttf", "otf", "cff"):
            continue
        try:
            content = doc.extract_font(xref)[3]
        except Exception:
            continue
        if isinstance(content, bytes | bytearray) and len(content) > 100:
            return f"xref{xref}", bytes(content)
    return None
