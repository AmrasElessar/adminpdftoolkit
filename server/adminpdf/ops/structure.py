"""Document structure: metadata, bookmarks (outline), embedded files."""

from __future__ import annotations

import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from typing import Any

import pymupdf

from ..core.errors import UserError
from ..core.files import safe_filename
from ..core.pdf import open_pdf, save_pdf
from .base import Context, Field, FileParam, Operation, Params, register

MAX_OUTLINE_ITEMS = 10_000
MAX_TITLE = 300
MAX_LEVEL = 64
MAX_ATTACHMENT_BYTES = 200 * 1024 * 1024
MAX_ATTACHMENTS = 10_000

_META_KEYS = ("title", "author", "subject", "keywords", "creator", "producer")
# Every Info key PyMuPDF writes; ``set_metadata`` keeps keys it is not given.
_ALL_META_KEYS = (*_META_KEYS, "creationDate", "modDate", "trapped")


def _empty_metadata() -> dict[str, str]:
    return dict.fromkeys(_ALL_META_KEYS, "")


# -- metadata ----------------------------------------------------------------------


class SetMetadataParams(Params):
    title: str = Field("", tr="Başlık", en="Title", max_length=1000)
    author: str = Field("", tr="Yazar", en="Author", max_length=1000)
    subject: str = Field("", tr="Konu", en="Subject", max_length=1000)
    keywords: str = Field("", tr="Anahtar sözcükler", en="Keywords", max_length=2000)
    creator: str = Field("", tr="Oluşturan uygulama", en="Creator", max_length=1000)
    producer: str = Field("", tr="Üretici", en="Producer", max_length=1000)
    clear_others: bool = Field(
        False,
        tr="Diğer alanları temizle",
        en="Clear the other fields",
        help_tr="Boş bırakılan alanlar ve XMP meta verisi silinir.",
        help_en="Fields left empty and the XMP metadata are removed.",
    )


@register
class SetMetadata(Operation):
    name = "set_metadata"
    category = "document"
    title_tr, title_en = "Meta Veri Düzenle", "Edit Metadata"
    description_tr = "Başlık, yazar, konu ve anahtar sözcükleri değiştirir."
    description_en = "Change the title, author, subject and keywords."
    Params = SetMetadataParams

    def run(self, ctx: Context, params: SetMetadataParams) -> None:
        given = {k: getattr(params, k).strip() for k in _META_KEYS if getattr(params, k).strip()}
        if not given and not params.clear_others:
            raise UserError("En az bir alan doldurun.", "Fill in at least one field.")
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            current = {k: v for k, v in (doc.metadata or {}).items() if k not in ("format", "encryption") and v}
            meta = _empty_metadata() | (given if params.clear_others else current | given)
            doc.set_metadata(meta)
            if params.clear_others:
                doc.del_xml_metadata()
            save_pdf(doc, ctx.output(f"{inp.stem}_meta.pdf"))


def strip_document_metadata(doc: pymupdf.Document) -> None:
    """Info dict, XMP (document and page level), thumbnails, PieceInfo."""
    doc.set_metadata(_empty_metadata())
    doc.del_xml_metadata()
    cat = doc.pdf_catalog()
    if cat:
        doc.xref_set_key(cat, "PieceInfo", "null")
    for page in doc:
        for key in ("Thumb", "PieceInfo", "Metadata"):
            if doc.xref_get_key(page.xref, key)[0] != "null":
                doc.xref_set_key(page.xref, key, "null")


@register
class RemoveMetadata(Operation):
    name = "remove_metadata"
    category = "document"
    title_tr, title_en = "Meta Veriyi Temizle", "Remove Metadata"
    description_tr = "Yazar, uygulama, tarih gibi gizli bilgileri, XMP verisini ve küçük resimleri siler."
    description_en = "Remove hidden details such as author, application and dates, XMP data and thumbnails."

    def run(self, ctx: Context, params: object) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            strip_document_metadata(doc)
            save_pdf(doc, ctx.output(f"{inp.stem}_temiz.pdf"))


# -- outline ---------------------------------------------------------------------------


@register
class GetOutline(Operation):
    name = "get_outline"
    category = "document"
    title_tr, title_en = "Yer İmlerini Göster", "Show Bookmarks"
    description_tr = "Belgenin yer imlerini (içindekiler) listeler."
    description_en = "List the document's bookmarks (outline)."
    returns_data = True

    def run(self, ctx: Context, params: object) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            toc = doc.get_toc(simple=True)
            items = [
                {"level": int(level), "title": str(title), "page": int(page) if int(page) >= 1 else None}
                for level, title, page, *_ in toc[:MAX_OUTLINE_ITEMS]
            ]
            ctx.data = {"items": items, "total": len(toc), "pages": doc.page_count}


class OutlineItem(Params):
    level: int = Field(..., tr="Düzey", en="Level", ge=1, le=MAX_LEVEL)
    title: str = Field(..., tr="Başlık", en="Title", min_length=1, max_length=MAX_TITLE)
    page: int = Field(..., tr="Sayfa", en="Page", ge=1, le=1_000_000)


class SetOutlineParams(Params):
    items: list[OutlineItem] = Field(
        default_factory=list,
        tr="Yer imleri",
        en="Bookmarks",
        max_length=MAX_OUTLINE_ITEMS,
        ui={"widget": "json"},
    )


def validate_outline(items: list[tuple[int, str, int]], page_count: int) -> None:
    prev = 0
    for n, (level, _title, page) in enumerate(items, 1):
        if level > prev + 1:
            raise UserError(
                f"Yer imi {n}: düzey {prev}'den {level}'e atlayamaz.",
                f"Bookmark {n}: level cannot jump from {prev} to {level}.",
            )
        if not 1 <= page <= page_count:
            raise UserError(
                f"Yer imi {n}: sayfa {page} aralık dışında (1–{page_count}).",
                f"Bookmark {n}: page {page} is out of range (1–{page_count}).",
            )
        prev = level


@register
class SetOutline(Operation):
    name = "set_outline"
    category = "document"
    title_tr, title_en = "Yer İmlerini Düzenle", "Edit Bookmarks"
    description_tr = "Belgenin yer imlerini verilen listeyle değiştirir."
    description_en = "Replace the document's bookmarks with the given list."
    hidden = True
    Params = SetOutlineParams

    def run(self, ctx: Context, params: SetOutlineParams) -> None:
        items = [(i.level, i.title.strip() or "—", i.page) for i in params.items]
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            validate_outline(items, doc.page_count)
            doc.set_toc([list(i) for i in items])
            save_pdf(doc, ctx.output(f"{inp.stem}_yer_imli.pdf"))


@dataclass
class Line:
    page: int
    text: str
    size: float
    bold: bool
    y0: float
    y1: float


def _lines(doc: pymupdf.Document) -> list[Line]:
    out: list[Line] = []
    for page in doc:
        for block in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                if not spans:
                    continue
                text = " ".join("".join(s["text"] for s in spans).split())
                size = round(max(float(s["size"]) for s in spans) * 2) / 2
                bold = all(
                    (int(s.get("flags", 0)) & pymupdf.TEXT_FONT_BOLD) or "bold" in str(s.get("font", "")).lower()
                    for s in spans
                )
                bbox = pymupdf.Rect(line["bbox"])
                out.append(Line(page.number, text, size, bool(bold), bbox.y0, bbox.y1))
    return out


def _normal(text: str) -> str:
    return re.sub(r"\d+", "#", text.lower()).strip()


def detect_headings(doc: pymupdf.Document, max_level: int) -> list[tuple[int, str, int]]:
    lines = _lines(doc)
    if not lines:
        return []
    chars: Counter[float] = Counter()
    for ln in lines:
        chars[ln.size] += len(ln.text)
    body = chars.most_common(1)[0][0]

    # Running headers / footers: the same text (digits ignored) on most pages.
    pages_with: dict[str, set[int]] = {}
    for ln in lines:
        pages_with.setdefault(_normal(ln.text), set()).add(ln.page)
    repeated = {t for t, pages in pages_with.items() if len(pages) >= 2 and len(pages) > doc.page_count / 2}

    def style(ln: Line) -> float | None:
        """Ranking key: font size, bold adds a half step. None = body text."""
        if len(ln.text) > MAX_TITLE or not re.search(r"[^\W\d_]", ln.text) or _normal(ln.text) in repeated:
            return None
        if ln.size >= body * 1.15:
            return ln.size + (0.25 if ln.bold else 0)
        if ln.bold and ln.size >= body and len(ln.text) <= 120:
            return body + 0.25
        return None

    styled = [(ln, style(ln)) for ln in lines]
    keys = sorted({k for _, k in styled if k is not None}, reverse=True)[:max_level]
    levels = {k: i + 1 for i, k in enumerate(keys)}

    merged: list[tuple[int, str, int, Line]] = []
    adjacent = False  # the previous text line was a heading too
    for ln, key in styled:
        if key not in levels:
            adjacent = False
            continue
        level = levels[key]
        if merged and adjacent:
            plevel, ptext, ppage, prev = merged[-1]
            # A heading wrapped over several lines: same style, same page,
            # the next line right below.
            wrapped = plevel == level and ppage == ln.page + 1 and -1 <= ln.y0 - prev.y1 < ln.size * 0.5
            if wrapped and len(ptext) + len(ln.text) < MAX_TITLE:
                merged[-1] = (level, f"{ptext} {ln.text}", ppage, ln)
                continue
        adjacent = True
        merged.append((level, ln.text, ln.page + 1, ln))

    # Bookmarks must start at level 1 and never skip a level.
    out: list[tuple[int, str, int]] = []
    prev_level = 0
    for level, text, page, _ in merged[:MAX_OUTLINE_ITEMS]:
        level = min(level, prev_level + 1)
        out.append((level, text, page))
        prev_level = level
    return out


class AutoBookmarksParams(Params):
    max_level: int = Field(2, tr="En fazla düzey", en="Maximum level", ge=1, le=3)
    replace_existing: bool = Field(True, tr="Mevcut yer imlerini değiştir", en="Replace existing bookmarks")


@register
class AutoBookmarks(Operation):
    name = "auto_bookmarks"
    category = "document"
    title_tr, title_en = "Otomatik Yer İmi", "Auto Bookmarks"
    description_tr = "Başlıkları yazı boyutundan tanıyıp içindekiler (yer imleri) oluşturur."
    description_en = "Detect headings from font sizes and build bookmarks (an outline)."
    Params = AutoBookmarksParams

    def run(self, ctx: Context, params: AutoBookmarksParams) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            headings = detect_headings(doc, params.max_level)
            ctx.progress(0.8, "")
            if not headings:
                raise UserError("Belgede başlık bulunamadı.", "No headings were found in the document.")
            toc: list[list[Any]] = [] if params.replace_existing else doc.get_toc(simple=True)
            toc = toc[: MAX_OUTLINE_ITEMS - len(headings)] + [list(h) for h in headings]
            doc.set_toc(toc)
            save_pdf(doc, ctx.output(f"{inp.stem}_yer_imli.pdf"))
            ctx.data = {"bookmarks": len(headings)}


# -- attachments ---------------------------------------------------------------------------


def _embedded(doc: pymupdf.Document) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in doc.embfile_names()[:MAX_ATTACHMENTS]:
        info = doc.embfile_info(name)
        out.append(
            {
                "name": str(name),
                "filename": str(info.get("ufilename") or info.get("filename") or name),
                "description": str(info.get("description") or info.get("desc") or ""),
                "size": int(info.get("size") or 0),
                "created": str(info.get("creationDate") or ""),
                "modified": str(info.get("modDate") or ""),
                "page": None,
            }
        )
    return out


def _annotation_files(doc: pymupdf.Document) -> list[tuple[dict[str, Any], tuple[int, int]]]:
    """File-attachment annotations as ``(info, (page index, annot xref))``."""
    out: list[tuple[dict[str, Any], tuple[int, int]]] = []
    for page in doc:
        for annot in page.annots(types=[pymupdf.PDF_ANNOT_FILE_ATTACHMENT]):
            info = annot.file_info
            out.append(
                (
                    {
                        "name": str(info.get("filename") or "ek"),
                        "filename": str(info.get("ufilename") or info.get("filename") or "ek"),
                        "description": str(info.get("description") or info.get("desc") or ""),
                        "size": int(info.get("size") or info.get("length") or 0),
                        "created": "",
                        "modified": "",
                        "page": page.number + 1,
                    },
                    (page.number, annot.xref),
                )
            )
            if len(out) >= MAX_ATTACHMENTS:
                return out
    return out


@register
class AttachmentsList(Operation):
    name = "attachments_list"
    category = "document"
    title_tr, title_en = "Ekleri Listele", "List Attachments"
    description_tr = "PDF'e gömülü dosyaları listeler."
    description_en = "List the files embedded in the PDF."
    returns_data = True

    def run(self, ctx: Context, params: object) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            items = _embedded(doc) + [info for info, _ in _annotation_files(doc)]
            ctx.data = {"attachments": items, "total": len(items)}


class AttachmentAddParams(Params):
    file: str = FileParam(
        tr="Eklenecek dosya", en="File to attach", accept=["pdf", "image", "docx", "xlsx", "pptx", "other"]
    )
    description: str = Field("", tr="Açıklama", en="Description", max_length=500)


@register
class AttachmentAdd(Operation):
    name = "attachment_add"
    category = "document"
    title_tr, title_en = "Dosya Ekle (Gömülü)", "Attach File"
    description_tr = "PDF'in içine bir dosya gömer (ek)."
    description_en = "Embed a file inside the PDF as an attachment."
    Params = AttachmentAddParams

    def run(self, ctx: Context, params: AttachmentAddParams) -> None:
        extra = ctx.files["file"]
        if extra.path.stat().st_size > MAX_ATTACHMENT_BYTES:
            raise UserError("Eklenecek dosya çok büyük.", "The file to attach is too large.")
        data = extra.path.read_bytes()
        filename = safe_filename(extra.name, default="ek")
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            taken = set(doc.embfile_names())
            name, n = filename, 2
            stem, dot, ext = filename.rpartition(".")
            while name in taken:
                name = f"{stem} ({n}).{ext}" if dot else f"{filename} ({n})"
                n += 1
            doc.embfile_add(name, data, filename=name, ufilename=name, desc=params.description)
            save_pdf(doc, ctx.output(f"{inp.stem}_ekli.pdf"))


@register
class AttachmentsExtract(Operation):
    name = "attachments_extract"
    category = "document"
    title_tr, title_en = "Ekleri Çıkar", "Extract Attachments"
    description_tr = "PDF'e gömülü tüm dosyaları ZIP olarak indirir."
    description_en = "Download every file embedded in the PDF as a ZIP."

    def run(self, ctx: Context, params: object) -> None:
        inp = ctx.inputs[0]
        skipped: list[str] = []
        written: list[str] = []
        with open_pdf(inp.path, inp.password) as doc:
            sources: list[tuple[dict[str, Any], tuple[int, int] | None]] = [(info, None) for info in _embedded(doc)]
            sources += _annotation_files(doc)
            if not sources:
                raise UserError("Bu PDF'te gömülü dosya yok.", "This PDF has no embedded files.")
            out = ctx.output(f"{inp.stem}_ekler.zip")
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                for k, (info, where) in enumerate(sources):
                    label = info["filename"]
                    if info["size"] > MAX_ATTACHMENT_BYTES:
                        skipped.append(label)
                        continue
                    data: bytes = _annot_file(doc, *where) if where else doc.embfile_get(info["name"])
                    if len(data) > MAX_ATTACHMENT_BYTES:
                        skipped.append(label)
                        continue
                    # Base name only: no directories, so no zip-slip on unpack.
                    name = _unique(safe_filename(label, default="ek"), written)
                    written.append(name)
                    zf.writestr(name, data)
                    ctx.progress((k + 1) / len(sources), "")
        ctx.data = {"extracted": len(written), "skipped": skipped}
        if not written:
            raise UserError(
                "Eklerin hepsi boyut sınırını (200 MB) aşıyor.",
                "Every attachment exceeds the size limit (200 MB).",
            )


def _annot_file(doc: pymupdf.Document, pno: int, xref: int) -> bytes:
    page = doc[pno]
    annot = page.load_annot(xref)
    data: bytes = annot.get_file() if annot is not None else b""
    return data


def _unique(name: str, taken: list[str]) -> str:
    lower = {t.lower() for t in taken}
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    candidate, n = name, 2
    while candidate.lower() in lower:
        candidate = f"{stem} ({n}).{ext}" if ext else f"{stem} ({n})"
        n += 1
    return candidate
