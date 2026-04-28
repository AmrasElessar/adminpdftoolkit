"""AI helpers (Section C — light) — pymupdf + heuristics, no new deps.

These three helpers cover the "instant value" slice of Section C: anything
that doesn't need a downloaded model. The heavier features (PII via Presidio
+ Turkish BERT, summary / RAG via llama-cpp-python) live in Phase 3b/3c and
trigger a one-shot model download on first use.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .logging_setup import logger
from .pdf_tools import _save_pdf


# ----- Boş sayfa tespiti -------------------------------------------------
def detect_blank_pages(
    input_path: Path,
    *,
    threshold: float = 0.999,
    dpi: int = 50,
) -> list[int]:
    """Return 1-indexed page numbers that look blank.

    Two-pass heuristic:
      1. If the page has *any* extractable text (after stripping whitespace),
         it is **not** blank. This catches pages with sparse text that the
         pixel-share check would miss (a single line is ~99.9% bright).
      2. Otherwise, render at ``dpi``, count pixels with grayscale ≥ 240, and
         flag the page if that share ≥ ``threshold``. This catches pages with
         only images that happen to be near-white, while sparing pages with
         actual image content.

    Pure-Python: pymupdf for text + Pillow for the pixel histogram.
    """
    import fitz
    from io import BytesIO
    from PIL import Image

    if not (0.5 < threshold <= 1.0):
        raise ValueError("threshold 0.5 ile 1.0 arasında olmalı.")
    blank: list[int] = []
    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        for idx, page in enumerate(doc):
            try:
                if (page.get_text() or "").strip():
                    continue  # has text → not blank
                pix = page.get_pixmap(dpi=dpi, alpha=False)
                img = Image.open(BytesIO(pix.tobytes("png"))).convert("L")
                hist = img.histogram()
                total = sum(hist)
                if total == 0:
                    continue
                bright = sum(hist[240:])  # ≥240 grayscale ≈ near-white
                if bright / total >= threshold:
                    blank.append(idx + 1)
            except Exception as e:
                logger.debug("blank-detect: page %d skipped (%s)", idx + 1, e)
                continue
    return blank


def remove_blank_pages(
    input_path: Path,
    output: Path,
    *,
    threshold: float = 0.995,
    dpi: int = 50,
) -> tuple[int, int]:
    """Drop blank pages from a PDF. Returns (kept, removed) counts."""
    blanks = detect_blank_pages(input_path, threshold=threshold, dpi=dpi)
    import fitz

    with fitz.open(str(input_path)) as src:
        total = src.page_count
        if not blanks:
            # No blanks — write a copy with our standard save options
            _save_pdf(src, output)
            return total, 0
        if len(blanks) == total:
            raise ValueError("Tüm sayfalar boş görünüyor — silmek mantıksız.")
        keep = [p for p in range(1, total + 1) if p not in set(blanks)]
        out_doc = fitz.open()
        try:
            for p in keep:
                out_doc.insert_pdf(src, from_page=p - 1, to_page=p - 1)
            _save_pdf(out_doc, output)
        finally:
            out_doc.close()
    return total - len(blanks), len(blanks)


# ----- İmza tespiti ------------------------------------------------------
def detect_signatures(input_path: Path) -> dict[str, Any]:
    """Detect signature artefacts (form fields + digital signature flags).

    Returns a dict shaped::

        {
            "is_signed": bool,
            "field_count": int,           # widget signature fields
            "filled_count": int,          # of those, how many have a value
            "digital_signature": bool,    # /SigFlags > 0 in the PDF catalog
            "fields": [{"page", "name", "filled"}],
        }

    Best-effort: the heuristic-only signature pixel detection is *not*
    performed here (would need OpenCV); a future v1.x can layer that on.
    """
    import fitz

    out: dict[str, Any] = {
        "is_signed": False,
        "field_count": 0,
        "filled_count": 0,
        "digital_signature": False,
        "fields": [],
    }
    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        for pno, page in enumerate(doc):
            for widget in (page.widgets() or []):
                try:
                    is_sig = widget.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE
                except AttributeError:
                    is_sig = "signature" in (widget.field_type_string or "").lower()
                if not is_sig:
                    continue
                filled = bool(widget.field_value)
                out["field_count"] += 1
                if filled:
                    out["filled_count"] += 1
                out["fields"].append({
                    "page": pno + 1,
                    "name": widget.field_name or "",
                    "filled": filled,
                })
        try:
            sigflags = doc.get_sigflags()
            if sigflags and sigflags > 0:
                out["digital_signature"] = True
        except Exception:
            pass
    out["is_signed"] = (
        out["filled_count"] > 0 or out["digital_signature"]
    )
    return out


# ----- Otomatik kategorizasyon (kural tabanlı) --------------------------
_CATEGORY_PATTERNS: dict[str, list[str]] = {
    "fatura": [
        r"\bfatura\b", r"\binvoice\b", r"\bkdv\b", r"\bvergi\s+no\b",
        r"toplam\s+tutar", r"ödenecek\s+tutar", r"fatura\s+tarih(i)?",
    ],
    "dekont": [
        r"\bdekont\b", r"\bhavale\b", r"\beft\b", r"\btransfer\b",
        r"alıcı.*iban", r"gönderen.*iban", r"işlem\s+tarih(i)?",
    ],
    "sözleşme": [
        r"\bsözleşme\b", r"taraflar(\s+arası)?", r"madde\s+\d", r"\bcontract\b",
        r"hüküm.*koşul", r"imza.*tarafından", r"yürürlük",
    ],
    "ekstre": [
        r"\bekstre\b", r"hesap\s+özeti", r"\bstatement\b",
        r"\bbakiye\b", r"\bborç\b", r"\balacak\b",
    ],
    "fiş": [
        r"\bfiş\b", r"\bperakende\b", r"yazar\s*kasa",
        r"ödeme\s+yapıldı", r"\bz\s+raporu\b",
    ],
    "mektup": [
        r"\bsayın\b", r"saygılarımla", r"\bdear\b", r"sincerely",
        r"konu\s*:", r"ref\s*\.?\s*:",
    ],
    "rapor": [
        r"\brapor\b", r"\breport\b", r"yönetici\s+özeti",
        r"executive\s+summary", r"\bbölüm\s+\d",
    ],
    "form": [
        r"\bform\b", r"başvuru\s+formu", r"talep\s+formu",
        r"lütfen\s+doldur", r"please\s+fill",
    ],
    "kimlik": [
        r"\bt\.?c\.?\s*kimlik\b", r"\bkimlik\s+numar(ası|asi)\b",
        r"nüfus\s+cüzdan(ı|i)", r"\bpasaport\b", r"\bid\s+card\b",
    ],
}


def classify_pdf(
    input_path: Path,
    *,
    max_pages: int = 5,
) -> dict[str, Any]:
    """Heuristically classify a PDF into one of a fixed category set.

    Reads up to ``max_pages`` of text (default 5 — categorisation hints are
    almost always on the cover or first page) and counts regex hits per
    category. Returns the winning label, its score and the full breakdown.
    Categories: fatura / dekont / sözleşme / ekstre / fiş / mektup / rapor /
    form / kimlik / diğer.
    """
    import fitz

    text_parts: list[str] = []
    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            text_parts.append(page.get_text() or "")
    text = "\n".join(text_parts).lower()

    scores: dict[str, int] = {}
    matches: dict[str, list[str]] = {}
    for category, patterns in _CATEGORY_PATTERNS.items():
        hits: list[str] = []
        for pat in patterns:
            for m in re.finditer(pat, text, flags=re.IGNORECASE | re.UNICODE):
                hits.append(m.group(0))
        scores[category] = len(hits)
        if hits:
            matches[category] = hits[:5]

    if not text.strip():
        winner = "diğer"
        confidence = 0.0
    else:
        winner = max(scores, key=lambda k: scores[k])
        if scores[winner] == 0:
            winner = "diğer"
            confidence = 0.0
        else:
            total = sum(scores.values()) or 1
            confidence = round(scores[winner] / total, 3)

    return {
        "category": winner,
        "score": scores.get(winner, 0),
        "confidence": confidence,
        "scores": scores,
        "matches": matches,
        "text_sample_chars": len(text),
    }
