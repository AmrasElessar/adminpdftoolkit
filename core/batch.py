"""Batch parsing — top-level so it pickles cleanly for ProcessPoolExecutor."""

from __future__ import annotations

from pathlib import Path

from .errors import sanitize_error
from .files import extract_generic_table


def parse_pdf_for_batch(args: tuple) -> dict:
    """Process-pool worker: parse one PDF for the batch-Excel-merge pipeline.

    Args is a 4-tuple ``(filename, pdf_path_str, mapping_or_none,
    target_schema)``; see ``_batch_convert_worker`` for the call site. Returns
    ``{"filename", "records", "warning"}``. Failures are caught and reported
    as warnings rather than re-raised, so one bad PDF doesn't abort the whole
    batch.

    Lives in core (not app) so the spawn-mode child processes import only
    the lightweight modules — no FastAPI app instantiation per worker.
    """
    import fitz
    from pdf_converter import is_call_log_pdf, parse_call_log, CALL_LOG_QUESTIONS

    filename, pdf_path_str, mapping, target_schema = args
    pdf_path = Path(pdf_path_str)
    records: list[dict] = []
    warning: str | None = None

    try:
        doc = fitz.open(pdf_path_str)
        try:
            if is_call_log_pdf(doc):
                for rec in parse_call_log(doc):
                    records.append({
                        "Kayıt No": rec.get("#", ""),
                        "Müşteri": rec.get("Müşteri", ""),
                        "Telefon": rec.get("Telefon", ""),
                        "Durum": rec.get("Durum", ""),
                        "Tarih": rec.get("Tarih", ""),
                        "Süre": rec.get("Süre", ""),
                        **{q: rec.get(q, "") for q in CALL_LOG_QUESTIONS},
                        "AI Özeti (Ham)": rec.get("AI Özeti (Ham)", ""),
                    })
            elif mapping:
                table = extract_generic_table(pdf_path)
                if not table or len(table) < 2:
                    warning = f"{filename} atlandı (tablo bulunamadı)."
                else:
                    for row in table[1:]:
                        mapped_rec: dict = {"Kayıt No": "", "AI Özeti (Ham)": ""}
                        for tgt, src_idx in mapping.items():
                            if src_idx is None or src_idx == "":
                                continue
                            try:
                                si = int(src_idx)
                            except (TypeError, ValueError):
                                continue
                            if 0 <= si < len(row):
                                mapped_rec[tgt] = row[si]
                        for t in target_schema:
                            mapped_rec.setdefault(t, "")
                        records.append(mapped_rec)
            else:
                warning = f"{filename} atlandı (sütun eşlemesi yapılmamış)."
        finally:
            doc.close()
    except Exception as e:
        warning = f"{filename} atlandı: {sanitize_error(e)}"
    return {"filename": filename, "records": records, "warning": warning}
