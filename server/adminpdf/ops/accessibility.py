"""Accessibility (ISO 14289-1 / PDF/UA) checks and the fixes that can be made
automatically.

A full PDF/UA conformance claim needs a properly tagged structure tree and a
human review (reading order, alt text quality); tagging untagged content is
not something a tool can do faithfully. The check therefore reports what the
standard requires item by item, and ``accessibility_fix`` repairs the
document-level properties that can be set safely.
"""

from __future__ import annotations

import re
from typing import Any

import pymupdf

from ..core.pdf import open_pdf, save_pdf
from .base import Context, Field, Operation, Params, register

MAX_STRUCT_NODES = 200_000


def _catalog_get(doc: pymupdf.Document, key: str) -> tuple[str, str]:
    kind, value = doc.xref_get_key(doc.pdf_catalog(), key)
    return str(kind), str(value)


def _struct_stats(doc: pymupdf.Document) -> dict[str, int]:
    """Walk the structure tree: count figures and figures lacking /Alt."""
    kind, value = _catalog_get(doc, "StructTreeRoot")
    stats = {"nodes": 0, "figures": 0, "figures_without_alt": 0, "headings": 0, "tables": 0}
    if kind != "xref":
        return stats
    stack = [int(value.split()[0])]
    seen: set[int] = set()
    while stack and stats["nodes"] < MAX_STRUCT_NODES:
        xref = stack.pop()
        if xref in seen:
            continue
        seen.add(xref)
        stats["nodes"] += 1
        s_kind, s_val = doc.xref_get_key(xref, "S")
        tag = s_val.lstrip("/") if s_kind == "name" else ""
        if tag == "Figure":
            stats["figures"] += 1
            if doc.xref_get_key(xref, "Alt")[0] == "null" and doc.xref_get_key(xref, "ActualText")[0] == "null":
                stats["figures_without_alt"] += 1
        elif re.fullmatch(r"H\d?", tag):
            stats["headings"] += 1
        elif tag == "Table":
            stats["tables"] += 1
        k_kind, k_val = doc.xref_get_key(xref, "K")
        if k_kind in ("xref", "array"):
            stack.extend(int(x) for x in re.findall(r"(\d+) 0 R", k_val))
    return stats


def check(doc: pymupdf.Document) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    def item(rule: str, ok: bool, tr: str, en: str, fixable: bool = False) -> None:
        items.append({"rule": rule, "ok": ok, "message": {"tr": tr, "en": en}, "auto_fix": fixable and not ok})

    tagged = _catalog_get(doc, "StructTreeRoot")[0] == "xref"
    mark = _catalog_get(doc, "MarkInfo")
    marked = "true" in (mark[1] or "") if mark[0] != "null" else False
    lang = _catalog_get(doc, "Lang")
    title = (doc.metadata or {}).get("title", "")
    vp = _catalog_get(doc, "ViewerPreferences")
    display_title = "DisplayDocTitle" in vp[1] and "true" in vp[1] if vp[0] != "null" else False
    item("7.1-tagged", tagged, "Belge etiketli (yapı ağacı var).", "Document is tagged (structure tree present).")
    item("7.1-marked", marked, "MarkInfo /Marked true.", "MarkInfo /Marked is true.", fixable=tagged)
    item(
        "7.2-lang",
        lang[0] == "string" and bool(lang[1].strip("() ")),
        "Belge dili (/Lang) tanımlı.",
        "Document language (/Lang) is set.",
        True,
    )
    item("7.1-title", bool(title.strip()), "Belge başlığı (Title) dolu.", "Document title is set.", True)
    item(
        "7.1-display-title",
        display_title,
        "Pencerede dosya adı yerine başlık gösterilir.",
        "Viewer shows the title, not the file name.",
        True,
    )

    unembedded: set[str] = set()
    scanned_pages: list[int] = []
    annots_without_tabs: list[int] = []
    widgets_without_tooltip = 0
    for page in doc:
        for f in page.get_fonts(full=True):
            if f[1] in ("n/a", "") or not f[1]:
                continue
            if f[1] != "Type3" and not f[0] and not doc.extract_font(f[0])[3]:
                unembedded.add(str(f[3]))
        try:
            if not page.get_text().strip() and page.get_images():
                scanned_pages.append(page.number + 1)
        except Exception:
            pass
        if page.first_annot is not None and doc.xref_get_key(page.xref, "Tabs") != ("name", "/S"):
            annots_without_tabs.append(page.number + 1)
        for w in page.widgets():
            if not (w.field_label or "").strip():
                widgets_without_tooltip += 1
    item("7.21-fonts", not unembedded, "Tüm fontlar gömülü.", "All fonts are embedded.")
    item(
        "7.1-text",
        not scanned_pages,
        "Tüm sayfalarda gerçek metin var."
        if not scanned_pages
        else f"Metinsiz (taranmış) sayfalar: {scanned_pages[:20]} — OCR uygulayın.",
        "Every page has real text." if not scanned_pages else f"Image-only pages: {scanned_pages[:20]} — run OCR.",
    )
    item(
        "7.18.3-tabs",
        not annots_without_tabs,
        "Açıklamalı sayfalarda sekme sırası yapıya göre (/Tabs /S).",
        "Pages with annotations use structure tab order (/Tabs /S).",
        True,
    )
    item(
        "7.18.4-field-tooltips",
        widgets_without_tooltip == 0,
        "Form alanlarının açıklaması (TU) var."
        if not widgets_without_tooltip
        else f"{widgets_without_tooltip} form alanında açıklama (TU) yok.",
        "Form fields have descriptions (TU)."
        if not widgets_without_tooltip
        else f"{widgets_without_tooltip} form fields lack a description (TU).",
    )
    stats = _struct_stats(doc)
    if tagged:
        item(
            "7.3-figure-alt",
            stats["figures_without_alt"] == 0,
            "Tüm şekillerin alternatif metni var."
            if not stats["figures_without_alt"]
            else f"{stats['figures_without_alt']} şeklin alternatif metni yok.",
            "All figures have alternative text."
            if not stats["figures_without_alt"]
            else f"{stats['figures_without_alt']} figures lack alternative text.",
        )
    perms = doc.permissions
    item(
        "7.16-security",
        bool(perms & pymupdf.PDF_PERM_ACCESSIBILITY) or not doc.is_encrypted,
        "Şifreleme ekran okuyuculara izin veriyor.",
        "Encryption allows assistive technology.",
    )
    passed = sum(1 for i in items if i["ok"])
    return {
        "standard": "ISO 14289-1 (PDF/UA-1)",
        "passed": passed,
        "total": len(items),
        "conformant_candidate": passed == len(items),
        "structure": stats,
        "checks": items,
        "note": {
            "tr": "Otomatik denetim; tam PDF/UA uygunluğu için okuma sırası ve alternatif metinlerin "
            "insan tarafından gözden geçirilmesi gerekir.",
            "en": "Automated checks; full PDF/UA conformance also needs a human review of reading order and alt text.",
        },
    }


@register
class AccessibilityCheck(Operation):
    name = "accessibility_check"
    category = "inspect"
    title_tr, title_en = "Erişilebilirlik Denetimi (PDF/UA)", "Accessibility Check (PDF/UA)"
    description_tr = (
        "ISO 14289-1 (PDF/UA) gereksinimlerini madde madde denetler: etiket, dil, başlık, font, "
        "alternatif metin, sekme sırası…"
    )
    description_en = (
        "Checks ISO 14289-1 (PDF/UA) requirements item by item: tags, language, title, fonts, alt text, tab order…"
    )
    returns_data = True

    def run(self, ctx: Context, params: object) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            ctx.data = check(doc)


class FixParams(Params):
    language: str = Field(
        "tr-TR",
        tr="Belge dili (BCP 47)",
        en="Document language (BCP 47)",
        help_tr="Örn. tr-TR, en-US",
        help_en="e.g. tr-TR, en-US",
        pattern=r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$",
        max_length=35,
    )
    title: str = Field("", tr="Başlık (boşsa dosya adından)", en="Title (empty = from file name)", max_length=300)


@register
class AccessibilityFix(Operation):
    name = "accessibility_fix"
    category = "inspect"
    title_tr, title_en = "Erişilebilirlik Özelliklerini Düzelt", "Fix Accessibility Properties"
    description_tr = (
        "Belge dili, başlık, başlığı gösterme, MarkInfo ve sekme sırası gibi otomatik düzeltilebilen "
        "PDF/UA maddelerini düzeltir."
    )
    description_en = (
        "Sets language, title, display-title, MarkInfo and tab order — "
        "the PDF/UA items that can be fixed automatically."
    )
    Params = FixParams

    def run(self, ctx: Context, params: FixParams) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            cat = doc.pdf_catalog()
            doc.xref_set_key(cat, "Lang", pymupdf.get_pdf_str(params.language))
            meta = dict(doc.metadata or {})
            if params.title.strip() or not (meta.get("title") or "").strip():
                meta["title"] = params.title.strip() or inp.stem
                doc.set_metadata(
                    {
                        k: v
                        for k, v in meta.items()
                        if k
                        in ("title", "author", "subject", "keywords", "creator", "producer", "creationDate", "modDate")
                    }
                )
            vp_kind, _ = doc.xref_get_key(cat, "ViewerPreferences")
            if vp_kind == "xref":
                doc.xref_set_key(
                    int(doc.xref_get_key(cat, "ViewerPreferences")[1].split()[0]), "DisplayDocTitle", "true"
                )
            else:
                doc.xref_set_key(cat, "ViewerPreferences", "<</DisplayDocTitle true>>")
            if doc.xref_get_key(cat, "StructTreeRoot")[0] == "xref":
                doc.xref_set_key(cat, "MarkInfo", "<</Marked true>>")
            for page in doc:
                if page.first_annot is not None:
                    doc.xref_set_key(page.xref, "Tabs", "/S")
            after = check(doc)
            save_pdf(doc, ctx.output(f"{inp.stem}_erisilebilir.pdf"))
        ctx.data = {"after": {"passed": after["passed"], "total": after["total"]}, "checks": after["checks"]}
