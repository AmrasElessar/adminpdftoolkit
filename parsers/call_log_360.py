"""360 Ankara çağrı kaydı PDF'i için özel parser.

Ham PDF metnini satır listesine açar, kayıt başlangıcını rakam-only satırla
yakalar, müşteri/telefon/durum/tarih/süre alanlarını ve S:/C: soru-cevap
bloklarını ayrıştırıp dict listesi döner.
"""
from __future__ import annotations

import re
from typing import Any

from .base import BaseParser


CALL_LOG_QUESTIONS = [
    "Ağrı / romatizma",
    "Termal / kaplıca",
    "Yaş",
    "Medeni durum",
    "Meslek",
    "İkamet ili",
]

DATE_LINE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}$")
PHONE_RE = re.compile(r"^\+?\d[\d\s]{7,}$")
STATUS_VALUES = {"ended", "completed", "missed", "failed", "no-answer", "busy"}


def _normalize_text(raw: str) -> list[str]:
    """PDF bazen '\\n' kaçışlarını literal olarak döndürüyor — normalize ediyoruz."""
    raw = raw.replace("\\n", "\n")
    return [ln.strip() for ln in raw.splitlines() if ln.strip() != ""]


def _is_record_start(line: str) -> bool:
    return line.isdigit() and 1 <= int(line) <= 999999


def _parse_qa(lines: list[str]) -> dict[str, str]:
    """S: ... satırlarını C: ... cevaplarıyla eşler (cevap çok satıra yayılabilir)."""
    result: dict[str, str] = {}
    current_q: str | None = None
    current_a: list[str] = []

    def flush() -> None:
        if current_q is not None:
            result[current_q] = " ".join(current_a).strip()

    for ln in lines:
        if ln.startswith("S:"):
            flush()
            current_q = ln[2:].strip()
            current_a = []
        elif ln.startswith("C:"):
            content = ln[2:].strip()
            if content:
                current_a.append(content)
        else:
            if current_q is not None:
                current_a.append(ln)
    flush()
    return result


class CallLog360Parser(BaseParser):
    name = "call_log_360"

    def is_match(self, doc: Any) -> bool:
        head = ""
        for i in range(min(2, len(doc))):
            head += doc[i].get_text()
        markers = ["S: Ağrı", "S: Termal", "MÜŞTERİ", "Seçilen kay"]
        return sum(m in head for m in markers) >= 2

    def parse_records(self, doc: Any) -> list[dict[str, Any]]:
        all_lines: list[str] = []
        for page in doc:
            all_lines.extend(_normalize_text(page.get_text()))

        while all_lines and "Seçilen kay" in all_lines[0]:
            all_lines.pop(0)

        records: list[dict[str, Any]] = []
        i = 0
        n = len(all_lines)

        while i < n:
            if not _is_record_start(all_lines[i]):
                i += 1
                continue

            rec_no = all_lines[i]
            i += 1
            if i >= n:
                break

            name_parts: list[str] = []
            while i < n and not PHONE_RE.match(all_lines[i]):
                if _is_record_start(all_lines[i]) and name_parts:
                    break
                name_parts.append(all_lines[i])
                i += 1
            customer = " ".join(name_parts).strip()

            phone = all_lines[i] if i < n and PHONE_RE.match(all_lines[i]) else ""
            if phone:
                i += 1

            status = all_lines[i] if i < n and all_lines[i].lower() in STATUS_VALUES else ""
            if status:
                i += 1

            date = all_lines[i] if i < n and DATE_LINE_RE.match(all_lines[i]) else ""
            if date:
                i += 1

            duration_parts: list[str] = []
            while i < n and not all_lines[i].startswith("S:") and not _is_record_start(all_lines[i]):
                duration_parts.append(all_lines[i])
                i += 1
            duration = " ".join(duration_parts).strip()

            qa_block_lines: list[str] = []
            while i < n and not _is_record_start(all_lines[i]):
                qa_block_lines.append(all_lines[i])
                i += 1

            qa = _parse_qa(qa_block_lines)

            rec: dict[str, Any] = {
                "#": rec_no,
                "Müşteri": customer,
                "Telefon": phone,
                "Durum": status,
                "Tarih": date,
                "Süre": duration,
            }
            for q in CALL_LOG_QUESTIONS:
                rec[q] = qa.get(q, "")
            rec["AI Özeti (Ham)"] = "\n".join(qa_block_lines)
            records.append(rec)

        return records
