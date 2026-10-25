"""Repair damaged PDFs.

qpdf (via pikepdf) reconstructs a broken cross-reference table and rewrites
the file; MuPDF's own repair is the fallback and is preferred when it recovers
more pages. Optionally linearises the result ("fast web view").
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

import pikepdf
import pymupdf

from ..core.errors import UserError
from .base import Context, Field, Operation, Params, register


class RepairParams(Params):
    linearize: bool = Field(
        False,
        tr="Hızlı web görünümü (doğrusallaştır)",
        en="Fast web view (linearise)",
        help_tr="İlk sayfanın indirme tamamlanmadan gösterilmesini sağlar.",
        help_en="Lets the first page display before the whole file has downloaded.",
    )


def _page_count(path: Path, password: str) -> int:
    try:
        with pymupdf.open(path) as doc:
            if doc.needs_pass and not doc.authenticate(password):
                return -1
            return int(doc.page_count)
    except Exception:
        return 0


def _qpdf_rewrite(src: Path, out: Path, password: str, linearize: bool) -> list[str]:
    with pikepdf.open(src, password=password, attempt_recovery=True) as pdf:
        warnings = [str(w) for w in pdf.get_warnings()]
        pdf.save(
            out,
            linearize=linearize,
            object_stream_mode=pikepdf.ObjectStreamMode.disable if linearize else pikepdf.ObjectStreamMode.generate,
            compress_streams=True,
            encryption=bool(pdf.is_encrypted),
        )
    return warnings


@register
class Repair(Operation):
    name = "repair"
    category = "optimize"
    title_tr, title_en = "PDF Onar", "Repair PDF"
    description_tr = "Bozuk veya açılmayan PDF'in yapısını yeniden kurar ve kurtarılabilen sayfaları kaydeder."
    description_en = "Rebuild the structure of a damaged PDF and save every recoverable page."
    # A PDF too damaged for MuPDF to open is stored as "other"; accept it and
    # check the header here instead.
    accepts = frozenset({"pdf", "other"})
    Params = RepairParams

    def run(self, ctx: Context, params: RepairParams) -> None:
        inp = ctx.inputs[0]
        with inp.path.open("rb") as fh:
            if b"%PDF-" not in fh.read(1024):
                raise UserError("Dosya bir PDF değil.", "The file is not a PDF.")
        out = ctx.output(f"{inp.stem}_onarilmis.pdf")
        warnings: list[str] = []
        method = ""
        ctx.progress(0.1, "qpdf")
        try:
            warnings = _qpdf_rewrite(inp.path, out, inp.password, params.linearize)
            method = "qpdf"
        except pikepdf.PasswordError as e:
            raise UserError(
                "PDF şifreli — doğru şifreyi girin.", "The PDF is password-protected — enter the correct password."
            ) from e
        except Exception:
            method = ""
        qpdf_pages = _page_count(out, inp.password) if method else 0
        mupdf_pages = _page_count(inp.path, inp.password)
        if mupdf_pages == -1:
            raise UserError(
                "PDF şifreli — doğru şifreyi girin.", "The PDF is password-protected — enter the correct password."
            )
        ctx.progress(0.5, "mupdf")
        if mupdf_pages > qpdf_pages:
            method = self._mupdf_rewrite(inp.path, out, inp.password, params.linearize) or method
        pages = _page_count(out, inp.password) if method else 0
        if pages <= 0:
            raise UserError(
                "PDF onarılamadı; kurtarılabilir sayfa bulunamadı.", "The PDF could not be repaired; no pages found."
            )
        name = str(inp.path)
        data: dict[str, Any] = {
            "method": method,
            "pages": pages,
            "repaired": bool(warnings) or method.startswith("mupdf"),
            "linearized": params.linearize,
            "warnings": [w.replace(name, "PDF")[:300] for w in warnings[:20]],
        }
        ctx.data = data

    @staticmethod
    def _mupdf_rewrite(src: Path, out: Path, password: str, linearize: bool) -> str:
        try:
            with pymupdf.open(src) as doc, tempfile.TemporaryDirectory(prefix="apt-repair-") as tmp:
                if doc.needs_pass:
                    doc.authenticate(password)
                tmp_out = Path(tmp) / "repaired.pdf"
                # Default save keeps the original encryption.
                doc.save(tmp_out, garbage=4, clean=True, deflate=True)
                if linearize:
                    _qpdf_rewrite(tmp_out, out, password, linearize)
                else:
                    shutil.move(tmp_out, out)
        except Exception:
            return ""
        return "mupdf"
