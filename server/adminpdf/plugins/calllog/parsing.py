"""PDF format detection and row extraction, ported from v1 ``parsers/``.

Three formats are recognised, in v1's dispatch order:

* ``call_log`` — the 360 call-centre export (``CallLog360Parser``): plain
  text, one record per block that starts with a digits-only line, followed by
  customer / phone / status / date / duration and ``S:`` / ``C:`` Q&A lines.
* ``scanned`` — image-only pages (< 40 characters per page on average and at
  least one image): needs OCR before it can be merged.
* ``table`` — any PDF with ruled tables (v1 ``GenericTableParser``; v1 used
  pdfplumber, v2 uses PyMuPDF's ``find_tables`` with the same "lines"
  strategy). The first row is the header.

Anything else is ``unknown``; a PDF that cannot be opened is ``invalid``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ...core.errors import UserError
from ...core.pdf import open_pdf

Kind = Literal["call_log", "table", "scanned", "unknown", "invalid"]

CALL_LOG_QUESTIONS = [
    "Ağrı / romatizma",
    "Termal / kaplıca",
    "Yaş",
    "Medeni durum",
    "Meslek",
    "İkamet ili",
]
# v1 ``core.TARGET_SCHEMA`` (set in v1 app.py), bracketed by "Kayıt No" and
# "AI Özeti (Ham)" exactly as v1's merged workbook writes it.
TARGET_SCHEMA = ["Müşteri", "Telefon", "Durum", "Tarih", "Süre", *CALL_LOG_QUESTIONS]
CALL_LOG_COLUMNS = ["Kayıt No", *TARGET_SCHEMA, "AI Özeti (Ham)"]
PHONE_COLUMN = "Telefon"

KIND_LABELS: dict[str, tuple[str, str]] = {
    "call_log": ("Çağrı kayıtları", "Call logs"),
    "table": ("Tablo", "Table"),
    "scanned": ("Taranmış PDF (OCR gerekli)", "Scanned PDF (needs OCR)"),
    "unknown": ("Tablo yok", "No table"),
    "invalid": ("Açılamadı", "Could not be opened"),
}

_DATE_LINE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}$")
_PHONE_RE = re.compile(r"^\+?\d[\d\s]{7,}$")
_STATUS_VALUES = {"ended", "completed", "missed", "failed", "no-answer", "busy"}
_CALL_LOG_MARKERS = ("S: Ağrı", "S: Termal", "MÜŞTERİ", "Seçilen kay")
_SCANNED_MAX_CHARS_PER_PAGE = 40


# -- 360 call log --------------------------------------------------------------
def normalize_lines(raw: str) -> list[str]:
    """The export sometimes contains literal ``\\n`` escapes; split on both."""
    raw = raw.replace("\\n", "\n")
    return [ln.strip() for ln in raw.splitlines() if ln.strip()]


def is_record_start(line: str) -> bool:
    return line.isascii() and line.isdigit() and 1 <= int(line) <= 999_999


def parse_qa(lines: list[str]) -> dict[str, str]:
    """Pair ``S: question`` lines with their ``C: answer`` (answers may wrap)."""
    result: dict[str, str] = {}
    question: str | None = None
    answer: list[str] = []
    for ln in lines:
        if ln.startswith("S:"):
            if question is not None:
                result[question] = " ".join(answer).strip()
            question, answer = ln[2:].strip(), []
        elif ln.startswith("C:"):
            content = ln[2:].strip()
            if content:
                answer.append(content)
        elif question is not None:
            answer.append(ln)
    if question is not None:
        result[question] = " ".join(answer).strip()
    return result


def is_call_log(doc: Any) -> bool:
    head = "".join(doc[i].get_text() for i in range(min(2, doc.page_count)))
    return sum(m in head for m in _CALL_LOG_MARKERS) >= 2


def parse_call_log_lines(lines: list[str]) -> list[dict[str, str]]:
    """Faithful port of v1 ``CallLog360Parser.parse_records``."""
    while lines and "Seçilen kay" in lines[0]:
        lines = lines[1:]
    records: list[dict[str, str]] = []
    i, n = 0, len(lines)
    while i < n:
        if not is_record_start(lines[i]):
            i += 1
            continue
        rec_no = lines[i]
        i += 1
        if i >= n:
            break

        name_parts: list[str] = []
        while i < n and not _PHONE_RE.match(lines[i]):
            if is_record_start(lines[i]) and name_parts:
                break
            name_parts.append(lines[i])
            i += 1

        phone = lines[i] if i < n and _PHONE_RE.match(lines[i]) else ""
        if phone:
            i += 1
        status = lines[i] if i < n and lines[i].lower() in _STATUS_VALUES else ""
        if status:
            i += 1
        date = lines[i] if i < n and _DATE_LINE_RE.match(lines[i]) else ""
        if date:
            i += 1

        duration: list[str] = []
        while i < n and not lines[i].startswith("S:") and not is_record_start(lines[i]):
            duration.append(lines[i])
            i += 1

        qa_lines: list[str] = []
        while i < n and not is_record_start(lines[i]):
            qa_lines.append(lines[i])
            i += 1
        qa = parse_qa(qa_lines)

        rec = {
            "Kayıt No": rec_no,
            "Müşteri": " ".join(name_parts).strip(),
            "Telefon": phone,
            "Durum": status,
            "Tarih": date,
            "Süre": " ".join(duration).strip(),
        }
        for q in CALL_LOG_QUESTIONS:
            rec[q] = qa.get(q, "")
        rec["AI Özeti (Ham)"] = "\n".join(qa_lines)
        records.append(rec)
    return records


def parse_call_log(doc: Any) -> list[list[str]]:
    lines: list[str] = []
    for page in doc:
        lines.extend(normalize_lines(page.get_text()))
    return [[rec.get(c, "") for c in CALL_LOG_COLUMNS] for rec in parse_call_log_lines(lines)]


# -- scanned / tables ----------------------------------------------------------
def is_scanned(doc: Any) -> bool:
    if doc.page_count == 0:
        return False
    chars = 0
    images = False
    for page in doc:
        chars += len(page.get_text().strip())
        images = images or bool(page.get_images())
    return chars / doc.page_count < _SCANNED_MAX_CHARS_PER_PAGE and images


def _clean(value: Any) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def unique_headers(raw: list[str], reserved: tuple[str, ...] = ("Sıra", "Kaynak PDF")) -> list[str]:
    """Blank headers become ``Sütun N``; repeats (and names the merged
    workbook already uses) get a ``(2)`` suffix so no column is lost."""
    out: list[str] = []
    taken = {r.casefold() for r in reserved}
    for i, h in enumerate(raw, start=1):
        base = h.strip() or f"Sütun {i}"
        name, k = base, 2
        while name.casefold() in taken:
            name = f"{base} ({k})"
            k += 1
        taken.add(name.casefold())
        out.append(name)
    return out


def header_signature(headers: list[str]) -> str:
    return "|".join(h.strip().casefold() for h in headers if h.strip()) or "(boş başlık)"


def extract_table(doc: Any, max_rows: int) -> tuple[list[str], list[list[str]]]:
    """All ruled-table rows of the document; the first row is the header.

    Unlike v1, header rows repeated on later pages and fully empty rows are
    dropped, and rows are padded / cut to the header width.
    """
    header: list[str] | None = None
    rows: list[list[str]] = []
    for page in doc:
        for table in page.find_tables().tables:
            for raw in table.extract():
                row = [_clean(v) for v in raw]
                if not any(row):
                    continue
                if header is None:
                    header = row
                    continue
                if header_signature(row) == header_signature(header):
                    continue
                width = len(header)
                rows.append((row + [""] * width)[:width])
                if len(rows) > max_rows:
                    raise UserError(
                        f"Bir PDF'teki tablo {max_rows:,} satırdan büyük.",
                        f"A PDF's table has more than {max_rows:,} rows.",
                    )
    if header is None:
        return [], []
    return unique_headers(header), rows


# -- classification ------------------------------------------------------------
@dataclass
class Parsed:
    name: str
    kind: Kind
    pages: int = 0
    columns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    message_tr: str = ""
    message_en: str = ""
    # Set when ``rows`` was cut down to a preview sample.
    row_count: int | None = None

    @property
    def signature(self) -> str:
        """Files with equal signatures are merged into one workbook."""
        if self.kind == "table":
            return "table:" + header_signature(self.columns)
        return self.kind

    @property
    def mergeable(self) -> bool:
        return self.kind in ("call_log", "table") and bool(self.rows)


def parse_pdf(path: Path, name: str, password: str, max_rows: int) -> Parsed:
    """Detect the format of one PDF and extract its rows. Never raises for a
    bad file — v1 skipped such files with a warning instead of failing the batch."""
    try:
        with open_pdf(path, password) as doc:
            pages = doc.page_count
            if is_call_log(doc):
                return Parsed(name, "call_log", pages, list(CALL_LOG_COLUMNS), parse_call_log(doc))
            if is_scanned(doc):
                return Parsed(
                    name,
                    "scanned",
                    pages,
                    message_tr="Taranmış (görsel) PDF — önce OCR uygulayın.",
                    message_en="Scanned (image) PDF — run OCR first.",
                )
            columns, rows = extract_table(doc, max_rows)
            if columns and rows:
                return Parsed(name, "table", pages, columns, rows)
            return Parsed(
                name,
                "unknown",
                pages,
                message_tr="Tablo veya çağrı kaydı bulunamadı.",
                message_en="No table or call log found.",
            )
    except UserError as e:
        return Parsed(name, "invalid", message_tr=e.tr, message_en=e.en)
    except MemoryError:
        raise
    except Exception:
        return Parsed(
            name, "invalid", message_tr="PDF okunamadı (bozuk olabilir).", message_en="Could not read the PDF."
        )
