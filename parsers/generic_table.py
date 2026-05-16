"""Generic table extraction (pdfplumber tabanlı).

Hem `/pdf/to-csv` (CSV çıktısı) hem batch-analyze preview (raw rows) hem de
"call-log değil" Excel fallback senaryosu için tek bir kaynak. Önceden
``core.extract_generic_table`` ve ``core.pdf_to_csv`` aynı işi iki yerde
yapıyordu.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .base import BaseParser


class GenericTableParser(BaseParser):
    name = "generic_table"

    def is_match(self, doc: Any) -> bool:
        # Last-resort fallback — registry sırasına güvenir, kendisi her zaman
        # eşleşir. classify() çağrısı boşa düşmesin diye en sona yerleşir.
        return True

    def extract_rows(self, pdf_path: Path) -> list[list[str]]:
        """Quick-and-best-effort table extraction for preview or raw inspection."""
        import pdfplumber

        rows: list[list[str]] = []
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables() or []
                    for tbl in tables:
                        for row in tbl:
                            rows.append([(c or "").strip() for c in row])
        except Exception:  # pragma: no cover — pdfplumber failure mode
            return rows
        return rows

    # Cap CSV output to defend against pathological PDFs (e.g. a scanned
    # table with millions of rows or a parser bug producing infinite output).
    _CSV_MAX_ROWS = 100_000

    def to_csv(
        self,
        input_path: Path,
        output: Path,
        *,
        table_index: int | None = None,
        delimiter: str = ",",
    ) -> int:
        """Extract embedded tables and write a CSV. Returns row count.

        Capped at ``_CSV_MAX_ROWS`` rows; once reached, extraction stops
        early and a warning row is appended so the operator knows the
        output is partial.
        """
        import pdfplumber

        rows: list[list[str]] = []
        table_count = 0
        target = (table_index - 1) if table_index else None
        found = False
        truncated = False

        with pdfplumber.open(str(input_path)) as pdf:
            for page in pdf.pages:
                if len(rows) >= self._CSV_MAX_ROWS:
                    truncated = True
                    break
                for tbl in page.extract_tables() or []:
                    table_count += 1
                    if target is not None:
                        if table_count - 1 != target:
                            continue
                        found = True
                        for r in tbl:
                            if len(rows) >= self._CSV_MAX_ROWS:
                                truncated = True
                                break
                            rows.append([(c or "").strip() for c in r])
                        break
                    else:
                        if rows:
                            rows.append([])  # blank separator
                        for r in tbl:
                            if len(rows) >= self._CSV_MAX_ROWS:
                                truncated = True
                                break
                            rows.append([(c or "").strip() for c in r])
                    if truncated:
                        break
                if (target is not None and found) or truncated:
                    break

        if not rows:
            if target is not None:
                raise ValueError(f"PDF'te {table_index}. tablo bulunamadı (toplam {table_count}).")
            raise ValueError("Bu PDF formatına uygun parser yok.")

        if truncated:
            rows.append([])
            rows.append(
                [f"# UYARI: {self._CSV_MAX_ROWS} satır üst sınırına ulaşıldı, çıktı kesildi."]
            )

        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8-sig", newline="") as fp:
            writer = csv.writer(fp, delimiter=delimiter)
            writer.writerows(rows)
        return sum(1 for r in rows if r)
