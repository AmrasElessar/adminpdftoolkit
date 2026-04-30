"""PDF Intelligence Engine v2 — metadata, outline, search, image extraction,
thumbnails, layout detection, deep analyze.

These helpers extend the existing primitives (extractability, granularity,
glyph coverage, font catalog) into a fuller analysis layer. They power
both the editor and the PDF Tools side, sharing one codebase.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .editor import _classify_extractability_from_doc
from .logging_setup import logger
from .pdf_tools import _save_pdf


# ----- Metadata read / write ------------------------------------------------
def _metadata_from_doc(doc: Any) -> dict[str, Any]:
    """Inner: build the metadata dict from an already-open ``fitz.Document``."""
    meta = dict(doc.metadata or {})
    return {
        "title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "subject": meta.get("subject", ""),
        "keywords": meta.get("keywords", ""),
        "creator": meta.get("creator", ""),
        "producer": meta.get("producer", ""),
        "creation_date": meta.get("creationDate", ""),
        "modification_date": meta.get("modDate", ""),
        "format": meta.get("format", ""),
        "encryption": meta.get("encryption"),
        "page_count": doc.page_count,
        "is_encrypted": bool(doc.is_encrypted),
        "is_pdf": doc.is_pdf,
        "needs_pass": doc.needs_pass,
    }


def extract_metadata(input_path: Path) -> dict[str, Any]:
    """Return the PDF's Info-dictionary metadata + structural counts."""
    import fitz

    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        return _metadata_from_doc(doc)


def set_metadata(
    input_path: Path,
    output: Path,
    *,
    title: str | None = None,
    author: str | None = None,
    subject: str | None = None,
    keywords: str | None = None,
) -> None:
    """Write a subset of the Info dictionary to a new PDF."""
    import fitz

    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        meta = dict(doc.metadata or {})
        if title is not None:
            meta["title"] = title
        if author is not None:
            meta["author"] = author
        if subject is not None:
            meta["subject"] = subject
        if keywords is not None:
            meta["keywords"] = keywords
        doc.set_metadata(meta)
        _save_pdf(doc, output)


# ----- Outline / TOC --------------------------------------------------------
def _outline_from_doc(doc: Any) -> list[dict[str, Any]]:
    """Inner: extract the TOC tree from an already-open document."""
    toc = doc.get_toc(simple=False) or []
    out: list[dict[str, Any]] = []
    for entry in toc:
        if not entry or len(entry) < 3:
            continue
        level = int(entry[0])
        title = str(entry[1] or "").strip()
        page = int(entry[2])
        y = 0.0
        if len(entry) >= 4 and isinstance(entry[3], dict):
            destination = entry[3]
            xy = destination.get("to") or destination.get("kind")
            if xy is not None and hasattr(xy, "y"):
                y = float(xy.y)
        out.append({"level": level, "title": title, "page": page, "y": y})
    return out


def extract_outline(input_path: Path) -> list[dict[str, Any]]:
    """Return the PDF's bookmark / TOC tree as a flat list with levels.

    Each entry::

        {"level": 1, "title": "Chapter 1", "page": 5, "y": 120.0}

    Empty list when the document has no outline.
    """
    import fitz

    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        return _outline_from_doc(doc)


# ----- Text search ---------------------------------------------------------
def find_text(
    input_path: Path,
    query: str,
    *,
    case_sensitive: bool = False,
    whole_words: bool = False,
    max_pages: int | None = None,
    max_results: int = 1000,
) -> list[dict[str, Any]]:
    """Search every page for ``query``, return per-occurrence bbox + context.

    Each entry::

        {"page": 1, "rect": [x0,y0,x1,y1], "text": "matched span", "context": "…matched span…"}

    The search uses PyMuPDF's ``page.search_for`` (returns rects). Context
    is a 60-char window from the page text around the first occurrence;
    useful for showing matches in a search results pane.
    """
    if not query or not query.strip():
        raise ValueError("Aranacak metin boş.")
    import fitz

    needle = query if case_sensitive else query.casefold()
    out: list[dict[str, Any]] = []
    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        for pno, page in enumerate(doc):
            if max_pages is not None and pno >= max_pages:
                break
            page_text = page.get_text() or ""
            haystack = page_text if case_sensitive else page_text.casefold()
            try:
                # PyMuPDF ≥ 1.18 supports flags: TEXT_PRESERVE_LIGATURES, etc.
                if not case_sensitive:
                    # search_for is case-insensitive by default in recent versions
                    pass
                rects = page.search_for(query, quads=False)
            except Exception:
                rects = []
            # Pair each rect with a context window
            cursor = 0
            for rect in rects:
                if len(out) >= max_results:
                    return out
                # Find the position in haystack from cursor onwards
                pos = haystack.find(needle, cursor)
                if pos == -1:
                    pos = haystack.find(needle)
                cursor = pos + len(needle) if pos != -1 else cursor
                ctx = ""
                if pos != -1:
                    start = max(0, pos - 30)
                    end = min(len(page_text), pos + len(query) + 30)
                    ctx = page_text[start:end].replace("\n", " ").strip()
                if whole_words and pos != -1:
                    pre = page_text[pos - 1] if pos > 0 else " "
                    post = page_text[pos + len(query)] if pos + len(query) < len(page_text) else " "
                    if pre.isalnum() or post.isalnum():
                        continue
                out.append(
                    {
                        "page": pno + 1,
                        "rect": [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)],
                        "text": query,
                        "context": ctx,
                    }
                )
    return out


# ----- Image extraction ----------------------------------------------------
def extract_images(
    input_path: Path,
    output_dir: Path,
    *,
    min_size: int = 32,
    page: int | None = None,
) -> list[dict[str, Any]]:
    """Pull every embedded raster image out into individual files.

    Returns a list of ``{"page", "index", "filename", "width", "height",
    "xref"}``. Images smaller than ``min_size`` × ``min_size`` (decorative
    icons / glyph fragments) are skipped. ``page=None`` walks every page;
    pass a 1-indexed integer to limit to one page.
    """
    import fitz

    output_dir.mkdir(parents=True, exist_ok=True)
    out: list[dict[str, Any]] = []
    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        seen: set[int] = set()  # dedupe shared xrefs (logos repeated across pages)
        page_iter = [(page - 1, doc[page - 1])] if page is not None else list(enumerate(doc))
        for pno, p in page_iter:
            for idx, img_info in enumerate(p.get_images(full=True)):
                xref = img_info[0]
                if xref in seen:
                    continue
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.width < min_size or pix.height < min_size:
                        pix = None
                        continue
                    if pix.colorspace and pix.colorspace.n > 3:
                        # CMYK / DeviceN — convert to RGB for portability
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    ext = "png"
                    filename = f"page{pno + 1}_img{idx + 1}_xref{xref}.{ext}"
                    out_path = output_dir / filename
                    pix.save(str(out_path))
                    pix = None
                    out.append(
                        {
                            "page": pno + 1,
                            "index": idx + 1,
                            "filename": filename,
                            "width": img_info[2],
                            "height": img_info[3],
                            "xref": xref,
                        }
                    )
                    seen.add(xref)
                except Exception as e:
                    logger.debug("extract_images: xref %s skipped (%s)", xref, e)
                    continue
    return out


# ----- Thumbnail -----------------------------------------------------------
def pdf_thumbnail(
    input_path: Path,
    output: Path,
    *,
    page_no: int = 1,
    dpi: int = 100,
    fmt: str = "png",
) -> tuple[int, int]:
    """Render a single page of the PDF as an image. Returns ``(width, height)``."""
    import fitz

    if fmt not in ("png", "jpg", "jpeg"):
        raise ValueError("Thumbnail formatı 'png' veya 'jpg' olmalı.")
    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        if page_no < 1 or page_no > doc.page_count:
            raise ValueError(f"Sayfa numarası geçersiz: {page_no} (1-{doc.page_count}).")
        page = doc[page_no - 1]
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        if fmt in ("jpg", "jpeg"):
            pix.save(str(output), output="jpeg")
        else:
            pix.save(str(output))
        return pix.width, pix.height


# ----- Layout: column detection -------------------------------------------
def detect_text_columns(page: Any, *, threshold_ratio: float = 0.6) -> int:
    """Estimate the number of text columns on ``page`` using span x-coords.

    Builds a histogram of span x0 values, finds peaks; returns 1, 2, or 3.
    Used to improve reading order in ``extract_text_spans`` for multi-column
    documents (sözleşmeler, akademik makaleler).
    """
    import fitz  # noqa: F401 — page is already a fitz.Page

    x_starts: list[float] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            bbox = line.get("bbox")
            if bbox:
                x_starts.append(float(bbox[0]))
    if len(x_starts) < 5:
        return 1
    x_starts.sort()
    # Quick & dirty: bucket into 20-pt bins, count peaks > threshold of max
    bin_size = 20.0
    bins: dict[int, int] = {}
    for x in x_starts:
        bins[int(x // bin_size)] = bins.get(int(x // bin_size), 0) + 1
    if not bins:
        return 1
    peak = max(bins.values())
    cutoff = peak * threshold_ratio
    cluster_count = 0
    last_b = None
    for b in sorted(bins):
        if bins[b] >= cutoff:
            if last_b is None or b - last_b > 1:
                cluster_count += 1
            last_b = b
    return max(1, min(3, cluster_count))


# ----- Layout: header / footer detection ----------------------------------
def _headers_footers_from_doc(
    doc: Any,
    *,
    top_pct: float = 0.10,
    bottom_pct: float = 0.10,
) -> dict[str, list[str]]:
    """Inner: detect repeating headers/footers from an already-open doc."""
    top_lines: dict[str, int] = {}
    bottom_lines: dict[str, int] = {}
    page_count = doc.page_count
    if page_count < 3:
        return {"headers": [], "footers": []}
    for page in doc:
        h = page.rect.height
        top_y = h * top_pct
        bottom_y = h * (1 - bottom_pct)
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                bbox = line.get("bbox")
                if not bbox:
                    continue
                text = " ".join(
                    (s.get("text") or "").strip() for s in line.get("spans", [])
                ).strip()
                if not text:
                    continue
                # Normalize: collapse digits to placeholder so "Sayfa 3" + "Sayfa 4" match
                key = re.sub(r"\d+", "#", text.lower())
                if bbox[3] <= top_y:
                    top_lines[key] = top_lines.get(key, 0) + 1
                elif bbox[1] >= bottom_y:
                    bottom_lines[key] = bottom_lines.get(key, 0) + 1
    threshold = max(2, page_count // 2)
    headers = [k for k, v in top_lines.items() if v >= threshold]
    footers = [k for k, v in bottom_lines.items() if v >= threshold]
    return {"headers": headers, "footers": footers}


def detect_headers_footers(
    input_path: Path, *, top_pct: float = 0.10, bottom_pct: float = 0.10
) -> dict[str, list[str]]:
    """Find lines that repeat at the top / bottom of multiple pages.

    A line is flagged as a header/footer if it appears (case-insensitive,
    whitespace-normalised) on ≥ 50% of pages within the top/bottom slice.
    Used by ``pdf_to_markdown`` to skip page-numbering and running titles.
    """
    import fitz

    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        return _headers_footers_from_doc(doc, top_pct=top_pct, bottom_pct=bottom_pct)


# ----- Deep analyze --------------------------------------------------------
def deep_analyze(input_path: Path) -> dict[str, Any]:
    """Run every public analyzer in one pass and return a combined report.

    Opens the PDF once and runs every per-doc analyzer against the same
    handle — a measurable win over the previous five-open implementation
    when the editor pulls /pdf/info on every document load.
    """
    import fitz

    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        extractability = _classify_extractability_from_doc(doc)
        metadata = _metadata_from_doc(doc)
        outline = _outline_from_doc(doc)
        headers_footers = (
            _headers_footers_from_doc(doc)
            if extractability["extractable"]
            else {"headers": [], "footers": []}
        )

        pages_info: list[dict[str, Any]] = []
        for pno, page in enumerate(doc):
            text = page.get_text() or ""
            pages_info.append(
                {
                    "page": pno + 1,
                    "width": float(page.rect.width),
                    "height": float(page.rect.height),
                    "rotation": int(page.rotation),
                    "char_count": len(text.strip()),
                    "image_count": len(page.get_images(full=False)),
                    "columns": detect_text_columns(page) if text.strip() else 0,
                }
            )

    return {
        "extractability": extractability,
        "metadata": metadata,
        "outline": outline,
        "outline_count": len(outline),
        "headers_footers": headers_footers,
        "pages": pages_info,
    }
