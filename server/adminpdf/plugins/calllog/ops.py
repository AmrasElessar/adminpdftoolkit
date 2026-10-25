"""Call-log workflow operations (v1 ``/batch-*`` endpoints, made stateless).

v1 kept a per-token JSON on the server between analyse → merge → dedup →
filter → distribute. Here every step is an independent job: the input is the
PDFs or the workbook the previous step produced, plus parameters.

* ``calllog_analyze``    — v1 ``/batch-analyze``
* ``calllog_to_excel``   — v1 ``/batch-convert`` (+ ``/batch-deduplicate``)
* ``excel_filter``       — v1 ``/batch-filter`` + ``/batch-deduplicate``
* ``excel_distribute``   — v1 ``/batch-distribute`` + its ZIP download
"""

from __future__ import annotations

import json
import re
import tempfile
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, StringConstraints

from ...core.errors import UserError
from ...ops.base import Context, Field, Operation, Params, register
from .distribution import Mode, WeightMode, check_weights, distribute, team_file_names
from .parsing import CALL_LOG_COLUMNS, KIND_LABELS, PHONE_COLUMN, Parsed, parse_pdf
from .tabular import (
    MAX_ROWS,
    FilterRule,
    SummaryBlock,
    Table,
    apply_rules,
    as_text,
    deduplicate,
    read_xlsx,
    safe_value,
    tr_fold,
    write_workbook,
)

MAX_PDFS = 500
MAX_TEAMS = 200
SAMPLE_ROWS = 3
SUMMARY_FILE = "_dagitim_ozeti.xlsx"


# -- parameter parsing (the generic form sends lists as plain text) ------------
def _split_list(value: Any) -> Any:
    """``"a, b"`` / one-per-line / JSON array → list of non-empty strings."""
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                value = json.loads(text)
            except json.JSONDecodeError as e:
                raise ValueError("invalid JSON list") from e
        else:
            sep = r"[\r\n]+" if "\n" in text else r"[;,]"
            value = re.split(sep, text)
    if isinstance(value, list):
        return [v.strip() if isinstance(v, str) else v for v in value if not (isinstance(v, str) and not v.strip())]
    return value


def _split_numbers(value: Any) -> Any:
    """``"60, 40"`` / ``"33,5; 66,5"`` (Turkish decimals with ``;``) → floats."""
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            return _split_list(text)
        if ";" in text:
            return [p.strip().replace(",", ".") for p in text.split(";") if p.strip()]
        return [p for p in re.split(r"[,\s]+", text) if p]
    return value


def _json_list(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            value = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError("rules must be a JSON list") from e
    if isinstance(value, dict):
        return [value]
    return value


ColumnName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ColumnList = Annotated[list[ColumnName], BeforeValidator(_split_list)]
TeamName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


# -- grouping ------------------------------------------------------------------
@dataclass
class Group:
    id: str
    kind: str
    columns: list[str]
    members: list[Parsed] = field(default_factory=list)

    @property
    def mergeable(self) -> bool:
        return self.kind in ("call_log", "table")

    @property
    def rows(self) -> int:
        return sum(len(m.rows) for m in self.members)

    def label(self) -> dict[str, str]:
        tr, en = KIND_LABELS[self.kind]
        if self.kind == "table":
            head = ", ".join(self.columns[:4]) + (" …" if len(self.columns) > 4 else "")
            return {"tr": f"{tr}: {head}", "en": f"{en}: {head}"}
        return {"tr": tr, "en": en}


def group_files(parsed: list[Parsed]) -> list[Group]:
    """Same-format files share a group (v1 ``/batch-analyze`` signatures);
    ids follow first appearance so analyse and convert agree."""
    groups: dict[str, Group] = {}
    for p in parsed:
        kind = p.kind if p.mergeable or p.kind not in ("call_log", "table") else "unknown"
        sig = p.signature if p.mergeable else kind
        g = groups.get(sig)
        if g is None:
            g = groups[sig] = Group(f"g{len(groups) + 1}", kind, p.columns if p.mergeable else [])
        g.members.append(p)
    return list(groups.values())


def _parse_all(ctx: Context, *, keep_rows: bool) -> list[Parsed]:
    if len(ctx.inputs) > MAX_PDFS:
        raise UserError(f"En fazla {MAX_PDFS} PDF işlenebilir.", f"At most {MAX_PDFS} PDFs can be processed.")
    parsed: list[Parsed] = []
    total = 0
    for k, inp in enumerate(ctx.inputs):
        p = parse_pdf(inp.path, inp.name, inp.password, MAX_ROWS)
        if p.kind == "call_log" and not p.rows:
            p.message_tr, p.message_en = "Çağrı kaydı bulunamadı.", "No call records found."
        total += len(p.rows)
        if total > MAX_ROWS:
            raise UserError(
                f"Toplam satır sayısı {MAX_ROWS:,} sınırını aşıyor.", f"The total row count exceeds {MAX_ROWS:,}."
            )
        if not keep_rows:
            p.rows, p.row_count = p.rows[:SAMPLE_ROWS], len(p.rows)
        parsed.append(p)
        ctx.progress((k + 1) / len(ctx.inputs) * (0.6 if keep_rows else 1.0), inp.name)
    return parsed


def _row_count(p: Parsed) -> int:
    return p.row_count if p.row_count is not None else len(p.rows)


# -- 1. analyse ----------------------------------------------------------------
@register
class CallLogAnalyze(Operation):
    name = "calllog_analyze"
    category = "workflow"
    title_tr, title_en = "Çağrı Kaydı Analizi", "Call Log Analysis"
    description_tr = (
        "PDF'lerin biçimini algılar (çağrı kaydı, tablo, taranmış) ve aynı yapıdakileri gruplar; "
        "satır sayılarını ve sütunları gösterir."
    )
    description_en = (
        "Detect each PDF's format (call log, table, scanned), group same-format files and show row counts and columns."
    )
    max_inputs = MAX_PDFS
    returns_data = True

    def run(self, ctx: Context, params: object) -> None:
        parsed = _parse_all(ctx, keep_rows=False)
        groups = group_files(parsed)
        group_of = {id(m): g.id for g in groups for m in g.members}
        files = []
        for i, p in enumerate(parsed):
            tr, en = KIND_LABELS[p.kind]
            files.append(
                {
                    "index": i,
                    "name": p.name,
                    "kind": p.kind,
                    "label": {"tr": tr, "en": en},
                    "group": group_of[id(p)],
                    "pages": p.pages,
                    "rows": _row_count(p),
                    "columns": p.columns,
                    "sample_rows": [[safe_value(v) for v in r] for r in p.rows[:SAMPLE_ROWS]],
                    "mergeable": p.mergeable,
                    "message": {"tr": p.message_tr, "en": p.message_en} if p.message_tr else None,
                }
            )
        ctx.data = {
            "files": files,
            "groups": [
                {
                    "id": g.id,
                    "kind": g.kind,
                    "label": g.label(),
                    "columns": g.columns,
                    "files": [m.name for m in g.members],
                    "file_indices": [parsed.index(m) for m in g.members],
                    "rows": sum(_row_count(m) for m in g.members),
                    "mergeable": g.mergeable,
                    "dedup_default": [PHONE_COLUMN] if g.kind == "call_log" else [],
                }
                for g in groups
            ],
            "file_count": len(parsed),
            "mergeable_files": sum(1 for p in parsed if p.mergeable),
            "total_rows": sum(_row_count(p) for p in parsed if p.mergeable),
            "call_log_columns": CALL_LOG_COLUMNS,
        }


# -- 2. merge to Excel ---------------------------------------------------------
class ToExcelParams(Params):
    dedup: bool = Field(
        False,
        tr="Mükerrer kayıtları sil",
        en="Remove duplicates",
        help_tr="Çağrı kayıtlarında aynı telefon numarası (0532…, +90 532…, 532… eşleşir) bir kez kalır.",
        help_en="For call logs, each phone number is kept once (0532…, +90 532…, 532… all match).",
    )
    dedup_columns: ColumnList = Field(
        default_factory=list,
        tr="Mükerrer sütunları",
        en="Duplicate columns",
        help_tr="Tablo PDF'leri için virgülle ayrılmış sütun adları. Çağrı kayıtlarında boş = Telefon.",
        help_en="Comma-separated column names for table PDFs. For call logs empty = Telefon (phone).",
        max_length=50,
        ui={"show_if": {"dedup": True}},
    )


def _pick_dedup_columns(group: Group, wanted: list[str]) -> tuple[list[str], dict[str, str] | None]:
    folded = {tr_fold(c): c for c in group.columns}
    present = [folded[tr_fold(c)] for c in wanted if tr_fold(c) in folded]
    missing = [c for c in wanted if tr_fold(c) not in folded]
    label = group.label()
    if group.kind == "call_log":
        if wanted and not missing:
            return present, None
        warn = (
            {
                "tr": f"{label['tr']}: {', '.join(missing)} sütunu yok; mükerrer kontrolü Telefon ile yapıldı.",
                "en": f"{label['en']}: no column {', '.join(missing)}; duplicates were checked by phone.",
            }
            if missing
            else None
        )
        return [PHONE_COLUMN], warn
    if not wanted:
        return [], {
            "tr": f"{label['tr']}: mükerrer sütunu seçilmediği için mükerrer silinmedi.",
            "en": f"{label['en']}: no duplicate columns given, so no duplicates were removed.",
        }
    if missing:
        return [], {
            "tr": f"{label['tr']}: {', '.join(missing)} sütunu yok; mükerrer silinmedi.",
            "en": f"{label['en']}: no column {', '.join(missing)}; no duplicates were removed.",
        }
    return present, None


@register
class CallLogToExcel(Operation):
    name = "calllog_to_excel"
    category = "workflow"
    title_tr, title_en = "Çağrı Kaydı → Excel (Birleştir)", "Call Logs → Excel (Merge)"
    description_tr = (
        "Çok sayıda çağrı kaydı / tablo PDF'ini biçimlerine göre gruplar ve her grubu tek Excel'de "
        "birleştirir; isteğe bağlı mükerrer temizliği ve özet sayfası."
    )
    description_en = (
        "Group many call-log / table PDFs by format and merge each group into one Excel workbook, "
        "with optional duplicate removal and a summary sheet."
    )
    max_inputs = MAX_PDFS
    Params = ToExcelParams

    def run(self, ctx: Context, params: ToExcelParams) -> None:
        parsed = _parse_all(ctx, keep_rows=True)
        groups = group_files(parsed)
        mergeable = [g for g in groups if g.mergeable]
        skipped = [p for p in parsed if not p.mergeable]
        if not mergeable:
            raise UserError(
                "Birleştirilecek veri bulunamadı (çağrı kaydı veya tablo içeren PDF yok).",
                "Nothing to merge (no PDF contains a call log or a table).",
            )
        skipped_info = [
            {"name": p.name, "kind": p.kind, "reason": {"tr": p.message_tr, "en": p.message_en}} for p in skipped
        ]
        warnings: list[dict[str, str]] = []
        report: list[dict[str, Any]] = []
        any_dedup = False
        for k, g in enumerate(mergeable):
            table = Table(
                ["Sıra", "Kaynak PDF", *g.columns],
                [[0, m.name, *row] for m in g.members for row in m.rows],
                "Birleşik Kayıtlar",
            )
            read = len(table.rows)
            cols: list[str] = []
            removed_by_file: Counter[str] = Counter()
            if params.dedup:
                cols, warn = _pick_dedup_columns(g, params.dedup_columns)
                if warn:
                    warnings.append(warn)
                if cols:
                    any_dedup = True
                    original = table.rows
                    removed_by_file.update(str(original[i][1]) for i in deduplicate(table, cols))
            table.renumber()
            removed = read - len(table.rows)
            stem = "cagri_kayitlari" if g.kind == "call_log" else f"tablo_{g.id}"
            out_name = f"{stem}_{len(table.rows)}_kayit.xlsx"
            label = g.label()
            summary: list[SummaryBlock] = [
                (
                    "Özet / Summary",
                    ["Alan", "Değer"],
                    [
                        ["Grup", label["tr"]],
                        ["Kaynak PDF sayısı", len(g.members)],
                        ["Okunan satır", read],
                        ["Silinen mükerrer", removed],
                        ["Yazılan satır", len(table.rows)],
                        ["Mükerrer sütunları", ", ".join(cols) if cols else "—"],
                    ],
                ),
                (
                    "Kaynak dosyalar / Source files",
                    ["Kaynak PDF", "Sayfa", "Okunan satır", "Silinen mükerrer"],
                    [[m.name, m.pages, len(m.rows), removed_by_file.get(m.name, 0)] for m in g.members],
                ),
            ]
            if skipped:
                summary.append(
                    (
                        "Dahil edilmeyen dosyalar / Skipped files",
                        ["Dosya", "Tür", "Neden"],
                        [[p.name, KIND_LABELS[p.kind][0], p.message_tr] for p in skipped],
                    )
                )
            if warnings:
                summary.append(("Uyarılar / Warnings", [], [[w["tr"]] for w in warnings]))
            write_workbook(ctx.output(out_name), table, summary)
            report.append(
                {
                    "id": g.id,
                    "kind": g.kind,
                    "label": label,
                    "files": [m.name for m in g.members],
                    "columns": table.columns,
                    "rows_read": read,
                    "duplicates_removed": removed,
                    "rows_written": len(table.rows),
                    "dedup_columns": cols,
                    "output": ctx.outputs[-1].name,
                }
            )
            ctx.progress(0.6 + 0.4 * (k + 1) / len(mergeable), out_name)
        if params.dedup and not any_dedup and not any(g.kind == "call_log" for g in mergeable):
            raise UserError(
                "Mükerrer kontrolü için tablolarda bulunan sütun adlarını girin.",
                "Enter column names that exist in the tables to remove duplicates.",
            )
        ctx.data = {
            "groups": report,
            "skipped": skipped_info,
            "warnings": warnings,
            "total_rows_read": sum(r["rows_read"] for r in report),
            "total_duplicates_removed": sum(r["duplicates_removed"] for r in report),
            "total_rows_written": sum(r["rows_written"] for r in report),
        }


# -- 3. filter -----------------------------------------------------------------
class FilterParams(Params):
    rules: Annotated[list[FilterRule], BeforeValidator(_json_list)] = Field(
        default_factory=list,
        tr="Filtre kuralları (JSON)",
        en="Filter rules (JSON)",
        help_tr='Örnek: [{"column": "Durum", "op": "in", "value": ["ended", "completed"]}]. '
        "op: equals, not_equals, contains, not_contains, in, not_in, empty, not_empty.",
        help_en='Example: [{"column": "Durum", "op": "in", "value": ["ended", "completed"]}]. '
        "op: equals, not_equals, contains, not_contains, in, not_in, empty, not_empty.",
        max_length=100,
    )
    match: Literal["all", "any"] = Field(
        "all",
        tr="Kurallar",
        en="Rules",
        ui={
            "options": {
                "all": {"tr": "Tümü sağlanmalı (VE)", "en": "All must match (AND)"},
                "any": {"tr": "Biri yeterli (VEYA)", "en": "Any may match (OR)"},
            }
        },
    )
    case_sensitive: bool = Field(False, tr="Büyük/küçük harf duyarlı", en="Case-sensitive")
    dedup_columns: ColumnList = Field(
        default_factory=list,
        tr="Mükerrer sütunları",
        en="Duplicate columns",
        help_tr="Boş = mükerrer kontrolü yok. Telefon sütunları Türk numara biçimine göre eşleştirilir.",
        help_en="Empty = no duplicate check. Phone columns are matched in Turkish number format.",
        max_length=50,
    )
    sheet: str = Field("", tr="Sayfa adı (boş = ilk)", en="Sheet name (empty = first)", max_length=31)


@register
class ExcelFilter(Operation):
    name = "excel_filter"
    category = "workflow"
    title_tr, title_en = "Excel Filtrele / Mükerrer Sil", "Filter Excel / Remove Duplicates"
    description_tr = "Excel satırlarını sütun kurallarına göre süzer ve/veya seçilen sütunlarda mükerrerleri siler."
    description_en = "Filter Excel rows by column rules and/or remove duplicates on chosen columns."
    accepts = frozenset({"xlsx"})
    Params = FilterParams

    def run(self, ctx: Context, params: FilterParams) -> None:
        if not params.rules and not params.dedup_columns:
            raise UserError(
                "En az bir filtre kuralı veya mükerrer sütunu girin.",
                "Enter at least one filter rule or duplicate column.",
            )
        inp = ctx.inputs[0]
        table = read_xlsx(inp.path, params.sheet)
        ctx.progress(0.4, "filter")
        before = len(table.rows)
        filtered = apply_rules(table, params.rules, match=params.match, case_sensitive=params.case_sensitive)
        duplicates = len(deduplicate(table, params.dedup_columns)) if params.dedup_columns else 0
        table.renumber()
        rule_rows: list[list[Any]] = [
            [r.column, r.op, ", ".join(as_text(v) for v in r.value) if isinstance(r.value, list) else as_text(r.value)]
            for r in params.rules
        ]
        summary: list[SummaryBlock] = [
            (
                "Özet / Summary",
                ["Alan", "Değer"],
                [
                    ["Kaynak dosya", inp.name],
                    ["Başlangıç satırı", before],
                    ["Filtreyle elenen", filtered],
                    ["Silinen mükerrer", duplicates],
                    ["Kalan satır", len(table.rows)],
                    ["Mükerrer sütunları", ", ".join(params.dedup_columns) or "—"],
                    ["Kural birleşimi", "VE" if params.match == "all" else "VEYA"],
                ],
            )
        ]
        if rule_rows:
            summary.append(("Kurallar / Rules", ["Sütun", "İşlem", "Değer"], rule_rows))
        ctx.progress(0.7, "write")
        write_workbook(ctx.output(f"{inp.stem}_filtreli.xlsx"), table, summary)
        ctx.data = {
            "rows_before": before,
            "removed_by_rules": filtered,
            "duplicates_removed": duplicates,
            "rows_after": len(table.rows),
            "columns": table.columns,
        }


# -- 4. distribute -------------------------------------------------------------
class DistributeParams(Params):
    teams: Annotated[list[TeamName], BeforeValidator(_split_list)] = Field(
        ...,
        tr="Ekipler",
        en="Teams",
        help_tr="Virgülle ayrılmış veya her satıra bir ekip adı.",
        help_en="Comma-separated, or one team name per line.",
        min_length=1,
        max_length=MAX_TEAMS,
    )
    mode: Mode = Field(
        "sequential",
        tr="Dağıtım",
        en="Distribution",
        ui={
            "options": {
                "sequential": {"tr": "Sıralı (bloklar halinde eşit)", "en": "Sequential (equal blocks)"},
                "round_robin": {"tr": "Döngüsel (1→E1, 2→E2, …)", "en": "Round-robin (1→T1, 2→T2, …)"},
                "ratio": {"tr": "Özel oran", "en": "Custom ratio"},
            }
        },
    )
    weight_mode: WeightMode = Field(
        "percent",
        tr="Oran türü",
        en="Weight type",
        ui={
            "show_if": {"mode": "ratio"},
            "options": {
                "percent": {"tr": "Doğrudan yüzde (toplam %100)", "en": "Direct percent (total 100%)"},
                "factor": {"tr": "Puan / katsayı (orantılı)", "en": "Score / factor (proportional)"},
            },
        },
    )
    weights: Annotated[list[float], BeforeValidator(_split_numbers)] = Field(
        default_factory=list,
        tr="Oranlar",
        en="Weights",
        help_tr="Ekip sırasıyla, örn. 50, 30, 20. Ondalık için noktalı virgül kullanın: 33,5; 66,5",
        help_en="In team order, e.g. 50, 30, 20.",
        max_length=MAX_TEAMS,
        ui={"show_if": {"mode": "ratio"}},
    )
    sheet: str = Field("", tr="Sayfa adı (boş = ilk)", en="Sheet name (empty = first)", max_length=31)


_MODE_TR = {"sequential": "Sıralı", "round_robin": "Döngüsel", "ratio": "Özel oran"}


@register
class ExcelDistribute(Operation):
    name = "excel_distribute"
    category = "workflow"
    title_tr, title_en = "Ekiplere Dağıt", "Distribute to Teams"
    description_tr = (
        "Excel satırlarını ekiplere sıralı, döngüsel veya özel oranla dağıtır; her ekip için ayrı Excel içeren ZIP."
    )
    description_en = (
        "Distribute Excel rows to teams sequentially, round-robin or by custom ratio; a ZIP with one Excel per team."
    )
    accepts = frozenset({"xlsx"})
    Params = DistributeParams

    def run(self, ctx: Context, params: DistributeParams) -> None:
        teams = params.teams
        dupes = [t for t, n in Counter(t.casefold() for t in teams).items() if n > 1]
        if dupes:
            raise UserError(
                f"Ekip adları benzersiz olmalı: {', '.join(dupes)}", f"Team names must be unique: {', '.join(dupes)}"
            )
        if params.mode == "ratio":
            check_weights(params.weights, len(teams), params.weight_mode)
        inp = ctx.inputs[0]
        table = read_xlsx(inp.path, params.sheet)
        if not table.rows:
            raise UserError("Dağıtılacak satır yok.", "There are no rows to distribute.")
        ctx.progress(0.2, "distribute")
        parts = distribute(table.rows, len(teams), params.mode, params.weights)
        files = team_file_names(teams, reserved=[SUMMARY_FILE])
        total = len(table.rows)
        weight_sum = sum(params.weights) if params.mode == "ratio" else 0.0
        mode_tr = _MODE_TR[params.mode]
        out = ctx.output(f"dagitim_{total}_kayit.zip")
        with (
            tempfile.TemporaryDirectory(dir=ctx.output_dir) as tmp,
            zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf,
        ):
            for k, (team, fname, rows) in enumerate(zip(teams, files, parts, strict=True)):
                if not rows:
                    continue
                path = Path(tmp) / f"{k}.xlsx"
                write_workbook(
                    path,
                    Table(table.columns, rows, table.title),
                    [
                        (
                            "Özet / Summary",
                            ["Alan", "Değer"],
                            [["Ekip", team], ["Dağıtım", mode_tr], ["Satır", len(rows)], ["Kaynak dosya", inp.name]],
                        )
                    ],
                )
                zf.write(path, fname)
                path.unlink()
                ctx.progress(0.2 + 0.7 * (k + 1) / len(teams), team)
            summary_rows: list[list[Any]] = []
            for j, (team, fname, rows) in enumerate(zip(teams, files, parts, strict=True)):
                share = round(100 * len(rows) / total, 2)
                weight: Any = params.weights[j] if params.mode == "ratio" else "—"
                summary_rows.append([team, fname if rows else "—", len(rows), share, weight])
            path = Path(tmp) / "summary.xlsx"
            write_workbook(
                path,
                Table(["Ekip", "Dosya", "Satır", "Pay (%)", "Oran"], summary_rows, "Dağıtım"),
                [
                    (
                        "Özet / Summary",
                        ["Alan", "Değer"],
                        [
                            ["Kaynak dosya", inp.name],
                            ["Dağıtım", mode_tr],
                            ["Oran türü", params.weight_mode if params.mode == "ratio" else "—"],
                            ["Toplam satır", total],
                            ["Ekip sayısı", len(teams)],
                        ],
                    )
                ],
            )
            zf.write(path, SUMMARY_FILE)
        ctx.data = {
            "mode": params.mode,
            "total": total,
            "counts": {team: len(rows) for team, rows in zip(teams, parts, strict=True)},
            "teams": [
                {
                    "name": team,
                    "file": fname if rows else None,
                    "count": len(rows),
                    "share": round(100 * len(rows) / total, 2),
                    "weight": params.weights[j] / weight_sum * 100 if weight_sum else None,
                }
                for j, (team, fname, rows) in enumerate(zip(teams, files, parts, strict=True))
            ],
            "summary_file": SUMMARY_FILE,
        }
