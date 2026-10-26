"""Redaction: find personal data (KVKK) and remove it for real.

Matching runs over the page's character stream (``rawdict``) so every hit
maps back to exact glyph boxes — a match may span words and lines and is
returned as one rectangle per line. Coordinates exchanged with the UI are
PDF user space (origin bottom-left, unrotated).
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

import pymupdf
from pydantic import field_validator

from ..core.errors import UserError
from ..core.pdf import flatten_to_images, open_pdf, parse_page_spec, save_pdf
from .base import Context, Field, Operation, Params, ProgressFn, register
from .stamp import parse_color
from .structure import strip_document_metadata

MAX_TERMS = 500
MAX_TERM_LENGTH = 200
MAX_REGEX_LENGTH = 500
MAX_PAGE_CHARS = 500_000
MAX_MATCHES = 20_000
MAX_AREAS = 5000

Preset = Literal["tckn", "iban", "phone", "email", "card"]

# -- validators ------------------------------------------------------------------


def tckn_valid(value: str) -> bool:
    """Turkish identity number: 11 digits, first ≠ 0, two check digits."""
    if len(value) != 11 or not value.isascii() or not value.isdigit() or value[0] == "0":
        return False
    d = [int(c) for c in value]
    tenth = ((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10
    eleventh = sum(d[:10]) % 10
    return d[9] == tenth and d[10] == eleventh


def iban_valid(value: str) -> bool:
    """ISO 13616 mod-97 check; Turkish IBANs must be ``TR`` + 24 digits."""
    s = re.sub(r"\s+", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", s):
        return False
    if s.startswith("TR") and not re.fullmatch(r"TR\d{24}", s):
        return False
    rearranged = s[4:] + s[:4]
    digits = "".join(str(int(c, 36)) for c in rearranged)
    return int(digits) % 97 == 1


def luhn_valid(value: str) -> bool:
    """Payment card number: 13–19 digits passing the Luhn checksum."""
    digits = re.sub(r"[\s-]", "", value)
    if not 13 <= len(digits) <= 19 or not digits.isascii() or not digits.isdigit():
        return False
    total = 0
    for i, c in enumerate(reversed(digits)):
        n = int(c)
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def phone_valid(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("0090"):
        digits = digits[4:]
    elif digits.startswith("90") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = digits[1:]
    return len(digits) == 10 and digits[0] in "23458"


_SEP = r"[ .\-]?"
_PRESETS: dict[str, tuple[re.Pattern[str], Any]] = {
    # Order matters: earlier kinds win when matches overlap.
    "iban": (re.compile(r"(?<![A-Za-z0-9])[Tt][Rr]\d{2}(?: ?\d{4}){5} ?\d{2}(?!\d)"), iban_valid),
    "card": (re.compile(r"(?<![\d\-])\d(?:[ \-]?\d){12,18}(?![\d\-])"), luhn_valid),
    "tckn": (re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)"), tckn_valid),
    "phone": (
        re.compile(
            r"(?<![\d+])(?:(?:\+|00)90" + _SEP + r"\(?0?[2-58]\d{2}\)?"  # +90 532… / +90 (212)…
            r"|\(0[2-58]\d{2}\)"  # (0212)…
            r"|0"
            + _SEP
            + r"\(?[2-58]\d{2}\)?)"  # 0532… / 0 (212)…
            + _SEP
            + r"\d{3}"
            + _SEP
            + r"\d{2}"
            + _SEP
            + r"\d{2}(?!\d)"
        ),
        phone_valid,
    ),
    "email": (
        re.compile(r"(?<![\w.%+-])[\w.%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){0,8}\.[A-Za-z]{2,24}\b"),
        None,
    ),
}


def mask_text(text: str) -> str:
    """``"12345678901"`` → ``"123*******1"`` — enough to recognise, not to leak."""
    chars = [c for c in text if not c.isspace()]
    n = len(chars)
    if n <= 2:
        return "*" * n
    front, back = min(4, n // 3), min(2, n // 6)
    return "".join(chars[:front]) + "*" * (n - front - back) + "".join(chars[n - back :] if back else [])


# -- user regex safety -------------------------------------------------------------

_REPEATS = ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT")


def _has_nested_quantifier(pattern: str) -> bool:
    parser: Any = importlib.import_module("re._parser")
    tree = parser.parse(pattern)

    def items(node: Any) -> Iterator[tuple[Any, Any]]:
        """Yield (op, argument) pairs anywhere below ``node``."""
        if isinstance(node, (parser.SubPattern, list)):
            for item in node:
                if isinstance(item, tuple) and len(item) == 2 and hasattr(item[0], "name"):
                    yield item
                    yield from items(item[1])
                else:
                    yield from items(item)
        elif isinstance(node, tuple):
            for part in node:
                yield from items(part)

    for op, av in items(tree):
        if op.name in _REPEATS and av[1] > 1:
            for inner_op, inner_av in items(av[2]):
                # A fixed count inside (``(?:\d{3}-)*``) cannot backtrack.
                if inner_op.name in _REPEATS and inner_av[0] != inner_av[1]:
                    return True
    return False


def compile_user_regex(pattern: str, case_sensitive: bool) -> re.Pattern[str]:
    if len(pattern) > MAX_REGEX_LENGTH:
        raise UserError("Düzenli ifade çok uzun.", "The regular expression is too long.")
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        compiled = re.compile(pattern, flags)
        nested = _has_nested_quantifier(pattern)
    except (re.error, RecursionError, OverflowError) as e:
        raise UserError("Düzenli ifade geçersiz.", "The regular expression is invalid.") from e
    if nested:
        raise UserError(
            "İç içe tekrarlayıcı içeren düzenli ifadelere izin verilmez (örn. (a+)+).",
            "Regular expressions with nested quantifiers are not allowed (e.g. (a+)+).",
        )
    return compiled


def compile_terms(terms: str, case_sensitive: bool) -> re.Pattern[str] | None:
    items = sorted({t.strip() for t in terms.splitlines() if t.strip()}, key=len, reverse=True)
    if len(items) > MAX_TERMS:
        raise UserError(f"En fazla {MAX_TERMS} terim girilebilir.", f"At most {MAX_TERMS} terms are allowed.")
    if any(len(t) > MAX_TERM_LENGTH for t in items):
        raise UserError("Terimlerden biri çok uzun.", "One of the terms is too long.")
    if not items:
        return None
    # Whitespace inside a term matches any run of whitespace, so a phrase
    # still matches when the PDF breaks it across lines.
    alts = [r"\s+".join(re.escape(w) for w in t.split()) for t in items]
    return re.compile("|".join(alts), 0 if case_sensitive else re.IGNORECASE)


# -- page text with glyph boxes -------------------------------------------------------


@dataclass
class PageText:
    text: str
    boxes: list[tuple[pymupdf.Rect, int] | None]  # per character: (box, line id)


def page_text(page: pymupdf.Page) -> PageText:
    flags = (pymupdf.TEXTFLAGS_RAWDICT | pymupdf.TEXT_ACCURATE_BBOXES) & ~pymupdf.TEXT_PRESERVE_LIGATURES
    flags &= ~pymupdf.TEXT_PRESERVE_IMAGES
    chars: list[str] = []
    boxes: list[tuple[pymupdf.Rect, int] | None] = []
    line_id = 0
    for block in page.get_text("rawdict", flags=flags).get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for ch in span.get("chars", []):
                    c = ch.get("c", "")
                    if not c:
                        continue
                    chars.append(c)
                    boxes.append((pymupdf.Rect(ch["bbox"]), line_id))
            chars.append("\n")
            boxes.append(None)
            line_id += 1
            if len(chars) > MAX_PAGE_CHARS:
                raise UserError(
                    f"Sayfa {page.number + 1} çok fazla metin içeriyor.",
                    f"Page {page.number + 1} contains too much text.",
                )
    return PageText("".join(chars), boxes)


def span_rects(pt: PageText, start: int, end: int) -> list[pymupdf.Rect]:
    """One rectangle per text line covered by ``[start, end)``."""
    by_line: dict[int, pymupdf.Rect] = {}
    for item in pt.boxes[start:end]:
        if item is None:
            continue
        box, line = item
        if box.is_empty or box.is_infinite:
            continue
        if line in by_line:
            by_line[line] |= box
        else:
            by_line[line] = pymupdf.Rect(box)
    return list(by_line.values())


# -- matching ----------------------------------------------------------------------


@dataclass
class Match:
    page: int  # 0-based
    kind: str
    text: str
    rects: list[pymupdf.Rect] = field(default_factory=list)


class MatchParams(Params):
    terms: str = Field(
        "",
        tr="Aranacak ifadeler",
        en="Terms to find",
        help_tr="Her satıra bir ifade (en fazla 500).",
        help_en="One term per line (up to 500).",
        max_length=MAX_TERMS * (MAX_TERM_LENGTH + 2),
        ui={"widget": "textarea"},
    )
    regex: str = Field(
        "",
        tr="Düzenli ifade (isteğe bağlı)",
        en="Regular expression (optional)",
        max_length=MAX_REGEX_LENGTH,
    )
    case_sensitive: bool = Field(False, tr="Büyük/küçük harfe duyarlı", en="Case sensitive")
    presets: list[Preset] = Field(
        default_factory=list,
        tr="Kişisel veri türleri",
        en="Personal data types",
        max_length=5,
        ui={
            "options": {
                "tckn": {"tr": "T.C. kimlik no", "en": "Turkish ID number"},
                "iban": {"tr": "IBAN", "en": "IBAN"},
                "phone": {"tr": "Telefon", "en": "Phone"},
                "email": {"tr": "E-posta", "en": "E-mail"},
                "card": {"tr": "Kredi kartı", "en": "Payment card"},
            }
        },
    )
    pages: str = Field("", tr="Sayfalar (boş = tümü)", en="Pages (empty = all)", max_length=2000)


def find_matches(doc: pymupdf.Document, p: MatchParams, progress: ProgressFn) -> tuple[list[Match], bool]:
    """All hits in the selected pages. Returns ``(matches, truncated)``."""
    term_re = compile_terms(p.terms, p.case_sensitive)
    user_re = compile_user_regex(p.regex, p.case_sensitive) if p.regex.strip() else None
    patterns: list[tuple[str, re.Pattern[str], Any]] = []
    for name, (rx, check) in _PRESETS.items():
        if name in p.presets:
            patterns.append((name, rx, check))
    if term_re:
        patterns.append(("term", term_re, None))
    if user_re:
        patterns.append(("regex", user_re, None))
    if not patterns:
        return [], False

    targets = sorted(set(parse_page_spec(p.pages, doc.page_count)))
    out: list[Match] = []
    for k, pno in enumerate(targets):
        pt = page_text(doc[pno])
        taken: list[tuple[int, int]] = []
        found: list[tuple[int, Match]] = []
        for kind, rx, check in patterns:
            for m in rx.finditer(pt.text):
                s, e = m.span()
                if s == e or any(s < te and ts < e for ts, te in taken):
                    continue
                if check is not None and not check(m.group()):
                    continue
                rects = span_rects(pt, s, e)
                if not rects:
                    continue
                taken.append((s, e))
                found.append((s, Match(pno, kind, m.group(), rects)))
                if len(out) + len(found) >= MAX_MATCHES:
                    out.extend(m for _, m in sorted(found, key=lambda t: t[0]))
                    return out, True
        out.extend(m for _, m in sorted(found, key=lambda t: t[0]))
        progress((k + 1) / len(targets), "")
    return out, False


def to_user(rect: pymupdf.Rect, page: pymupdf.Page) -> list[float]:
    r = (rect * ~page.transformation_matrix).normalize()
    return [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]


def from_user(rect: Iterable[float], page: pymupdf.Page) -> pymupdf.Rect:
    return (pymupdf.Rect(*rect) * page.transformation_matrix).normalize()


@register
class FindSensitive(Operation):
    name = "find_sensitive"
    category = "redact"
    title_tr, title_en = "Kişisel Veri Bul", "Find Personal Data"
    description_tr = (
        "T.C. kimlik no, IBAN, telefon, e-posta, kart no veya aradığınız ifadeleri bulur; dosyayı değiştirmez."
    )
    description_en = (
        "Find Turkish ID numbers, IBANs, phones, e-mails, card numbers or your own terms without changing the file."
    )
    returns_data = True
    Params = MatchParams

    def run(self, ctx: Context, params: MatchParams) -> None:
        if not (params.terms.strip() or params.regex.strip() or params.presets):
            raise UserError(
                "Aranacak ifade, düzenli ifade veya veri türü seçin.",
                "Enter terms, a regular expression or choose a data type.",
            )
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            matches, truncated = find_matches(doc, params, ctx.progress)
            counts: dict[str, int] = {}
            items: list[dict[str, Any]] = []
            for m in matches:
                counts[m.kind] = counts.get(m.kind, 0) + 1
                page = doc[m.page]
                items.append(
                    {
                        "page": m.page + 1,
                        "kind": m.kind,
                        "text": mask_text(m.text),
                        "rects": [to_user(r, page) for r in m.rects],
                    }
                )
            ctx.data = {"total": len(items), "counts": counts, "truncated": truncated, "matches": items}


# -- redaction ------------------------------------------------------------------------


class Area(Params):
    page: int = Field(..., tr="Sayfa", en="Page", ge=1, le=100_000)
    rect: tuple[float, float, float, float] = Field(..., tr="Alan", en="Area")

    @field_validator("rect")
    @classmethod
    def _finite(cls, v: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        if any(abs(x) > 1_000_000 or x != x for x in v):
            raise ValueError("coordinate out of range")
        return v


class RedactParams(MatchParams):
    areas: list[Area] = Field(
        default_factory=list,
        tr="Elle seçilen alanlar",
        en="Hand-drawn areas",
        max_length=MAX_AREAS,
        ui={"widget": "json"},
    )
    fill_color: str = Field(
        "#000000", tr="Dolgu rengi", en="Fill colour", pattern=r"^#?[0-9a-fA-F]{6}$", ui={"widget": "color"}
    )
    overlay_text: str = Field(
        "",
        tr="Kutu üzerindeki yazı",
        en="Label on the box",
        help_tr="Örn. KARARTILDI",
        help_en="E.g. REDACTED",
        max_length=60,
    )
    remove_metadata: bool = Field(True, tr="Meta veriyi de temizle", en="Also remove metadata")
    flatten: bool = Field(
        False,
        tr="Ekstra güvenli PDF (sayfaları görsele çevir)",
        en="Extra-secure PDF (turn pages into images)",
        help_tr="Sonuç yalnızca sayfa görüntülerinden oluşur: metin, gizli katman veya nesne kalmaz, hiçbir araçla "
        "geri getirilemez. Metin artık seçilemez ve aranamaz; dosya büyüyebilir.",
        help_en="The result is page pictures only: no text, hidden layers or objects remain, nothing can be "
        "recovered by any tool. Text can no longer be selected or searched; the file may grow.",
    )
    flatten_dpi: int = Field(
        200,
        tr="Görüntü çözünürlüğü (DPI)",
        en="Image resolution (DPI)",
        ge=100,
        le=400,
        ui={"show_if": {"flatten": True}},
    )


def _intersects(rect: pymupdf.Rect, boxes: list[pymupdf.Rect]) -> bool:
    return any(rect.intersects(b) for b in boxes)


def _clear_overlapping(page: pymupdf.Page, boxes: list[pymupdf.Rect]) -> None:
    """Annotations, links and form values over a redacted area would keep
    the content alive (comments quote text, fields hold values)."""
    for link in page.get_links():
        if _intersects(pymupdf.Rect(link["from"]), boxes):
            page.delete_link(link)
    for widget in list(page.widgets()):
        if _intersects(widget.rect, boxes):
            if widget.field_type in (pymupdf.PDF_WIDGET_TYPE_CHECKBOX, pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON):
                widget.field_value = False
            elif widget.field_type in (pymupdf.PDF_WIDGET_TYPE_TEXT, pymupdf.PDF_WIDGET_TYPE_COMBOBOX):
                widget.field_value = ""
            widget.update()
    doomed = [a.xref for a in page.annots() if a.type[0] != pymupdf.PDF_ANNOT_REDACT and _intersects(a.rect, boxes)]
    for xref in doomed:
        annot = page.load_annot(xref)
        if annot is not None:
            page.delete_annot(annot)


@register
class Redact(Operation):
    name = "redact"
    category = "redact"
    title_tr, title_en = "Karart (Kalıcı)", "Redact (Permanent)"
    description_tr = (
        "Seçilen metni, görsel piksellerini ve çizimleri kalıcı olarak siler; altındaki içerik geri getirilemez."
    )
    description_en = "Permanently remove the selected text, image pixels and drawings; the content cannot be recovered."
    Params = RedactParams

    def run(self, ctx: Context, params: RedactParams) -> None:
        fill = parse_color(params.fill_color)
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            matches, truncated = find_matches(doc, params, lambda f, m: ctx.progress(f / 2, m))
            if truncated:
                raise UserError(
                    f"Çok fazla eşleşme (>{MAX_MATCHES}); aramayı daraltın.",
                    f"Too many matches (>{MAX_MATCHES}); narrow the search.",
                )
            boxes: dict[int, list[pymupdf.Rect]] = {}
            for m in matches:
                boxes.setdefault(m.page, []).extend(m.rects)
            for a in params.areas:
                if a.page > doc.page_count:
                    raise UserError(
                        f"Sayfa {a.page} aralık dışında (1–{doc.page_count}).",
                        f"Page {a.page} is out of range (1–{doc.page_count}).",
                    )
                page = doc[a.page - 1]
                r = from_user(a.rect, page)
                if r.is_empty:
                    continue
                boxes.setdefault(a.page - 1, []).append(r)
            if not boxes:
                raise UserError(
                    "Karartılacak bir şey bulunamadı.",
                    "Nothing to redact was found.",
                )
            total = 0
            for k, (pno, rects) in enumerate(sorted(boxes.items())):
                page = doc[pno]
                _clear_overlapping(page, rects)
                for r in rects:
                    page.add_redact_annot(
                        r,
                        text=params.overlay_text or None,
                        fontsize=max(4.0, min(11.0, r.height * 0.7)),
                        fill=fill,
                        text_color=(1, 1, 1) if sum(fill) < 1.5 else (0, 0, 0),
                        align=pymupdf.TEXT_ALIGN_CENTER,
                        cross_out=False,
                    )
                    total += 1
                # Acrobat's default: blank the covered image pixels, drop
                # vector art only when it lies entirely inside the box.
                page.apply_redactions(
                    images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                    graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                    text=pymupdf.PDF_REDACT_TEXT_REMOVE,
                )
                ctx.progress(0.5 + 0.5 * (k + 1) / len(boxes), "")
            if params.remove_metadata:
                strip_document_metadata(doc)
            if params.flatten:
                flatten_to_images(doc, ctx.output(f"{inp.stem}_karartilmis_guvenli.pdf"), dpi=params.flatten_dpi)
            else:
                # garbage=4 drops the now-unreferenced original streams.
                save_pdf(doc, ctx.output(f"{inp.stem}_karartilmis.pdf"), clean=True)
        ctx.data = {"redactions": total, "pages": [p + 1 for p in sorted(boxes)]}
