"""OCR: make scanned PDFs searchable with OCRmyPDF + Tesseract.

OCRmyPDF runs in-process (single job, threads) inside the job worker; its
progress bars are forwarded to the job through the plugin hook in
``_ocrmypdf``. The visible page stays as it is (except in ``force`` mode) and
an invisible, selectable text layer is added on top.
"""

from __future__ import annotations

import shutil
from functools import lru_cache
from typing import Any, Literal

from ..core import proc
from ..core.errors import UserError
from ..core.pdf import open_pdf, parse_page_spec
from ..core.tools import bundled_ocr, find_tool, use_user_tessdata
from ._ocrmypdf import find_ghostscript, plain_input, run_ocrmypdf
from .base import Context, Field, Operation, Params, register

LANGS_RE = r"^[A-Za-z_]{3,20}(\+[A-Za-z_]{3,20}){0,7}$"


TESSERACT_URL = "https://github.com/UB-Mannheim/tesseract/wiki"


def find_tesseract() -> str | None:
    # The Windows package's own, verified copy comes first: it works offline
    # and is known to carry the Turkish data.
    exe, _problem = bundled_ocr()
    if exe:
        return exe
    use_user_tessdata()
    return find_tool(
        ("tesseract",),
        windows_globs=("Tesseract-OCR/tesseract.exe",),
        unix_paths=("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"),
    )


def tesseract_languages() -> frozenset[str]:
    """Installed Tesseract language packs (empty if Tesseract is missing)."""
    exe = find_tesseract()
    return _languages(exe) if exe else frozenset()


@lru_cache(maxsize=4)
def _languages(exe: str) -> frozenset[str]:
    try:
        result = proc.run([exe, "--list-langs"], timeout=30)
    except (UserError, OSError):
        return frozenset()
    text = (result.stdout + result.stderr).decode("utf-8", "replace")
    langs = {
        line.strip()
        for line in text.splitlines()
        if line.strip() and " " not in line.strip() and not line.strip().endswith(":")
    }
    return frozenset(langs)


def pages_option(indices: list[int]) -> str:
    """0-based page indices → OCRmyPDF's 1-based ``"1-3,7"`` syntax."""
    nums = sorted({i + 1 for i in indices})
    ranges: list[str] = []
    start = prev = nums[0]
    for n in [*nums[1:], -1]:
        if n == prev + 1:
            prev = n
            continue
        ranges.append(f"{start}-{prev}" if prev > start else str(start))
        start = prev = n
    return ",".join(ranges)


class OcrParams(Params):
    languages: str = Field(
        "tur+eng",
        tr="Diller",
        en="Languages",
        help_tr="Tesseract dil kodları, '+' ile: tur+eng, tur, eng…",
        help_en="Tesseract language codes joined by '+': tur+eng, tur, eng…",
        max_length=200,
        pattern=LANGS_RE,
    )
    mode: Literal["skip", "redo", "force"] = Field(
        "skip",
        tr="Metin içeren sayfalar",
        en="Pages that already have text",
        ui={
            "options": {
                "skip": {"tr": "Atla (yalnızca taranmış sayfalar)", "en": "Skip (scanned pages only)"},
                "redo": {"tr": "Eski OCR katmanını yenile", "en": "Replace the old OCR layer"},
                "force": {"tr": "Her şeyi görüntüye çevirip OCR yap", "en": "Rasterise everything and OCR"},
            }
        },
    )
    deskew: bool = Field(False, tr="Eğriliği düzelt", en="Deskew pages")
    rotate_pages: bool = Field(True, tr="Sayfa yönünü otomatik düzelt", en="Auto-rotate pages")
    optimize: int = Field(
        1,
        tr="Boyut iyileştirme (0–3)",
        en="Size optimisation (0–3)",
        help_tr="0 kapalı, 1 kayıpsız; 2–3 kayıplı (pngquant/jbig2 varsa daha etkili).",
        help_en="0 off, 1 lossless; 2–3 lossy (more effective with pngquant/jbig2).",
        ge=0,
        le=3,
    )
    archive: bool = Field(
        False,
        tr="PDF/A-2b olarak kaydet",
        en="Save as PDF/A-2b",
        help_tr="Arşivleme için; Ghostscript gerekir.",
        help_en="For archiving; needs Ghostscript.",
    )
    pages: str = Field("", tr="Sayfalar (boş = tümü)", en="Pages (empty = all)", max_length=2000)


@register
class Ocr(Operation):
    name = "ocr"
    category = "ocr"
    title_tr, title_en = "OCR (Metin Tanıma)", "OCR (Text Recognition)"
    description_tr = "Taranmış PDF'lere aranabilir ve kopyalanabilir görünmez bir metin katmanı ekler."
    description_en = "Add an invisible, searchable and copyable text layer to scanned PDFs."
    Params = OcrParams

    def run(self, ctx: Context, params: OcrParams) -> None:
        if find_tesseract() is None:
            if bundled_ocr()[1] == "damaged":
                raise UserError(
                    "Paketteki OCR dosyaları bozuk ya da değiştirilmiş; güvenlik için kullanılmadı. "
                    "Uygulama klasöründeki 'OCR Onar (Windows).bat' dosyasını çalıştırın veya paketi yeniden çıkarın.",
                    "The bundled OCR files are damaged or were altered, so they were not used. Run "
                    "'OCR Onar (Windows).bat' in the app folder or extract the package again.",
                )
            raise UserError(
                "OCR motoru (Tesseract) bulunamadı. Windows'ta uygulama klasöründeki 'OCR Kur (Windows).bat' "
                f"dosyasını çalıştırın ya da {TESSERACT_URL} adresinden kurup 'Additional language data' "
                "altından Turkish'i seçin; sonra uygulamayı yeniden başlatın.",
                "The OCR engine (Tesseract) was not found. On Windows run 'OCR Kur (Windows).bat' in the app "
                f"folder, or install it from {TESSERACT_URL} and tick Turkish under 'Additional language data'; "
                "then restart the app.",
            )
        installed = tesseract_languages()
        languages = list(dict.fromkeys(params.languages.split("+")))
        missing = [lang for lang in languages if lang not in installed]
        if missing:
            have = ", ".join(sorted(installed - {"osd"})) or "—"
            raise UserError(
                f"Dil paketi yüklü değil: {', '.join(missing)}. Yüklü diller: {have}. "
                "Windows'ta 'OCR Kur (Windows).bat' Türkçe paketi ekler.",
                f"Language pack not installed: {', '.join(missing)}. Installed: {have}. "
                "On Windows, 'OCR Kur (Windows).bat' adds the Turkish data.",
            )
        notes: list[dict[str, str]] = []
        options: dict[str, Any] = {
            "language": languages,
            "mode": params.mode,
            "optimize": params.optimize,
            "output_type": "pdfa-2" if params.archive else "pdf",
        }
        if params.archive and find_ghostscript() is None:
            raise UserError(
                "PDF/A için Ghostscript gerekir ve yüklü değil.", "PDF/A needs Ghostscript, which is not installed."
            )
        if params.deskew:
            if params.mode == "redo":
                notes.append(
                    {
                        "tr": "Yeniden OCR kipinde eğrilik düzeltme uygulanamaz; atlandı.",
                        "en": "Deskew cannot be combined with redo mode; skipped.",
                    }
                )
            else:
                options["deskew"] = True
        if params.rotate_pages:
            if "osd" in installed:
                options["rotate_pages"] = True
            else:
                notes.append(
                    {
                        "tr": "Yön algılama paketi (osd) yüklü değil; otomatik döndürme atlandı.",
                        "en": "Orientation data (osd) is not installed; auto-rotation skipped.",
                    }
                )
        if params.optimize >= 2 and not (shutil.which("pngquant") or shutil.which("jbig2")):
            notes.append(
                {
                    "tr": "pngquant/jbig2 yüklü değil; kayıplı iyileştirme sınırlı uygulandı.",
                    "en": "pngquant/jbig2 are not installed; lossy optimisation is limited.",
                }
            )

        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            page_count = doc.page_count
            targets = parse_page_spec(params.pages, page_count)
        if params.pages.strip():
            options["pages"] = pages_option(targets)

        out = ctx.output(f"{inp.stem}_ocr.pdf")
        ctx.progress(0.01, "OCR")
        with plain_input(inp) as src:
            warnings = run_ocrmypdf(src, out, ctx.progress, **options)
        ctx.data = {
            "languages": languages,
            "mode": params.mode,
            "pages": len(set(targets)),
            "page_count": page_count,
            "optimize": params.optimize,
            "pdfa": params.archive,
            "notes": notes,
            "warnings": warnings,
        }
