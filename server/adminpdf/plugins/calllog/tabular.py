"""Row tables: safe .xlsx reading/writing, duplicate removal and filtering.

The ops are stateless, so the workbook *is* the hand-off between steps: the
merge op writes it, filter / distribute read it back. Everything written goes
through :func:`safe_value`, which fixes two v1 bugs — PDF text starting with
``= + - @`` turning into live formulas, and control characters raising
openpyxl's ``IllegalCharacterError``.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core.errors import UserError
from ...ops.office import check_ooxml, to_cell

MAX_ROWS = 1_000_000
MAX_CELLS = 25_000_000
MAX_COLUMNS = 500
EXCEL_MAX_CELL_CHARS = 32_767
SUMMARY_SHEET = "Özet"
EMPTY_LABEL = "(boş)"

_SURROGATES = re.compile(r"[\ud800-\udfff]")
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")

_WIDTHS = {
    "Sıra": 7,
    "Kaynak PDF": 28,
    "Kayıt No": 10,
    "Müşteri": 28,
    "Telefon": 18,
    "Durum": 12,
    "Tarih": 18,
    "Süre": 10,
    "Ağrı / romatizma": 22,
    "Termal / kaplıca": 22,
    "Yaş": 14,
    "Medeni durum": 16,
    "Meslek": 22,
    "İkamet ili": 16,
    "AI Özeti (Ham)": 50,
}


# -- text helpers --------------------------------------------------------------
def tr_fold(value: Any) -> str:
    """Case-insensitive key that respects Turkish dotted / dotless I."""
    text = "" if value is None else str(value)
    return text.strip().replace("I", "ı").replace("İ", "i").lower()


def normalize_phone(value: Any) -> str:
    """Canonical Turkish phone key: ``+90 (532) 123 45 67``, ``0532 123 4567``,
    ``0090532…`` and ``5321234567`` all become ``5321234567``.

    v1 kept the ``+`` and the trunk ``0``, so these did not match each other.
    Numbers that are not Turkish-shaped keep all their digits.
    """
    digits = "".join(ch for ch in str(value or "") if ch in "0123456789")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 12 and digits.startswith("90"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def is_phone_column(name: str) -> bool:
    key = tr_fold(name)
    return key in ("tel", "tel.", "gsm", "cep") or any(t in key for t in ("telefon", "phone", "gsm", "cep tel"))


def safe_value(value: Any) -> Any:
    """A value openpyxl can store: control characters / lone surrogates
    removed, newlines flattened (as v1 did) and over-long text cut."""
    if value is None or isinstance(value, bool | int | float | dt.date | dt.time | dt.timedelta):
        return value
    if not isinstance(value, str):
        value = str(value)
    text = value.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    cleaned = to_cell(_SURROGATES.sub("", text), "text")
    return str(cleaned)[:EXCEL_MAX_CELL_CHARS]


def is_formula_like(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(_FORMULA_START)


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


# -- table model ---------------------------------------------------------------
@dataclass
class Table:
    columns: list[str]
    rows: list[list[Any]] = field(default_factory=list)
    title: str = "Kayıtlar"

    def index(self, column: str) -> int:
        try:
            return self.columns.index(column)
        except ValueError:
            pass
        folded = [tr_fold(c) for c in self.columns]
        key = tr_fold(column)
        if key in folded:
            return folded.index(key)
        raise UserError(
            f"Sütun bulunamadı: {column!r}. Mevcut sütunlar: {', '.join(self.columns)}",
            f"Column not found: {column!r}. Available columns: {', '.join(self.columns)}",
        )

    def renumber(self, column: str = "Sıra") -> None:
        if column in self.columns:
            i = self.columns.index(column)
            for n, row in enumerate(self.rows, start=1):
                row[i] = n


def dedup_key(row: Sequence[Any], indices: list[int], phone: list[bool]) -> str | None:
    """Composite key; ``None`` (all key cells empty) means "never a duplicate"."""
    parts = [
        normalize_phone(row[i]) if is_phone else tr_fold(as_text(row[i]))
        for i, is_phone in zip(indices, phone, strict=True)
    ]
    return "\x1f".join(parts) if any(parts) else None


def deduplicate(table: Table, columns: list[str]) -> list[int]:
    """Drop later rows whose key columns repeat an earlier row (first one
    wins, input order kept). Returns the indices of the removed rows."""
    if not columns:
        raise UserError("Mükerrer kontrolü için en az bir sütun seçin.", "Pick at least one column for duplicates.")
    indices = [table.index(c) for c in columns]
    phone = [is_phone_column(table.columns[i]) for i in indices]
    seen: set[str] = set()
    kept: list[list[Any]] = []
    removed: list[int] = []
    for n, row in enumerate(table.rows):
        key = dedup_key(row, indices, phone)
        if key is not None and key in seen:
            removed.append(n)
            continue
        if key is not None:
            seen.add(key)
        kept.append(row)
    table.rows = kept
    return removed


# -- filtering -----------------------------------------------------------------
RuleOp = Literal["equals", "not_equals", "contains", "not_contains", "in", "not_in", "empty", "not_empty"]


class FilterRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1, max_length=200)
    op: RuleOp = "equals"
    value: str | float | list[str | float] | None = None

    @model_validator(mode="after")
    def _check(self) -> FilterRule:
        if self.op in ("in", "not_in"):
            if self.value is None:
                self.value = []
            elif not isinstance(self.value, list):
                self.value = [self.value]
            if len(self.value) > 10_000:
                raise ValueError("too many values")
        elif self.op in ("equals", "not_equals", "contains", "not_contains"):
            if isinstance(self.value, list) or self.value is None:
                raise ValueError(f"'{self.op}' needs a single value")
        return self


def _matcher(rule: FilterRule, case_sensitive: bool) -> Any:
    def norm(v: Any) -> str:
        text = as_text(v)
        return text if case_sensitive else tr_fold(text)

    if rule.op == "empty":
        return lambda cell: as_text(cell) == ""
    if rule.op == "not_empty":
        return lambda cell: as_text(cell) != ""
    if rule.op in ("in", "not_in"):
        values = rule.value if isinstance(rule.value, list) else []
        wanted = {norm(v) for v in values}
        # v1's filter offered "(boş)" for empty cells.
        if any(as_text(v) in ("", EMPTY_LABEL) for v in values):
            wanted.add("")
        positive = rule.op == "in"
        return lambda cell: (norm(cell) in wanted) == positive
    target = norm(rule.value)
    if rule.op == "equals":
        return lambda cell: norm(cell) == target
    if rule.op == "not_equals":
        return lambda cell: norm(cell) != target
    if rule.op == "contains":
        return lambda cell: target in norm(cell)
    return lambda cell: target not in norm(cell)


def apply_rules(table: Table, rules: Iterable[FilterRule], *, match: str = "all", case_sensitive: bool = False) -> int:
    """Keep the rows matching all (or any) rules; returns how many were removed."""
    compiled = [(table.index(r.column), _matcher(r, case_sensitive)) for r in rules]
    if not compiled:
        return 0
    combine = all if match == "all" else any
    before = len(table.rows)
    table.rows = [row for row in table.rows if combine(test(row[i]) for i, test in compiled)]
    return before - len(table.rows)


# -- reading -------------------------------------------------------------------
def read_xlsx(path: Path, sheet: str = "") -> Table:
    """The first non-summary sheet (or ``sheet``): first non-empty row is the
    header, empty rows are skipped."""
    from openpyxl import load_workbook

    check_ooxml(path)
    with path.open("rb") as fh:
        try:
            wb = load_workbook(fh, read_only=True, data_only=True)
        except Exception as e:
            raise UserError("Excel dosyası okunamadı.", "Could not read the Excel file.") from e
        try:
            if sheet:
                if sheet not in wb.sheetnames:
                    raise UserError(
                        f"Sayfa bulunamadı: {sheet!r}. Mevcut: {', '.join(wb.sheetnames)}",
                        f"Sheet not found: {sheet!r}. Available: {', '.join(wb.sheetnames)}",
                    )
                ws = wb[sheet]
            else:
                candidates = [n for n in wb.sheetnames if n != SUMMARY_SHEET] or wb.sheetnames
                ws = wb[candidates[0]]
            header: list[str] | None = None
            rows: list[list[Any]] = []
            cells = 0
            for raw in ws.iter_rows(values_only=True):
                if not any(v is not None and as_text(v) != "" for v in raw):
                    continue
                if header is None:
                    values = [as_text(v) for v in raw]
                    while values and not values[-1]:
                        values.pop()
                    if len(values) > MAX_COLUMNS:
                        raise UserError(
                            f"En fazla {MAX_COLUMNS} sütun desteklenir.",
                            f"At most {MAX_COLUMNS} columns are supported.",
                        )
                    from .parsing import unique_headers

                    header = unique_headers(values, reserved=())
                    continue
                width = len(header)
                row = list(raw[:width])
                if len(row) < width:
                    row.extend([None] * (width - len(row)))
                rows.append(row)
                cells += width
                if len(rows) > MAX_ROWS or cells > MAX_CELLS:
                    raise UserError(
                        f"Çalışma kitabı çok büyük (en fazla {MAX_ROWS:,} satır).",
                        f"The workbook is too large (at most {MAX_ROWS:,} rows).",
                    )
            title = str(ws.title)
        finally:
            wb.close()
    if header is None:
        raise UserError("Excel sayfası boş.", "The worksheet is empty.")
    return Table(header, rows, title)


# -- writing -------------------------------------------------------------------
class SheetWriter:
    """Write-only (streaming) worksheet whose every cell is sanitised."""

    def __init__(self, wb: Any, title: str) -> None:
        self.ws = wb.create_sheet(_sheet_title(title))

    def _cell(self, value: Any, *, bold: bool = False, header: bool = False) -> Any:
        from openpyxl.cell import WriteOnlyCell
        from openpyxl.styles import Alignment, Font, PatternFill

        v = safe_value(value)
        cell = WriteOnlyCell(self.ws, value=v)
        if is_formula_like(v):
            # Literal text, never a formula (CSV/Excel injection).
            cell.data_type = "s"
        if header:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="2F5496")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        elif bold:
            cell.font = Font(bold=True)
        return cell

    def widths(self, columns: Sequence[str]) -> None:
        from openpyxl.utils import get_column_letter

        for i, c in enumerate(columns, start=1):
            self.ws.column_dimensions[get_column_letter(i)].width = _WIDTHS.get(c, 18)

    def header(self, columns: Sequence[str]) -> None:
        self.ws.append([self._cell(c, header=True) for c in columns])

    def row(self, values: Iterable[Any], *, bold: bool = False) -> None:
        self.ws.append([self._cell(v, bold=bold) for v in values])


def _sheet_title(title: str) -> str:
    cleaned = re.sub(r"[\[\]:*?/\\]", "_", safe_value(title) or "Sayfa").strip("'") or "Sayfa"
    return cleaned[:31]


SummaryBlock = tuple[str, list[str], list[list[Any]]]


def write_workbook(path: Path, table: Table, summary: list[SummaryBlock]) -> None:
    """``table`` as a frozen, filterable data sheet plus an ``Özet`` sheet
    made of titled blocks ``(title, header, rows)``."""
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    wb = Workbook(write_only=True)
    data = SheetWriter(wb, table.title)
    data.widths(table.columns)
    data.ws.freeze_panes = "A2"
    last_col = get_column_letter(max(1, len(table.columns)))
    data.ws.auto_filter.ref = f"A1:{last_col}{len(table.rows) + 1}"
    data.header(table.columns)
    for row in table.rows:
        data.row(row)
    if summary:
        write_summary(SheetWriter(wb, SUMMARY_SHEET), summary)
    wb.save(path)


def write_summary(sheet: SheetWriter, blocks: list[SummaryBlock]) -> None:
    from openpyxl.utils import get_column_letter

    widest = max((len(h) for _, h, _ in blocks), default=1)
    for i in range(1, widest + 1):
        sheet.ws.column_dimensions[get_column_letter(i)].width = 34 if i == 1 else 20
    for n, (title, header, rows) in enumerate(blocks):
        if n:
            sheet.row([])
        sheet.row([title], bold=True)
        if header:
            sheet.header(header)
        for r in rows:
            sheet.row(r)
