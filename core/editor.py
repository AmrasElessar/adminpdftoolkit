"""Editor operations (Section / Phase 4b — annotation mode).

The frontend (``static/pdf-editor.mjs``) emits an "operations" list whenever
the user saves their edits. Each op is a plain dict shaped like:

  { "type": "highlight" | "underline" | "strikeout" |
            "sticky" | "ink" | "image" | "text" | "rect" |
            "ellipse" | "line" | "replace",
    "page": 1,                               # 1-indexed
    "rect":  [x0, y0, x1, y1],               # rect-based ops + image
    "point": [x, y],                         # sticky
    "content": "...",                        # sticky note text
    "strokes": [[[x,y], [x,y], ...], ...],   # ink: list of strokes
    "stroke_width": 1.5,                     # ink line thickness (pt)
    "image_data_url": "data:image/png;base64,...",
    "color":   [r, g, b],                    # 0-1 floats
    "opacity": 0.4,                          # 0-1
  }

All coordinates are in PDF points (top-left origin), converted on the
frontend before being sent. Page rect / mediabox are validated server-side.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from state import BASE_DIR

from .errors import sanitize_error
from .logging_setup import logger
from .pdf_tools import _find_unicode_font, _save_pdf

# ---------------------------------------------------------------------------
# 16. Editor operations (Section / Phase 4b — annotation mode)
# ---------------------------------------------------------------------------
# The frontend (`static/pdf-editor.mjs`) emits an "operations" list whenever
# the user saves their edits. Each op is a plain dict shaped like:
#
#   { "type": "highlight" | "underline" | "strikeout" |
#             "sticky" | "ink" | "image",
#     "page": 1,                               # 1-indexed
#     "rect":  [x0, y0, x1, y1],               # rect-based ops + image
#     "point": [x, y],                         # sticky
#     "content": "...",                        # sticky note text
#     "strokes": [[[x,y], [x,y], …], …],       # ink: list of strokes
#     "stroke_width": 1.5,                     # ink line thickness (pt)
#     "image_data_url": "data:image/png;base64,…",
#     "color":   [r, g, b],                    # 0-1 floats (highlight bg etc.)
#     "opacity": 0.4,                          # 0-1
#   }
#
# All coordinates are in PDF points (top-left origin), converted on the
# frontend before being sent. Page rect / mediabox are validated server-side.

_VALID_OPS: frozenset[str] = frozenset(
    {
        "highlight",
        "underline",
        "strikeout",
        "sticky",
        "ink",
        "image",
        "text",
        "rect",
        "ellipse",
        "line",
        "replace",
    }
)


# ---------------------------------------------------------------------------
# Bundled font catalogue — resolves a family + style combo to a real TTF on
# disk. Used both by the editor's /pdf/edit/fonts endpoint AND by the text-
# overlay op when emitting text to the PDF. Single source of truth.
# ---------------------------------------------------------------------------
EDITOR_FONT_FAMILIES: list[dict[str, Any]] = [
    {
        "id": "noto-sans",
        "label": "Noto Sans",
        "category": "sans",
        "variants": {
            "regular": "NotoSans-Regular.ttf",
            "bold": "NotoSans-Bold.ttf",
            "italic": "NotoSans-Italic.ttf",
            "bolditalic": "NotoSans-BoldItalic.ttf",
        },
    },
    {
        "id": "noto-serif",
        "label": "Noto Serif",
        "category": "serif",
        "variants": {
            "regular": "NotoSerif-Regular.ttf",
            "bold": "NotoSerif-Bold.ttf",
            "italic": "NotoSerif-Italic.ttf",
            "bolditalic": "NotoSerif-BoldItalic.ttf",
        },
    },
    {
        "id": "noto-mono",
        "label": "Noto Sans Mono",
        "category": "mono",
        "variants": {
            "regular": "NotoSansMono-Regular.ttf",
            "bold": "NotoSansMono-Bold.ttf",
        },
    },
    {
        "id": "dejavu-sans",
        "label": "DejaVu Sans",
        "category": "sans",
        "variants": {
            "regular": "DejaVuSans.ttf",
            "bold": "DejaVuSans-Bold.ttf",
        },
    },
    {
        "id": "dejavu-serif",
        "label": "DejaVu Serif",
        "category": "serif",
        "variants": {"regular": "DejaVuSerif.ttf"},
    },
    {
        "id": "dejavu-mono",
        "label": "DejaVu Mono",
        "category": "mono",
        "variants": {"regular": "DejaVuSansMono.ttf"},
    },
]

_FONTS_DIR: Path = BASE_DIR / "static" / "fonts"


def editor_font_catalog() -> list[dict[str, Any]]:
    """Return the families that have at least one TTF physically present.

    Each entry includes ``id``, ``label``, ``category`` and the list of
    variants (``["regular", "bold", "italic", "bolditalic"]``) actually
    available on disk. Frontend uses this to gate the bold / italic
    checkboxes per family.

    NOTE: This returns only **bundled** families. The user-facing catalog
    (bundled + locally installed system fonts) lives in
    :func:`core.fonts.editor_font_catalog_with_system`, which the
    ``/pdf/edit/fonts`` route uses. Keep this thin function for internal
    callers that explicitly want the bundled-only list.
    """
    out: list[dict[str, Any]] = []
    for fam in EDITOR_FONT_FAMILIES:
        present: list[str] = []
        for variant_key, filename in fam["variants"].items():
            if (_FONTS_DIR / filename).is_file():
                present.append(variant_key)
        if not present:
            continue
        out.append(
            {
                "id": fam["id"],
                "label": fam["label"],
                "category": fam["category"],
                "variants": present,
                "source": "bundled",
            }
        )
    return out


def resolve_editor_font(
    family_id: str,
    *,
    bold: bool = False,
    italic: bool = False,
) -> Path | None:
    """Resolve a (family, bold, italic) combination to a TTF path.

    Falls back to the family's regular variant if the requested style is not
    bundled, then to Noto Sans, then to whatever ``_find_unicode_font()``
    returns. Returns ``None`` only when no Unicode TTF is available at all.

    NOTE: handles only **bundled** families. For system-font-aware lookup
    (sys:* ids), use :func:`core.fonts.resolve_editor_font_with_system`.
    """
    family = next((f for f in EDITOR_FONT_FAMILIES if f["id"] == family_id), None)
    if family is None:
        family = next((f for f in EDITOR_FONT_FAMILIES if f["id"] == "noto-sans"), None)
    if family is None:
        fallback = _find_unicode_font()
        return Path(fallback) if fallback else None
    variants = family["variants"]
    style_key = (
        "bolditalic"
        if bold and italic
        else ("bold" if bold else ("italic" if italic else "regular"))
    )
    for candidate in (
        style_key,
        "regular",
        "bold" if bold else "regular",
        "italic" if italic else "regular",
    ):
        filename = variants.get(candidate)
        if not filename:
            continue
        path: Path = _FONTS_DIR / filename
        if path.is_file():
            return path
    fallback = _find_unicode_font()
    return Path(fallback) if fallback else None


def _parse_data_url(data_url: str) -> bytes:
    """Decode ``data:<mime>;base64,<payload>`` into raw bytes."""
    import base64

    if not data_url.startswith("data:"):
        raise ValueError("Görsel data URL formatında olmalı.")
    try:
        header, payload = data_url.split(",", 1)
    except ValueError as e:
        raise ValueError("Geçersiz data URL — virgül eksik.") from e
    if "base64" not in header:
        raise ValueError("Yalnızca base64 data URL'leri desteklenir.")
    try:
        return base64.b64decode(payload)
    except Exception as e:
        raise ValueError("Görsel base64 çözülemedi.") from e


def _coerce_rect(value: Any, page_rect: Any) -> Any:
    """Convert ``[x0, y0, x1, y1]`` → ``fitz.Rect`` clamped inside the page."""
    import fitz

    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("rect 4 elemanlı bir liste olmalı [x0, y0, x1, y1].")
    try:
        x0, y0, x1, y1 = (float(v) for v in value)
    except (TypeError, ValueError) as e:
        raise ValueError("rect değerleri sayısal olmalı.") from e
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    rect = fitz.Rect(x0, y0, x1, y1) & page_rect
    if rect.is_empty or rect.width < 0.5 or rect.height < 0.5:
        raise ValueError("rect sayfa dışına düşüyor veya çok küçük.")
    return rect


def _coerce_point(value: Any, page_rect: Any) -> Any:
    """Convert ``[x, y]`` → ``fitz.Point`` clamped to the page."""
    import fitz

    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("point 2 elemanlı bir liste olmalı [x, y].")
    try:
        x, y = float(value[0]), float(value[1])
    except (TypeError, ValueError) as e:
        raise ValueError("point değerleri sayısal olmalı.") from e
    x = max(page_rect.x0, min(page_rect.x1, x))
    y = max(page_rect.y0, min(page_rect.y1, y))
    return fitz.Point(x, y)


def _coerce_color(value: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if value is None:
        return default
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            r, g, b = (max(0.0, min(1.0, float(v))) for v in value)
            return (r, g, b)
        except (TypeError, ValueError):
            return default
    return default


def _apply_one_op(page: Any, op: dict, op_index: int) -> None:
    """Apply a single operation to ``page`` (or raise ValueError)."""
    import fitz

    op_type = op.get("type")
    if op_type not in _VALID_OPS:
        raise ValueError(f"#{op_index}: bilinmeyen operasyon tipi '{op_type}'.")
    page_rect = page.rect

    if op_type in ("highlight", "underline", "strikeout"):
        rect = _coerce_rect(op.get("rect"), page_rect)
        color = _coerce_color(
            op.get("color"),
            (1.0, 0.92, 0.23) if op_type == "highlight" else (1.0, 0.0, 0.0),
        )
        if op_type == "highlight":
            annot = page.add_highlight_annot(rect)
        elif op_type == "underline":
            annot = page.add_underline_annot(rect)
        else:
            annot = page.add_strikeout_annot(rect)
        try:
            annot.set_colors({"stroke": color})
            annot.update()
        except Exception:
            pass
        return

    if op_type == "sticky":
        point = _coerce_point(op.get("point"), page_rect)
        content = str(op.get("content") or "").strip()
        if not content:
            raise ValueError(f"#{op_index}: sticky note boş olamaz.")
        annot = page.add_text_annot(point, content)
        try:
            color = _coerce_color(op.get("color"), (1.0, 0.85, 0.0))
            annot.set_colors({"stroke": color})
            annot.update()
        except Exception:
            pass
        return

    if op_type == "ink":
        strokes = op.get("strokes")
        if not isinstance(strokes, list) or not strokes:
            raise ValueError(f"#{op_index}: ink için en az 1 stroke gerekli.")
        normalised: list[list[tuple[float, float]]] = []
        for s_idx, stroke in enumerate(strokes):
            if not isinstance(stroke, list) or len(stroke) < 2:
                raise ValueError(f"#{op_index}: ink stroke #{s_idx} en az 2 nokta içermeli.")
            pts: list[tuple[float, float]] = []
            for p in stroke:
                if not isinstance(p, (list, tuple)) or len(p) != 2:
                    raise ValueError(f"#{op_index}: ink noktası [x, y] olmalı.")
                try:
                    pts.append((float(p[0]), float(p[1])))
                except (TypeError, ValueError) as e:
                    raise ValueError(f"#{op_index}: ink koordinatı sayısal olmalı.") from e
            normalised.append(pts)
        annot = page.add_ink_annot(normalised)
        color = _coerce_color(op.get("color"), (0.0, 0.0, 0.0))
        width = float(op.get("stroke_width") or 1.5)
        width = max(0.25, min(20.0, width))
        try:
            annot.set_colors({"stroke": color})
            annot.set_border(width=width)
            annot.update()
        except Exception:
            pass
        return

    if op_type == "image":
        rect = _coerce_rect(op.get("rect"), page_rect)
        data_url = op.get("image_data_url")
        if not isinstance(data_url, str) or not data_url:
            raise ValueError(f"#{op_index}: image_data_url eksik.")
        img_bytes = _parse_data_url(data_url)
        try:
            page.insert_image(rect, stream=img_bytes, overlay=True)
        except TypeError:
            page.insert_image(rect, stream=img_bytes)
        return

    # ----- overlay ops (Phase 4c) -----
    if op_type == "text":
        text = str(op.get("text") or "").strip()
        if not text:
            raise ValueError(f"#{op_index}: text içeriği boş olamaz.")
        point = _coerce_point(op.get("point"), page_rect)
        fontsize = float(op.get("fontsize") or 12)
        fontsize = max(4.0, min(200.0, fontsize))
        color = _coerce_color(op.get("color"), (0.0, 0.0, 0.0))
        family_id = str(op.get("font_id") or "noto-sans")
        bold = bool(op.get("bold"))
        italic = bool(op.get("italic"))
        from core.fonts import resolve_editor_font_with_system

        font_path = resolve_editor_font_with_system(family_id, bold=bold, italic=italic)
        # PyMuPDF positions text by the BASELINE — adjust point.y so the
        # user's click lands at the visual top of the glyph (matches the
        # frontend preview which draws from top-left).
        baseline_y = point.y + fontsize * 0.85
        try:
            if font_path:
                page.insert_text(
                    fitz.Point(point.x, baseline_y),
                    text,
                    fontsize=fontsize,
                    color=color,
                    fontname="hf-uni",
                    fontfile=str(font_path),
                )
            else:
                page.insert_text(
                    fitz.Point(point.x, baseline_y),
                    text,
                    fontsize=fontsize,
                    color=color,
                    fontname="helv",
                )
        except Exception as e:
            raise ValueError(f"#{op_index}: metin yerleştirilemedi ({sanitize_error(e)}).") from e
        return

    if op_type in ("rect", "ellipse"):
        rect = _coerce_rect(op.get("rect"), page_rect)
        stroke = _coerce_color(op.get("color"), (0.0, 0.0, 0.0))
        fill_value = op.get("fill")
        fill = _coerce_color(fill_value, stroke) if fill_value else None
        width = float(op.get("stroke_width") or 1.0)
        width = max(0.0, min(20.0, width))
        if op_type == "rect":
            page.draw_rect(rect, color=stroke, fill=fill, width=width)
        else:
            page.draw_oval(rect, color=stroke, fill=fill, width=width)
        return

    if op_type == "line":
        p1 = _coerce_point(op.get("p1"), page_rect)
        p2 = _coerce_point(op.get("p2"), page_rect)
        if abs(p1.x - p2.x) < 0.5 and abs(p1.y - p2.y) < 0.5:
            raise ValueError(f"#{op_index}: çizgi başı ve sonu aynı.")
        color = _coerce_color(op.get("color"), (0.0, 0.0, 0.0))
        width = float(op.get("stroke_width") or 1.5)
        width = max(0.25, min(20.0, width))
        page.draw_line(p1, p2, color=color, width=width)
        return

    # ----- replace (Phase 4d) — handled in two passes; see _apply_one_op call site
    if op_type == "replace":
        # Implementation lives in _apply_replace_ops_for_page so all replace
        # ops on the same page share one apply_redactions() call. Reaching
        # here means the caller forgot to filter — raise so it doesn't
        # silently produce wrong output.
        raise ValueError(
            f"#{op_index}: replace ops must be applied via _apply_replace_ops_for_page."
        )


# ----- Replace op support ------------------------------------------------
def _map_font_name_to_family(font_name: str) -> tuple[str, bool, bool]:
    """Best-effort guess of (family_id, bold, italic) from a PDF font name.

    PDF font names are arbitrary strings ("Helvetica", "Arial-BoldMT",
    "TimesNewRomanPS-ItalicMT", "Courier New Bold Italic"). We grep for
    well-known keywords to pick the closest bundled family + style.
    """
    raw = (font_name or "").strip()
    lower = raw.lower()
    bold = any(token in lower for token in ("bold", "heavy", "black", "demi", "bd-", "-bd"))
    italic = any(token in lower for token in ("italic", "oblique", "-it", "it-", "slant"))
    if any(t in lower for t in ("mono", "courier", "consolas", "menlo", "fixed")):
        family = "noto-mono"
    elif any(
        t in lower
        for t in (
            "times",
            "serif",
            "garamond",
            "georgia",
            "palatino",
            "minion",
            "caslon",
            "baskerville",
            "didot",
        )
    ):
        family = "noto-serif"
    else:
        family = "noto-sans"
    return family, bold, italic


def _color_int_to_rgb(value: int) -> tuple[float, float, float]:
    """PyMuPDF span ``color`` is a packed int (0xRRGGBB)."""
    try:
        v = int(value or 0)
    except (TypeError, ValueError):
        return (0.0, 0.0, 0.0)
    r = ((v >> 16) & 0xFF) / 255.0
    g = ((v >> 8) & 0xFF) / 255.0
    b = (v & 0xFF) / 255.0
    return (r, g, b)


def _classify_extractability_from_doc(doc: Any) -> dict[str, Any]:
    """Inner version of ``classify_pdf_extractability`` that takes an already
    open ``fitz.Document`` — lets ``deep_analyze`` collapse multiple opens
    into one. Caller owns the document lifecycle.
    """
    pages_with_text = 0
    pages_with_only_images = 0
    total_chars = 0
    total_pages = doc.page_count
    for page in doc:
        text = (page.get_text() or "").strip()
        has_text = bool(text)
        has_image = bool(page.get_images(full=False))
        if has_text:
            pages_with_text += 1
            total_chars += len(text)
        elif has_image:
            pages_with_only_images += 1

    if pages_with_text == 0:
        if pages_with_only_images > 0:
            kind = "image"
            msg = (
                "Bu PDF görsel/taranmış — metin katmanı yok. "
                "Mevcut metni değiştir modu çalışmaz; OCR ile metin çıkarın "
                "veya overlay modunda yeni metin/şekil ekleyin."
            )
        else:
            kind = "empty"
            msg = "PDF'te ne metin ne de görsel bulunamadı."
    elif pages_with_only_images > 0:
        kind = "hybrid"
        msg = (
            f"{pages_with_only_images}/{total_pages} sayfa görsel-tabanlı "
            "(metin değiştirme yalnızca metinli sayfalarda çalışır)."
        )
    else:
        kind = "vector"
        msg = f"Tüm {total_pages} sayfa metin içeriyor — replace modu kullanılabilir."

    return {
        "type": kind,
        "total_pages": total_pages,
        "pages_with_text": pages_with_text,
        "pages_with_only_images": pages_with_only_images,
        "total_chars": total_chars,
        "extractable": pages_with_text > 0,
        "message": msg,
    }


def classify_pdf_extractability(input_path: Path) -> dict[str, Any]:
    """Identify whether a PDF is vector (text-extractable), image (scanned),
    or hybrid. The editor's "replace" mode only works on extractable text;
    pages without any extractable text need a different flow (OCR or overlay).

    Returns shape::

        {
            "type": "vector" | "image" | "hybrid" | "empty",
            "total_pages": int,
            "pages_with_text": int,
            "pages_with_only_images": int,
            "total_chars": int,
            "extractable": bool,
            "message": str,
        }
    """
    import fitz

    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        return _classify_extractability_from_doc(doc)


def font_glyph_coverage(font_buffer: bytes, text: str) -> tuple[int, int]:
    """Return ``(covered, total)`` — how many code points of ``text`` the
    font in ``font_buffer`` actually has glyphs for.

    Subsetted embedded PDF fonts (the common case) only contain glyphs
    already used in the document. Calling ``page.insert_text`` with a
    subsetted font and *new* glyphs produces tofu (.notdef rectangles).
    Use this helper *before* committing to an embedded-font replacement to
    decide whether to fall back to the bundled Noto/DejaVu set.

    Only ``has_glyph`` is consulted — ``glyph_advance`` is unreliable here
    (it returns nonzero defaults even for codepoints with no actual glyph).
    """
    import fitz

    if not text:
        return (0, 0)
    try:
        font = fitz.Font(fontbuffer=font_buffer)
    except Exception:
        return (0, len(text))
    has_glyph = getattr(font, "has_glyph", None)
    covered = 0
    total = 0
    for ch in text:
        cp = ord(ch)
        if cp < 32:  # control / whitespace — assume covered
            covered += 1
            total += 1
            continue
        total += 1
        if has_glyph is None:
            # No has_glyph API → conservatively assume the font covers it.
            covered += 1
            continue
        try:
            if has_glyph(cp) > 0:
                covered += 1
        except Exception:
            pass
    return (covered, total)


def _spans_share_style(a: dict, b: dict, *, y_tol: float = 1.0) -> bool:
    """True if two spans look like they belong to the same continuous run.

    Same line (y0 within tolerance), same font name + size + colour, same
    bold/italic flags. Used by the line-granularity merger.
    """
    if a["page"] != b["page"]:
        return False
    if abs(a["rect"][1] - b["rect"][1]) > y_tol:
        return False
    if abs(a["rect"][3] - b["rect"][3]) > y_tol:
        return False
    if a["font_name"] != b["font_name"]:
        return False
    if abs(a["fontsize"] - b["fontsize"]) > 0.5:
        return False
    if a["bold"] != b["bold"] or a["italic"] != b["italic"]:
        return False
    return bool(a["color"] == b["color"])


def _merge_consecutive_spans(spans: list[dict]) -> list[dict]:
    """Merge horizontally-consecutive spans that share style on the same line.

    Useful so a phrase like "tarafından imzalanmıştır" — which the PDF emits
    as 3 separate spans — becomes one clickable block in the editor.
    Inserts a single space between merged texts when the source spans had a
    visual gap; otherwise concatenates directly.
    """
    if not spans:
        return []
    out: list[dict] = []
    current = dict(spans[0])
    for s in spans[1:]:
        if _spans_share_style(current, s):
            # Merge: union bbox, gap-aware text join
            cur_rect = current["rect"]
            s_rect = s["rect"]
            gap = s_rect[0] - cur_rect[2]
            avg_char = max(1.0, current["fontsize"] * 0.3)
            sep = " " if gap > avg_char * 0.5 else ""
            current = {
                **current,
                "rect": [
                    min(cur_rect[0], s_rect[0]),
                    min(cur_rect[1], s_rect[1]),
                    max(cur_rect[2], s_rect[2]),
                    max(cur_rect[3], s_rect[3]),
                ],
                "text": current["text"] + sep + s["text"],
            }
        else:
            out.append(current)
            current = dict(s)
    out.append(current)
    return out


def extract_text_spans(
    input_path: Path,
    *,
    granularity: str = "line",
    merge_adjacent: bool = True,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    """Return per-page text-span metadata for the editor's "replace" mode.

    ``granularity`` controls how raw spans are grouped before being returned:

      • ``"word"``  — every PyMuPDF span as-is (≈ word-level on most PDFs).
      • ``"line"``  — spans on the same visual line are merged (default).
        Uses each line's outer bbox so the user can click anywhere on the
        line and edit the whole phrase.
      • ``"block"`` — every span in the same block (paragraph) is merged
        into a single entry; useful for multi-line edits.

    ``merge_adjacent`` (only meaningful with ``"word"``) further fuses
    consecutive same-style spans on the same line — handy for PDFs that
    over-fragment phrases.

    Each span entry shape::

        {"page": 1, "rect": [x0, y0, x1, y1], "text": "Some text",
         "font_name": "Arial-BoldMT", "font_id": "noto-sans",
         "fontsize": 11.0, "color": [r, g, b], "bold": true, "italic": false,
         "granularity": "line"}

    Empty / whitespace-only spans are dropped. Coordinates are in PDF points
    (top-left origin, same convention as the editor's other ops).
    """
    if granularity not in ("word", "line", "block"):
        raise ValueError(f"granularity 'word'/'line'/'block' olmalı, '{granularity}' geldi.")
    import fitz

    out: list[dict[str, Any]] = []
    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        for pno, page in enumerate(doc):
            if max_pages is not None and pno >= max_pages:
                break
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                if granularity == "block":
                    out.extend(_extract_block_spans(block, pno))
                else:
                    out.extend(_extract_line_spans(block, pno, granularity, merge_adjacent))
    return out


def _make_span_dict(
    page_idx: int,
    rect: Any,
    text: str,
    font_name: str,
    fontsize: float,
    color_int: Any,
    granularity: str,
) -> dict[str, Any]:
    family, bold, italic = _map_font_name_to_family(font_name)
    return {
        "page": page_idx + 1,
        "rect": [float(b) for b in rect],
        "text": text,
        "font_name": font_name,
        "font_id": family,
        "fontsize": float(fontsize or 0),
        "color": list(_color_int_to_rgb(color_int)),
        "bold": bold,
        "italic": italic,
        "granularity": granularity,
    }


def _extract_line_spans(
    block: dict,
    page_idx: int,
    granularity: str,
    merge_adjacent: bool,
) -> list[dict]:
    """Yield word- or line-level entries for one text block."""
    line_results: list[dict] = []
    for line in block.get("lines", []):
        raw: list[dict] = []
        for span in line.get("spans", []):
            text = (span.get("text") or "").strip()
            if not text:
                continue
            raw.append(
                _make_span_dict(
                    page_idx,
                    span.get("bbox") or [0, 0, 0, 0],
                    text,
                    span.get("font") or "",
                    span.get("size") or 0,
                    span.get("color"),
                    granularity,
                )
            )
        if not raw:
            continue
        if granularity == "line":
            # Always collapse a whole line into one entry. Use the first span's
            # style (the most visually prominent) and the line's outer bbox.
            line_bbox = line.get("bbox") or [
                min(s["rect"][0] for s in raw),
                min(s["rect"][1] for s in raw),
                max(s["rect"][2] for s in raw),
                max(s["rect"][3] for s in raw),
            ]
            head = raw[0]
            joined = " ".join(s["text"] for s in raw)
            line_results.append(
                {
                    **head,
                    "rect": [float(b) for b in line_bbox],
                    "text": joined,
                    "granularity": "line",
                }
            )
        elif merge_adjacent:
            line_results.extend(_merge_consecutive_spans(raw))
        else:
            line_results.extend(raw)
    return line_results


def _extract_block_spans(block: dict, page_idx: int) -> list[dict]:
    """Yield one entry covering the entire text block (paragraph)."""
    raw: list[dict] = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = (span.get("text") or "").strip()
            if not text:
                continue
            raw.append(
                _make_span_dict(
                    page_idx,
                    span.get("bbox") or [0, 0, 0, 0],
                    text,
                    span.get("font") or "",
                    span.get("size") or 0,
                    span.get("color"),
                    "block",
                )
            )
    if not raw:
        return []
    block_bbox = block.get("bbox") or [
        min(s["rect"][0] for s in raw),
        min(s["rect"][1] for s in raw),
        max(s["rect"][2] for s in raw),
        max(s["rect"][3] for s in raw),
    ]
    head = raw[0]
    joined = "\n".join(" ".join(s["text"] for s in raw[i : i + 1]) for i in range(len(raw)))
    # Better: group raw by line y, join lines with \n, words with space
    # (approximate; PyMuPDF already preserves order)
    lines_text: list[list[str]] = []
    last_y = None
    for s in raw:
        y0 = round(s["rect"][1], 1)
        if last_y is None or abs(y0 - last_y) > max(1.0, head["fontsize"] * 0.3):
            lines_text.append([])
            last_y = y0
        lines_text[-1].append(s["text"])
    joined = "\n".join(" ".join(parts) for parts in lines_text)
    return [
        {
            **head,
            "rect": [float(b) for b in block_bbox],
            "text": joined,
            "granularity": "block",
        }
    ]


def _sample_bg_color(
    page: Any,
    rect: Any,
    *,
    padding: float = 4.0,
) -> tuple[float, float, float]:
    """Sample the most-common color in the strip around ``rect``.

    Used as the redaction fill so the patched-out area blends with whatever
    was behind the original text — colored backgrounds, gradients, table
    cells, etc. Falls back to white when sampling fails.

    Method: render a thin frame around ``rect`` (left + right + top + bottom
    strips, each ``padding`` points wide) at 72 DPI, then take the mode of
    the pixel colors. This avoids picking glyph ink from inside the rect.
    """
    from collections import Counter

    import fitz

    try:
        h_pad = padding
        v_pad = padding
        # Build four strips: top, bottom, left, right (in PDF points)
        strips = [
            fitz.Rect(rect.x0 - h_pad, rect.y0 - v_pad, rect.x1 + h_pad, rect.y0),  # top
            fitz.Rect(rect.x0 - h_pad, rect.y1, rect.x1 + h_pad, rect.y1 + v_pad),  # bottom
            fitz.Rect(rect.x0 - h_pad, rect.y0, rect.x0, rect.y1),  # left
            fitz.Rect(rect.x1, rect.y0, rect.x1 + h_pad, rect.y1),  # right
        ]
        page_rect = page.rect
        counter: Counter = Counter()
        for s in strips:
            clip = s & page_rect
            if clip.is_empty or clip.width < 0.5 or clip.height < 0.5:
                continue
            pix = page.get_pixmap(clip=clip, dpi=72, alpha=False)
            if pix.colorspace.name != "DeviceRGB":
                pix = fitz.Pixmap(fitz.csRGB, pix)
            n = pix.n  # bytes per pixel
            samples = pix.samples
            for y in range(0, pix.height, max(1, pix.height // 8)):
                for x in range(0, pix.width, max(1, pix.width // 8)):
                    o = y * pix.stride + x * n
                    counter[(samples[o], samples[o + 1], samples[o + 2])] += 1
        if not counter:
            return (1.0, 1.0, 1.0)
        (r, g, b), _ = counter.most_common(1)[0]
        return (r / 255.0, g / 255.0, b / 255.0)
    except Exception as e:
        logger.debug("bg sample failed: %s", e)
        return (1.0, 1.0, 1.0)


def _try_extract_embedded_font(
    doc: Any,
    page: Any,
    font_name: str,
) -> bytes | None:
    """Pull the byte buffer for an embedded font matching ``font_name``.

    Walks the page's font xrefs, finds the first whose basefont/name contains
    ``font_name`` (case-insensitive), and returns its TTF/CFF bytes via
    ``doc.extract_font``. Returns None if no match or extraction fails (e.g.
    Type 1 / Type 3 fonts that pymupdf can't pull). The caller falls back to
    the bundled ``HTUni`` set when this returns None.

    Caveat: subsetted embedded fonts only contain glyphs already used in the
    document. If the user's new text contains other glyphs, those characters
    will render as tofu. Rendering of the original text is reliable; for
    arbitrary new text the bundled font is the safer choice — callers can
    decide which to prefer.
    """
    if not font_name:
        return None
    needle = font_name.lower().lstrip("+").split("-")[0]  # "Arial-BoldMT" → "arial"
    if not needle or len(needle) < 3:
        return None
    try:
        fonts = page.get_fonts(full=False)
    except Exception:
        return None
    for entry in fonts:
        try:
            xref = entry[0]
            ext = entry[1] or ""
            basefont = (entry[3] or "").lower()
            name = (entry[4] or "").lower()
            if needle not in basefont and needle not in name:
                continue
            if ext.lower() not in ("ttf", "otf", "cff"):
                continue
            data = doc.extract_font(xref)
            # extract_font returns (basefont, ext, type, content)
            content = data[3] if len(data) >= 4 else None
            if isinstance(content, (bytes, bytearray)) and len(content) > 100:
                return bytes(content)
        except Exception as e:
            logger.debug("extract_font(%s) failed: %s", font_name, e)
            continue
    return None


def _fit_fontsize_to_rect(
    text: str,
    *,
    rect: Any,
    requested_fontsize: float,
    font_path: Path | None,
    font_buffer: bytes | None,
    min_fontsize: float = 4.0,
    safety_margin: float = 0.97,
) -> float:
    """Return a fontsize that makes ``text`` fit horizontally inside ``rect``.

    Algorithm:
      1. Measure the text at the requested fontsize.
      2. If it already fits → keep requested (don't grow).
      3. Otherwise scale by ``rect.width / text_width × safety_margin``;
         clamp to ``min_fontsize``.
      4. One verification re-measure (in case the first ratio was off due
         to font metric quirks); shrink one more time if needed.

    Returns the chosen fontsize. Never grows beyond ``requested_fontsize``.
    Never goes below ``min_fontsize`` (text may overflow at that floor —
    accepted; the user is warned via the surrounding caller's error path
    if we ever wanted to escalate).
    """
    import fitz

    if rect.width <= 0 or not text:
        return requested_fontsize

    try:
        if font_buffer:
            font = fitz.Font(fontbuffer=font_buffer)
        elif font_path:
            font = fitz.Font(fontfile=str(font_path))
        else:
            font = fitz.Font("helv")
    except Exception:
        return requested_fontsize

    try:
        width_at_requested = font.text_length(text, fontsize=requested_fontsize)
    except Exception:
        return requested_fontsize

    if width_at_requested <= rect.width:
        return requested_fontsize  # already fits — don't shrink

    # Scale by the ratio (with a safety margin so kerning rounding doesn't
    # bump us back over the limit).
    ratio = rect.width / width_at_requested
    candidate: float = float(max(min_fontsize, requested_fontsize * ratio * safety_margin))

    # One verification pass — if metrics weren't perfectly linear, shrink
    # incrementally until we fit or hit the floor.
    try:
        verify = font.text_length(text, fontsize=candidate)
    except Exception:
        return candidate
    while verify > rect.width and candidate > min_fontsize:
        candidate *= 0.95
        if candidate < min_fontsize:
            candidate = float(min_fontsize)
            break
        try:
            verify = font.text_length(text, fontsize=candidate)
        except Exception:
            break
    return candidate


def _apply_replace_ops_for_page(
    page: Any,
    ops_with_indices: list[tuple[int, dict]],
) -> list[tuple[int, str | None]]:
    """Apply all "replace" ops queued for one page.

    Per-page flow:
      1. For each op, sample the background color around the rect (so the
         redaction blends rather than leaving a white box on coloured
         backgrounds).
      2. Add redaction annotations with those fills.
      3. Call ``page.apply_redactions()`` once for the whole page.
      4. Insert the replacement text — preferring the document's embedded
         font for that span, falling back to our bundled Noto/DejaVu set.

    Returns ``[(op_index, error_or_none), ...]`` so the caller can report
    per-op success / failure into the global summary.
    """
    import fitz

    page_rect = page.rect
    doc = page.parent
    results: list[tuple[int, str | None]] = []
    pending_inserts: list[tuple[int, dict, Any]] = []

    # Phase 1 — sample bg + add redactions
    for idx, op in ops_with_indices:
        try:
            rect = _coerce_rect(op.get("rect"), page_rect)
            bg = _sample_bg_color(page, rect)
            page.add_redact_annot(rect, fill=bg)
            pending_inserts.append((idx, op, rect))
        except ValueError as e:
            results.append((idx, sanitize_error(e)))
        except Exception as e:
            results.append((idx, sanitize_error(e)))

    # Phase 2 — apply once for the whole page
    if pending_inserts:
        try:
            page.apply_redactions()
        except Exception as e:
            for idx, _op, _rect in pending_inserts:
                results.append((idx, f"apply_redactions başarısız: {sanitize_error(e)}"))
            return results

    # Phase 3 — insert replacement text
    for idx, op, rect in pending_inserts:
        try:
            text = str(op.get("text") or "").strip()
            if not text:
                # User wanted to *delete* the original — nothing more to do.
                results.append((idx, None))
                continue
            requested_fontsize = float(op.get("fontsize") or rect.height * 0.85)
            requested_fontsize = max(4.0, min(200.0, requested_fontsize))
            color = _coerce_color(op.get("color"), (0.0, 0.0, 0.0))
            family_id = str(op.get("font_id") or "noto-sans")
            bold = bool(op.get("bold"))
            italic = bool(op.get("italic"))
            original_font = str(op.get("font_name") or "")

            # Try embedded font first (best fidelity), fall back to bundled.
            font_buffer: bytes | None = None
            if original_font:
                font_buffer = _try_extract_embedded_font(doc, page, original_font)
            # Proactive glyph-coverage check: subsetted embedded fonts often
            # only contain the glyphs already used in the document. If our
            # replacement text needs glyphs the embedded font lacks, those
            # would render as tofu — so prefer the bundled font in that case.
            if font_buffer:
                covered, total = font_glyph_coverage(font_buffer, text)
                if total > 0 and covered < total:
                    logger.debug(
                        "embedded font misses %d/%d glyphs — using bundled",
                        total - covered,
                        total,
                    )
                    font_buffer = None
            from core.fonts import resolve_editor_font_with_system as _resolve_w_sys

            font_path = (
                None
                if font_buffer
                else _resolve_w_sys(
                    family_id,
                    bold=bold,
                    italic=italic,
                )
            )

            # Fit-to-rect: if the new text is wider than the original area,
            # shrink the font so it doesn't overflow and disturb surrounding
            # layout. Single-shot ratio calc (cap with 2% safety margin),
            # min 4 pt — below that the text becomes unreadable anyway.
            fontsize = _fit_fontsize_to_rect(
                text,
                rect=rect,
                requested_fontsize=requested_fontsize,
                font_path=font_path,
                font_buffer=font_buffer,
                min_fontsize=4.0,
            )

            baseline_y = rect.y1 - fontsize * 0.15
            kwargs: dict[str, Any] = {"fontsize": fontsize, "color": color}
            try:
                if font_buffer:
                    kwargs["fontname"] = "hf-orig"
                    kwargs["fontbuffer"] = font_buffer
                elif font_path:
                    kwargs["fontname"] = "hf-uni"
                    kwargs["fontfile"] = str(font_path)
                else:
                    kwargs["fontname"] = "helv"
                page.insert_text(fitz.Point(rect.x0, baseline_y), text, **kwargs)
            except Exception:
                # Embedded font might be missing required glyphs (subsetted).
                # Retry once with the bundled fallback.
                if font_buffer:
                    from core.fonts import resolve_editor_font_with_system as _resolve_w_sys_fb

                    fallback = _resolve_w_sys_fb(family_id, bold=bold, italic=italic)
                    kwargs.pop("fontbuffer", None)
                    if fallback:
                        kwargs["fontname"] = "hf-uni"
                        kwargs["fontfile"] = str(fallback)
                    else:
                        kwargs["fontname"] = "helv"
                    page.insert_text(fitz.Point(rect.x0, baseline_y), text, **kwargs)
                else:
                    raise
            results.append((idx, None))
        except Exception as e:
            results.append((idx, sanitize_error(e)))
    return results


def apply_editor_operations(
    input_path: Path,
    output: Path,
    operations: list[dict],
) -> dict[str, Any]:
    """Apply a list of editor operations to a PDF, save the result.

    Returns a summary dict shaped::

        {
            "applied": int,           # ops that succeeded
            "skipped": int,           # ops that raised
            "errors": [               # one entry per skipped op
                {"index": int, "type": str|None, "page": int|None, "error": str}
            ],
        }

    A failing op never aborts the run — the rest still apply. Pages whose
    target page index is out of range are reported as skipped.
    """
    import fitz

    if not isinstance(operations, list):
        raise ValueError("operations bir liste olmalı.")

    applied = 0
    skipped = 0
    errors: list[dict[str, Any]] = []

    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        total_pages = doc.page_count

        # Group "replace" ops by page so we can do one ``apply_redactions``
        # call per page (it's a destructive page-level operation, not per-op).
        replace_by_page: dict[int, list[tuple[int, dict]]] = {}

        for i, op in enumerate(operations):
            if not isinstance(op, dict):
                skipped += 1
                errors.append(
                    {
                        "index": i,
                        "type": None,
                        "page": None,
                        "error": "Operasyon bir nesne olmalı.",
                    }
                )
                continue
            try:
                page_no = int(op.get("page", 0))
            except (TypeError, ValueError):
                page_no = 0
            if page_no < 1 or page_no > total_pages:
                skipped += 1
                errors.append(
                    {
                        "index": i,
                        "type": op.get("type"),
                        "page": page_no,
                        "error": f"Sayfa numarası geçersiz: {page_no} (1-{total_pages}).",
                    }
                )
                continue
            if op.get("type") == "replace":
                replace_by_page.setdefault(page_no, []).append((i, op))
                continue
            try:
                _apply_one_op(doc[page_no - 1], op, i)
                applied += 1
            except ValueError as e:
                skipped += 1
                errors.append(
                    {
                        "index": i,
                        "type": op.get("type"),
                        "page": page_no,
                        "error": sanitize_error(e),
                    }
                )
            except Exception as e:
                skipped += 1
                errors.append(
                    {
                        "index": i,
                        "type": op.get("type"),
                        "page": page_no,
                        "error": sanitize_error(e),
                    }
                )
                logger.debug("editor op #%d unexpected failure: %s", i, e)

        # Now process replace ops, page by page
        for page_no, ops_with_idx in replace_by_page.items():
            page_results = _apply_replace_ops_for_page(doc[page_no - 1], ops_with_idx)
            for op_idx, error_msg in page_results:
                if error_msg is None:
                    applied += 1
                else:
                    skipped += 1
                    src_op = next(
                        (op for i, op in ops_with_idx if i == op_idx),
                        {"type": "replace"},
                    )
                    errors.append(
                        {
                            "index": op_idx,
                            "type": src_op.get("type"),
                            "page": page_no,
                            "error": error_msg,
                        }
                    )

        _save_pdf(doc, output)

    return {"applied": applied, "skipped": skipped, "errors": errors}
