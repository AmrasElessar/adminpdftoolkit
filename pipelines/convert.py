"""Single-PDF and Word/JPG-batch convert pipelines.

Three workers live here:

* :func:`convert_worker` — a single PDF → Excel / Word / JPG (.zip).
* :func:`batch_files_worker` — N PDFs → one ZIP of .docx or per-PDF JPG dirs.
* :class:`Pdf2DocxProgressHandler` — logging shim that turns pdf2docx's
  ``(i/N)`` progress lines into per-page progress on the convert job.
"""

from __future__ import annotations

import logging
import re
import shutil
import zipfile
from pathlib import Path

import core
from core import logger, sanitize_error
from pdf_converter import (
    convert_to_jpg,
    convert_to_word,
    is_call_log_pdf,
    is_scanned_pdf,
    parse_call_log,
    write_call_log_excel,
    write_generic_excel,
)
from state import batch_store, convert_store


class Pdf2DocxProgressHandler(logging.Handler):
    """Listens to ``pdf2docx``'s ``(i/N) Page i`` info lines and forwards
    them as per-page progress on a convert job."""

    _RE = re.compile(r"\((\d+)/(\d+)\)")

    def __init__(self, token: str) -> None:
        super().__init__(level=logging.INFO)
        self.token = token

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            m = self._RE.search(msg)
            if not m:
                return
            cur, total = int(m.group(1)), int(m.group(2))
            convert_store.update(self.token, current=cur, total=total)
        except Exception:
            pass


def convert_worker(
    token: str,
    pdf_path: Path,
    target: str,
    custom_name: str,
    job_dir: Path,
    orig_filename: str,
    jpg_quality: int = 90,
    skip_safety: bool = False,
    jpg_dpi: int = 200,
) -> None:
    """Single-PDF convert worker. ``target`` ∈ ``{word, excel, jpg}``."""
    try:
        import fitz as _fitz

        # Phase 1: ClamAV + structural safety scan (cancellable via skip_safety
        # flag set on the store). Skipped if the request explicitly opted out.
        if not skip_safety:
            from pipelines.safety import scan_single_file

            ok, err = scan_single_file(convert_store, token, pdf_path, orig_filename)
            if not ok:
                convert_store.update(token, error=err or "Güvensiz PDF reddedildi.", done=True)
                return

        stem = Path(orig_filename).stem
        safe_custom = core.safe_filename(custom_name.strip()) if custom_name else ""
        final_stem = safe_custom or core.safe_filename(stem)

        convert_store.update(token, phase="preparing", current=0, last_file=None)

        doc = _fitz.open(str(pdf_path))
        total_pages = len(doc)
        convert_store.update(token, total=total_pages)

        if target in ("word", "excel") and is_scanned_pdf(doc):
            doc.close()
            raise RuntimeError(
                "Bu PDF taranmış (metin katmanı yok). 'OCR ile Dene' butonunu kullanın."
            )

        if target == "jpg":
            convert_store.update(token, phase="rendering")
            zoom = jpg_dpi / 72
            mat = _fitz.Matrix(zoom, zoom)
            jpg_dir = job_dir / final_stem
            jpg_dir.mkdir(parents=True, exist_ok=True)
            files: list[Path] = []
            try:
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    out = jpg_dir / f"sayfa_{i + 1:03d}.jpg"
                    pix.save(str(out), jpg_quality=jpg_quality)
                    pix = None  # release Pixmap eagerly so 100+ page batches don't bloat
                    files.append(out)
                    convert_store.update(token, current=i + 1)
            finally:
                doc.close()
            zip_path = job_dir / f"{final_stem}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    zf.write(f, arcname=f"{final_stem}/{f.name}")
            shutil.rmtree(jpg_dir, ignore_errors=True)
            convert_store.update(
                token,
                output_path=str(zip_path),
                output_name=f"{final_stem}.zip",
                media_type="application/zip",
                phase="done",
                done=True,
            )
            return

        if target == "word":
            doc.close()
            convert_store.update(token, phase="converting", current=0)

            pdf2docx_logger = logging.getLogger("pdf2docx")
            old_level = pdf2docx_logger.level
            pdf2docx_logger.setLevel(logging.INFO)
            handler = Pdf2DocxProgressHandler(token)
            pdf2docx_logger.addHandler(handler)
            try:
                out = job_dir / f"{final_stem}.docx"
                convert_to_word(pdf_path, out)
            finally:
                pdf2docx_logger.removeHandler(handler)
                pdf2docx_logger.setLevel(old_level)

            convert_store.update(
                token,
                current=total_pages,
                output_path=str(out),
                output_name=f"{final_stem}.docx",
                media_type=(
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
                phase="done",
                done=True,
            )
            return

        # excel
        try:
            convert_store.update(token, phase="writing")
            out = job_dir / f"{final_stem}.xlsx"
            record_count: int | None = None
            if is_call_log_pdf(doc):
                records = parse_call_log(doc)
                record_count = len(records)
                write_call_log_excel(records, out)
            else:
                write_generic_excel(doc, out)
        finally:
            doc.close()

        convert_store.update(
            token,
            current=total_pages,
            output_path=str(out),
            output_name=f"{final_stem}.xlsx",
            media_type=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            record_count=record_count,
            phase="done",
            done=True,
        )
    except Exception as e:
        logger.exception("convert worker failed (token=%s)", token)
        convert_store.update(token, error=sanitize_error(e), done=True)
    finally:
        snap = convert_store.snapshot(token)
        if snap:
            core.persist_job_state("convert", token, snap)


def batch_files_worker(
    token: str,
    files_data: list[tuple[str, Path]],
    target: str,
    job_dir: Path,
    custom_names: list[str] | None = None,
    jpg_quality: int = 90,
    skip_safety: bool = False,
    jpg_dpi: int = 200,
) -> None:
    """Word / JPG / Excel per-file batch worker — each PDF produces its own
    output and they're all bundled into a single ZIP.

    Target ∈ ``{word, jpg, excel}``. For Excel, each PDF is auto-detected:
    call-log layout → call-log style sheet; otherwise → generic Excel
    (page-by-page text dump). No skipping, no column mapping required —
    every PDF gets a usable Excel.
    """
    try:
        # Phase 1: per-file safety scan (cancellable). Saved files that fail
        # are dropped from files_data; the user can also press "Atla" to skip
        # remaining scans entirely.
        if not skip_safety:
            from pipelines.safety import scan_files_with_progress

            ok, err = scan_files_with_progress(batch_store, token, files_data)
            if not ok:
                batch_store.update(token, error=err or "Güvensiz PDF reddedildi.", done=True)
                return

        # Initialize per-file progress so frontend can render rows immediately
        files_progress = [
            {
                "name": fn,
                "status": "pending",
                "kind": None,
                "kind_label": None,
                "record_count": 0,
                "error": None,
            }
            for fn, _ in files_data
        ]
        zip_path = job_dir / "_output.zip"
        produced = 0
        batch_store.update(
            token,
            phase="processing",
            current=0,
            last_file=None,
            files_progress=files_progress,
        )
        # Accumulator for call-log records across multiple PDFs — when target
        # is Excel and any of the input PDFs match the call-log layout, we
        # also produce a single merged "_cagrilar_birlesik.xlsx" inside the
        # ZIP. Generic / scanned PDFs still get their own per-file Excel.
        merged_call_log: list[dict] = []
        merged_call_log_sources: list[str] = []

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, (filename, pdf_path) in enumerate(files_data):
                orig_stem = Path(filename).stem
                custom = ""
                if custom_names and i < len(custom_names):
                    custom = (custom_names[i] or "").strip()
                stem = core.safe_filename(custom) if custom else core.safe_filename(orig_stem)
                if not stem:
                    stem = "output"

                files_progress[i]["status"] = "processing"
                batch_store.update(
                    token, current=i, last_file=filename, files_progress=files_progress
                )

                try:
                    if target == "word":
                        out = job_dir / f"{stem}.docx"
                        convert_to_word(pdf_path, out)
                        zf.write(out, arcname=f"{stem}.docx")
                        out.unlink(missing_ok=True)
                        files_progress[i]["kind"] = "word"
                        files_progress[i]["kind_label"] = "Word belgesi"
                    elif target == "excel":
                        # Per-file kind detection. Call-log PDFs are also
                        # accumulated for the merged sheet at the end.
                        out = job_dir / f"{stem}.xlsx"
                        import fitz as _fitz

                        doc = _fitz.open(str(pdf_path))
                        try:
                            if is_call_log_pdf(doc):
                                records = parse_call_log(doc)
                                write_call_log_excel(records, out)
                                files_progress[i]["kind"] = "call_log"
                                files_progress[i]["kind_label"] = "Çağrı kayıtları"
                                files_progress[i]["record_count"] = len(records)
                                merged_call_log.extend(records)
                                merged_call_log_sources.append(filename)
                            elif is_scanned_pdf(doc):
                                write_generic_excel(doc, out)
                                files_progress[i]["kind"] = "scanned"
                                files_progress[i]["kind_label"] = "Görselden PDF"
                            else:
                                kind_label = "Metin belgesi"
                                try:
                                    from core.analysis import classify_pdf

                                    cat = classify_pdf(pdf_path).get("category")
                                    if cat and cat != "diğer":
                                        kind_label = cat.capitalize()
                                except Exception:
                                    pass
                                write_generic_excel(doc, out)
                                files_progress[i]["kind"] = "generic"
                                files_progress[i]["kind_label"] = kind_label
                        finally:
                            doc.close()
                        zf.write(out, arcname=f"{stem}.xlsx")
                        out.unlink(missing_ok=True)
                    else:  # jpg
                        out_dir = job_dir / stem
                        jpgs = convert_to_jpg(
                            pdf_path, out_dir, dpi=jpg_dpi, jpg_quality=jpg_quality
                        )
                        for j in jpgs:
                            zf.write(j, arcname=f"{stem}/{j.name}")
                        shutil.rmtree(out_dir, ignore_errors=True)
                        files_progress[i]["kind"] = "jpg"
                        files_progress[i]["kind_label"] = "Sayfa görselleri"
                    files_progress[i]["status"] = "done"
                    produced += 1
                except Exception as inner_exc:
                    files_progress[i]["status"] = "error"
                    files_progress[i]["error"] = sanitize_error(inner_exc)
                    logger.warning("batch-files: %s failed: %s", filename, inner_exc)

                pdf_path.unlink(missing_ok=True)
                batch_store.update(
                    token,
                    current=i + 1,
                    last_file=filename,
                    files_progress=files_progress,
                )

            # Bonus output: if we accumulated call-log records from 2+ PDFs,
            # also write a merged Excel — gives the user the "20 dosya, 5'i
            # call-log → tek dosyada birleştir" behaviour for free.
            if target == "excel" and len(merged_call_log_sources) >= 2:
                merged_out = job_dir / "_cagrilar_birlesik.xlsx"
                try:
                    write_call_log_excel(merged_call_log, merged_out)
                    zf.write(merged_out, arcname="_cagrilar_birlesik.xlsx")
                    merged_out.unlink(missing_ok=True)
                    logger.info(
                        "batch-files: merged %d call-log records from %d PDFs",
                        len(merged_call_log),
                        len(merged_call_log_sources),
                    )
                except Exception as merge_exc:
                    logger.warning("batch-files merged sheet failed: %s", merge_exc)

        zip_name = f"pdfler_{target}_{produced}.zip"
        batch_store.update(
            token,
            output_path=str(zip_path),
            output_name=zip_name,
            produced=produced,
            phase="done",
            done=True,
        )
    except Exception as e:
        logger.exception("batch-files worker failed (token=%s)", token)
        batch_store.update(token, error=sanitize_error(e), done=True)
    finally:
        snap = batch_store.snapshot(token)
        if snap:
            core.persist_job_state("batch", token, snap)
