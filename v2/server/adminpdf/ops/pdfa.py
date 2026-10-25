"""PDF/A conversion (archival PDF) without OCR.

OCRmyPDF drives Ghostscript's PDF/A writer; ``ocr_engine="none"`` with
``mode="skip"`` turns OCR off so pages are converted, never rasterised.
The result *declares* PDF/A (XMP ``pdfaid``) — a formal validator such as
veraPDF is not bundled, so conformance is not independently verified.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import pymupdf

from ..core.errors import UserError
from ..core.pdf import open_pdf
from ._ocrmypdf import find_ghostscript, plain_input, run_ocrmypdf
from .base import Context, Field, Operation, Params, register

# Text-fidelity check after conversion: compare at most this many pages.
CHECK_PAGES = 50


def pdfa_declaration(path: Path) -> dict[str, str] | None:
    """``{"part": "2", "conformance": "B"}`` from the XMP metadata, or None."""
    import pikepdf

    try:
        with pikepdf.open(path) as pdf:
            meta = pdf.open_metadata()
            part = meta.get("pdfaid:part")
            conformance = meta.get("pdfaid:conformance")
    except Exception:
        return None
    if not part:
        return None
    return {"part": str(part), "conformance": str(conformance or "")}


def _page_texts(path: Path, limit: int) -> list[str]:
    with pymupdf.open(path) as doc:
        return ["".join(doc[i].get_text().split()) for i in range(min(limit, doc.page_count))]


class PdfaParams(Params):
    level: Literal["1b", "2b", "3b"] = Field(
        "2b",
        tr="PDF/A düzeyi",
        en="PDF/A level",
        help_tr="2b çoğu arşiv için önerilir; 1b en eski sistemler, 3b ek dosya taşıyan arşivler içindir.",
        help_en="2b suits most archives; 1b is for legacy systems, 3b allows embedded files.",
        ui={
            "options": {
                "1b": {"tr": "PDF/A-1b", "en": "PDF/A-1b"},
                "2b": {"tr": "PDF/A-2b (önerilen)", "en": "PDF/A-2b (recommended)"},
                "3b": {"tr": "PDF/A-3b", "en": "PDF/A-3b"},
            }
        },
    )


@register
class Pdfa(Operation):
    name = "pdfa"
    category = "archive"
    title_tr, title_en = "PDF/A'ya Dönüştür", "Convert to PDF/A"
    description_tr = "Uzun süreli arşivleme için PDF/A-1b, 2b veya 3b biçiminde kaydeder (yazı tipleri gömülür)."
    description_en = "Save as PDF/A-1b, 2b or 3b for long-term archiving (fonts embedded)."
    Params = PdfaParams

    def run(self, ctx: Context, params: PdfaParams) -> None:
        if find_ghostscript() is None:
            raise UserError(
                "PDF/A dönüştürmek için Ghostscript gerekir ve yüklü değil.",
                "Converting to PDF/A needs Ghostscript, which is not installed.",
            )
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            page_count = doc.page_count
        part = params.level[0]
        out = ctx.output(f"{inp.stem}_pdfa-{params.level}.pdf")
        ctx.progress(0.02, "PDF/A")
        with plain_input(inp) as src:
            before = pdfa_declaration(src)
            warnings = run_ocrmypdf(
                src,
                out,
                ctx.progress,
                ocr_engine="none",
                mode="skip",
                output_type=f"pdfa-{part}",
                pdfa_backend="ghostscript",
                optimize=0,
            )
            ctx.progress(0.98, "check")
            original_text = _page_texts(src, CHECK_PAGES)
        declared = pdfa_declaration(out)
        if declared is None or declared["part"] != part:
            raise UserError("PDF/A dönüştürme başarısız oldu.", "PDF/A conversion failed.")
        changed = [
            i + 1 for i, (a, b) in enumerate(zip(original_text, _page_texts(out, CHECK_PAGES), strict=False)) if a != b
        ]
        notes: list[dict[str, str]] = [
            {
                "tr": "Biçimsel doğrulama (veraPDF) pakette yok; dosya PDF/A olarak işaretlendi ama bağımsız "
                "olarak doğrulanmadı.",
                "en": "Formal validation (veraPDF) is not bundled; the file declares PDF/A but was not "
                "independently validated.",
            }
        ]
        if changed:
            notes.append(
                {
                    "tr": "Bazı sayfalarda kopyalanan/aranan metin değişti (Ghostscript yazı tipi eşlemesi). "
                    "Görünüm aynıdır; metin gerekiyorsa sonucu kontrol edin.",
                    "en": "Copyable/searchable text changed on some pages (Ghostscript font mapping). "
                    "The appearance is the same; check the result if text matters.",
                }
            )
        data: dict[str, Any] = {
            "level": f"PDF/A-{params.level.upper()}",
            "declared": declared,
            "input_declared": before,
            "engine": "OCRmyPDF + Ghostscript",
            "validated": False,
            "pages": page_count,
            "text_changed_pages": changed[:100],
            "notes": notes,
            "warnings": warnings,
        }
        ctx.data = data
