"""KVKK assistant: scan a document for personal data, then apply a chosen
treatment per finding (black-out, white-out, mask or blur).

The scan reuses the checksum-validated detectors of ``redact`` and adds
Turkish-specific ones (vehicle plates, tax numbers, labelled fields such as
"Ad Soyad:" / "Adres:") plus keyword hints for *special categories* of
personal data (KVKK md. 6: health, religion, union membership, criminal
records, biometrics…), which are flagged for human review.

Every treatment removes the underlying text for real (redaction); "blur"
then lays a heavily pixelated rendering of the original area on top, which
keeps the layout readable without the content being recoverable.
"""

from __future__ import annotations

import io
import re
from typing import Any, Literal

import pymupdf
from pydantic import field_validator

from ..core.errors import UserError
from ..core.pdf import open_pdf, save_pdf
from .base import Context, Field, Operation, Params, register
from .redact import (
    _PRESETS,
    MAX_MATCHES,
    _clear_overlapping,
    from_user,
    mask_text,
    page_text,
    span_rects,
    to_user,
)
from .structure import strip_document_metadata

Action = Literal["black", "white", "mask", "blur", "keep"]

# kind → (tr, en, recommended action, KVKK special category?)
KINDS: dict[str, tuple[str, str, Action, bool]] = {
    "tckn": ("T.C. kimlik no", "Turkish ID number", "black", False),
    "iban": ("IBAN", "IBAN", "mask", False),
    "card": ("Kredi kartı", "Payment card", "black", False),
    "phone": ("Telefon", "Phone", "mask", False),
    "email": ("E-posta", "E-mail", "mask", False),
    "vkn": ("Vergi kimlik no", "Tax number", "mask", False),
    "plate": ("Araç plakası", "Vehicle plate", "blur", False),
    "name": ("Ad soyad", "Name", "blur", False),
    "address": ("Adres", "Address", "blur", False),
    "birth": ("Doğum bilgisi", "Birth details", "black", False),
    "parent": ("Anne / baba adı", "Parent's name", "black", False),
    "special": ("Özel nitelikli veri ipucu", "Special-category hint", "keep", True),
    "manual": ("Elle seçilen alan", "Manually selected area", "black", False),
}


def vkn_valid(value: str) -> bool:
    """Turkish tax number (VKN) checksum."""
    d = [int(c) for c in re.sub(r"\D", "", value)]
    if len(d) != 10:
        return False
    total = 0
    for i in range(9):
        t = (d[i] + 9 - i) % 10
        p = (t * 2 ** (9 - i)) % 9
        if t != 0 and p == 0:
            p = 9
        total += p
    return (10 - total % 10) % 10 == d[9]


_LABEL = r"\s*[:：]\s*"
EXTRA: dict[str, re.Pattern[str]] = {
    # 34 ABC 123 / 06 AB 1234 / 35 A 12345 — province code 01–81.
    "plate": re.compile(r"(?<![\w])(?:0[1-9]|[1-7]\d|8[01]) ?[A-PR-VYZ]{1,3} ?\d{2,5}(?![\w])"),
    "vkn": re.compile(r"(?i)(?:vergi\s*(?:kimlik\s*)?no|vkn)\s*[:：]?\s*(\d{10})(?!\d)"),
    "name": re.compile(
        r"(?im)^.*?\b(?:ad[ıi]?\s*soyad[ıi]?|ad\s*/\s*soyad|isim\s*soyisim|müşteri\s*ad[ıi])" + _LABEL + r"(.{2,80})$"
    ),
    "address": re.compile(r"(?im)^.*?\b(?:adres(?:i)?|ikamet(?:gah)?\s*adresi?)" + _LABEL + r"(.{4,200})$"),
    "birth": re.compile(r"(?im)\b(?:doğum\s*(?:tarihi|yeri|tarihi\s*/\s*yeri))" + _LABEL + r"(.{2,60})$"),
    "parent": re.compile(r"(?im)\b(?:anne|baba)\s*ad[ıi]" + _LABEL + r"(.{2,60})$"),
}

SPECIAL_WORDS = re.compile(
    r"(?i)\b(sağlık\s*rapor\w*|teşhis\w*|tanı\b|hastal[ıi]k\w*|ilaç\w*|tedavi\w*|engelli\w*|kan\s*grubu|"
    r"din(?:i|î)?\b|mezhep\w*|ırk\w*|etnik\w*|sendika\w*|siyasi\s*parti\w*|ceza\w*\s*mahkûmiyet\w*|"
    r"sabıka\w*|biyometrik\w*|parmak\s*izi|genetik\w*|cinsel\w*)\b"
)

MAX_FINDINGS = MAX_MATCHES


def _overlaps(a: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(a[0] < e and s < a[1] for s, e in spans)


class ScanParams(Params):
    include_special: bool = Field(
        True,
        tr="Özel nitelikli veri ipuçlarını da işaretle",
        en="Also flag special-category hints",
        help_tr="Sağlık, din, sendika, ceza mahkûmiyeti gibi KVKK md. 6 kapsamındaki ifadeler incelemeye sunulur.",
        help_en="Health, religion, union, criminal-record terms (KVKK art. 6) are offered for review.",
    )
    pages: str = Field("", tr="Sayfalar (boş = tümü)", en="Pages (empty = all)", max_length=2000)


@register
class KvkkScan(Operation):
    name = "kvkk_scan"
    category = "redact"
    title_tr, title_en = "KVKK Taraması", "Personal-Data Scan"
    description_tr = (
        "Belgeyi tarar: kimlik no, IBAN, kart, telefon, e-posta, plaka, vergi no, ad-soyad, adres, doğum bilgisi "
        "ve özel nitelikli veri ipuçlarını bulur, her biri için işlem önerir."
    )
    description_en = (
        "Scans for ID numbers, IBANs, cards, phones, e-mails, plates, tax numbers, names, addresses, birth details "
        "and special-category hints, and suggests a treatment for each."
    )
    returns_data = True
    Params = ScanParams

    def run(self, ctx: Context, params: ScanParams) -> None:
        from ..core.pdf import parse_page_spec

        inp = ctx.inputs[0]
        findings: list[dict[str, Any]] = []
        with open_pdf(inp.path, inp.password) as doc:
            targets = sorted(set(parse_page_spec(params.pages, doc.page_count)))
            for k, pno in enumerate(targets):
                findings.extend(_page_findings(doc[pno], params.include_special, MAX_FINDINGS - len(findings)))
                ctx.progress((k + 1) / len(targets), "")
        counts: dict[str, int] = {}
        for f in findings:
            counts[f["kind"]] = counts.get(f["kind"], 0) + 1
        ctx.data = {
            "total": len(findings),
            "truncated": len(findings) >= MAX_FINDINGS,
            "counts": counts,
            "kinds": {k: {"tr": v[0], "en": v[1], "suggested": v[2], "special": v[3]} for k, v in KINDS.items()},
            "findings": findings,
        }


def _page_findings(page: pymupdf.Page, include_special: bool, budget: int) -> list[dict[str, Any]]:
    """Findings of one page; earlier detectors win where matches overlap."""
    pt = page_text(page)
    taken: list[tuple[int, int]] = []
    out: list[dict[str, Any]] = []

    def add(kind: str, s: int, e: int, text: str) -> None:
        if s >= e or len(out) >= budget or _overlaps((s, e), taken):
            return
        rects = span_rects(pt, s, e)
        if not rects:
            return
        taken.append((s, e))
        out.append(
            {
                "id": f"{page.number + 1}-{s}",
                "page": page.number + 1,
                "kind": kind,
                "text": mask_text(text),
                "mask": mask_text(text),
                "rects": [to_user(r, page) for r in rects],
                "suggested": KINDS[kind][2],
            }
        )

    for kind, (rx, check) in _PRESETS.items():
        for m in rx.finditer(pt.text):
            if check is None or check(m.group()):
                add(kind, *m.span(), m.group())
    for kind, rx in EXTRA.items():
        for m in rx.finditer(pt.text):
            g = 1 if rx.groups else 0
            value = m.group(g).rstrip()
            if kind == "vkn" and not vkn_valid(value):
                continue
            s = m.start(g)
            add(kind, s, s + len(value), value)
    if include_special:
        for m in SPECIAL_WORDS.finditer(pt.text):
            add("special", *m.span(), m.group())
    return out


class Treatment(Params):
    page: int = Field(..., tr="Sayfa", en="Page", ge=1, le=100_000)
    rects: list[list[float]] = Field(..., tr="Alanlar", en="Areas", min_length=1, max_length=50)
    action: Action = Field("black", tr="İşlem", en="Action")
    mask: str = Field("", tr="Maske metni", en="Mask text", max_length=200)

    @field_validator("rects")
    @classmethod
    def _four(cls, v: list[list[float]]) -> list[list[float]]:
        for r in v:
            if len(r) != 4 or not all(abs(x) < 1e6 for x in r):
                raise ValueError("each rect needs 4 finite numbers")
        return v


class ApplyParams(Params):
    items: list[Treatment] = Field(..., tr="Uygulanacaklar", en="Treatments", min_length=1, max_length=MAX_FINDINGS)
    remove_metadata: bool = Field(True, tr="Meta veriyi temizle", en="Remove metadata")


_TR_ASCII = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")


def _ascii_mask(text: str) -> str:
    """Redaction overlay text uses a base-14 font (Latin-1); masks are short
    hints, so folding Turkish letters to ASCII is fine."""
    return text.translate(_TR_ASCII).encode("latin-1", "replace").decode("latin-1")


def _pixelated(page: pymupdf.Page, rect: pymupdf.Rect) -> bytes:
    """A mosaic of the area: ~3 cells per text line height, then smoothed —
    shapes stay, characters are gone for good."""
    from PIL import Image, ImageFilter

    pix = page.get_pixmap(clip=rect, dpi=96, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    cell = max(3.0, min(pix.width, pix.height) / 3)
    small = img.resize((max(1, int(pix.width / cell)), max(1, int(pix.height / cell))), Image.Resampling.BILINEAR)
    out = small.resize(img.size, Image.Resampling.NEAREST).filter(ImageFilter.GaussianBlur(cell / 2))
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


@register
class KvkkApply(Operation):
    name = "kvkk_apply"
    category = "redact"
    title_tr, title_en = "KVKK İşlemlerini Uygula", "Apply Personal-Data Treatments"
    description_tr = "Seçilen alanlara karartma, beyazlatma, maskeleme veya bulanıklaştırma uygular."
    description_en = "Apply black-out, white-out, masking or blur to the selected areas."
    hidden = True
    Params = ApplyParams

    def run(self, ctx: Context, params: ApplyParams) -> None:
        inp = ctx.inputs[0]
        counts: dict[str, int] = {}
        with open_pdf(inp.path, inp.password) as doc:
            by_page: dict[int, list[tuple[pymupdf.Rect, Treatment]]] = {}
            for item in params.items:
                if item.action == "keep":
                    continue
                if item.page > doc.page_count:
                    raise UserError(
                        f"Sayfa {item.page} aralık dışında (1–{doc.page_count}).",
                        f"Page {item.page} is out of range (1–{doc.page_count}).",
                    )
                page = doc[item.page - 1]
                for r in item.rects:
                    rect = from_user(r, page) & page.rect
                    if not rect.is_empty:
                        by_page.setdefault(item.page - 1, []).append((rect, item))
            if not by_page:
                raise UserError("Uygulanacak bir işlem seçilmedi.", "No treatment was selected.")
            for k, (pno, entries) in enumerate(sorted(by_page.items())):
                page = doc[pno]
                # Render blur patches from the untouched page first.
                patches = [(rect, _pixelated(page, rect)) for rect, it in entries if it.action == "blur"]
                _clear_overlapping(page, [r for r, _ in entries])
                for rect, it in entries:
                    counts[it.action] = counts.get(it.action, 0) + 1
                    if it.action == "black":
                        page.add_redact_annot(rect, fill=(0, 0, 0), cross_out=False)
                    elif it.action == "white":
                        page.add_redact_annot(rect, fill=(1, 1, 1), cross_out=False)
                    elif it.action == "mask":
                        page.add_redact_annot(
                            rect,
                            text=_ascii_mask(it.mask) or "****",
                            fontname="helv",
                            fontsize=max(5.0, min(18.0, rect.height * 0.85)),
                            fill=(1, 1, 1),
                            text_color=(0, 0, 0),
                            align=pymupdf.TEXT_ALIGN_LEFT,
                            cross_out=False,
                        )
                    else:  # blur
                        page.add_redact_annot(rect, fill=False, cross_out=False)
                page.apply_redactions(
                    images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                    graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                    text=pymupdf.PDF_REDACT_TEXT_REMOVE,
                )
                for rect, png in patches:
                    page.insert_image(rect, stream=png, keep_proportion=False, overlay=True)
                ctx.progress((k + 1) / len(by_page), "")
            if params.remove_metadata:
                strip_document_metadata(doc)
            save_pdf(doc, ctx.output(f"{inp.stem}_kvkk.pdf"), clean=True)
        ctx.data = {"applied": counts, "pages": [p + 1 for p in sorted(by_page)]}
