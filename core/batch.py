"""Batch parsing — top-level so it pickles cleanly for ProcessPoolExecutor."""

from __future__ import annotations

from pathlib import Path

from .errors import sanitize_error
from .files import extract_generic_table


def parse_pdf_for_batch(args: tuple) -> dict:
    """Process-pool worker: parse one PDF for the batch-Excel-merge pipeline.

    Args tuple shape depends on ``mode`` (the optional 5th element):

    * Legacy 4-tuple ``(filename, pdf_path, mapping, target_schema)`` —
      mode defaults to ``"call_log"``. Call-log detection runs first; for
      non-call-log PDFs with a user-supplied mapping, columns are mapped
      into the call-log ``target_schema``.
    * 5-tuple ``(filename, pdf_path, mapping_or_none, schema, mode)`` —
      ``mode="other_table"`` keys rows by ``schema`` (the group's common
      headers) without forcing them into the call-log layout. ``mapping``
      is unused in this mode; the table is taken verbatim and aligned to
      ``schema`` by column index.

    Returns ``{"filename", "records", "warning"}``. Failures are caught
    and reported as warnings rather than re-raised, so one bad PDF
    doesn't abort the whole batch.

    Lives in core (not app) so the spawn-mode child processes import only
    the lightweight modules — no FastAPI app instantiation per worker.
    """
    import fitz

    from pdf_converter import CALL_LOG_QUESTIONS, is_call_log_pdf, parse_call_log

    if len(args) == 5:
        filename, pdf_path_str, mapping, target_schema, mode = args
    else:
        filename, pdf_path_str, mapping, target_schema = args
        mode = "call_log"
    pdf_path = Path(pdf_path_str)
    records: list[dict] = []
    warning: str | None = None

    try:
        if mode == "other_table":
            # Same-format grup: PDF zaten /batch-analyze tarafından bu
            # gruba atanmış, yani sütunlar grubun ``target_schema``
            # (group_headers) ile aynı sırada gelecek. Mapping kullanmaya
            # gerek yok — tabloyu olduğu gibi al ve header'lara hizala.
            table = extract_generic_table(pdf_path)
            if not table or len(table) < 2:
                warning = f"{filename} atlandı (tablo bulunamadı)."
            else:
                schema = list(target_schema or [])
                for row in table[1:]:
                    rec: dict = {}
                    for i, h in enumerate(schema):
                        rec[h] = row[i] if i < len(row) else ""
                    records.append(rec)
        else:
            doc = fitz.open(pdf_path_str)
            try:
                if is_call_log_pdf(doc):
                    for rec in parse_call_log(doc):
                        records.append(
                            {
                                "Kayıt No": rec.get("#", ""),
                                "Müşteri": rec.get("Müşteri", ""),
                                "Telefon": rec.get("Telefon", ""),
                                "Durum": rec.get("Durum", ""),
                                "Tarih": rec.get("Tarih", ""),
                                "Süre": rec.get("Süre", ""),
                                **{q: rec.get(q, "") for q in CALL_LOG_QUESTIONS},
                                "AI Özeti (Ham)": rec.get("AI Özeti (Ham)", ""),
                            }
                        )
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
