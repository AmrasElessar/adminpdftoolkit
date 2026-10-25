"""PyMuPDF helpers shared by every operation."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

import pymupdf

from .errors import UserError

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

_FONT_CANDIDATES = (
    FONT_DIR / "NotoSans-Regular.ttf",
    FONT_DIR / "DejaVuSans.ttf",
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("/Library/Fonts/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
)


@lru_cache(maxsize=1)
def unicode_font_path() -> str | None:
    """A TTF covering Turkish glyphs, or None (callers fall back to Helvetica)."""
    for c in _FONT_CANDIDATES:
        if c.is_file():
            return str(c)
    return None


def unicode_font() -> pymupdf.Font:
    path = unicode_font_path()
    return pymupdf.Font(fontfile=path) if path else pymupdf.Font("helv")


@contextmanager
def open_pdf(path: Path, password: str = "") -> Iterator[pymupdf.Document]:
    """Open a PDF for modification, authenticating if it is encrypted."""
    try:
        doc = pymupdf.open(path)
    except Exception as e:
        raise UserError("Dosya geçerli bir PDF değil.", "Not a valid PDF.") from e
    try:
        if not doc.is_pdf:
            raise UserError("Dosya geçerli bir PDF değil.", "Not a valid PDF.")
        if doc.needs_pass and not doc.authenticate(password):
            raise UserError(
                "PDF şifreli — doğru şifreyi girin.",
                "The PDF is password-protected — enter the correct password.",
            )
        yield doc
    finally:
        doc.close()


_ALL_PERMS = (
    pymupdf.PDF_PERM_PRINT
    | pymupdf.PDF_PERM_MODIFY
    | pymupdf.PDF_PERM_COPY
    | pymupdf.PDF_PERM_ANNOTATE
    | pymupdf.PDF_PERM_FORM
    | pymupdf.PDF_PERM_ASSEMBLE
    | pymupdf.PDF_PERM_PRINT_HQ
)


def require_owner(doc: pymupdf.Document, password: str) -> None:
    """Changing a document's security needs owner rights when the author
    restricted it — same rule as Acrobat. Unrestricted files pass."""
    if not (doc.metadata or {}).get("encryption"):
        return
    if doc.authenticate(password) & 4:
        return
    if doc.permissions & _ALL_PERMS != _ALL_PERMS:
        raise UserError(
            "Bu PDF'in güvenlik ayarlarını değiştirmek için izin (sahip) şifresi gerekir.",
            "Changing this PDF's security settings requires its permissions (owner) password.",
        )


def save_pdf(doc: pymupdf.Document, output: Path, **extra: Any) -> None:
    """Save compactly. Garbage collection rewrites xrefs, so this is safe for
    every operation that produced orphans (deleted pages, replaced images)."""
    kwargs: dict[str, Any] = {
        "garbage": 4,
        "deflate": True,
        "deflate_images": True,
        "deflate_fonts": True,
        "use_objstms": 1,
    }
    kwargs.update(extra)
    doc.save(output, **kwargs)


def parse_page_spec(spec: str, page_count: int) -> list[int]:
    """Parse ``"1-3,5,8-"`` into 0-based indices, preserving order.

    Accepts ``last`` / ``son`` as an alias for the final page, open ranges
    (``5-`` / ``-3``) and reversed ranges (``5-3``). Raises ``UserError`` on
    anything out of bounds rather than silently clamping.
    """
    spec = (spec or "").strip().lower()
    if not spec or spec in ("all", "tümü", "tumu", "*"):
        return list(range(page_count))
    if len(spec) > 2000:
        raise UserError("Sayfa aralığı çok uzun.", "Page range is too long.")

    def num(tok: str, default: int) -> int:
        tok = tok.strip()
        if not tok:
            return default
        if tok in ("last", "son", "z"):
            return page_count
        if not tok.isdigit():
            raise UserError(f"Geçersiz sayfa: {tok!r}", f"Invalid page: {tok!r}")
        n = int(tok)
        if not 1 <= n <= page_count:
            raise UserError(
                f"Sayfa {n} aralık dışında (1–{page_count}).",
                f"Page {n} is out of range (1–{page_count}).",
            )
        return n

    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a_s, b_s = part.split("-", 1)
            a, b = num(a_s, 1), num(b_s, page_count)
            step = 1 if a <= b else -1
            out.extend(i - 1 for i in range(a, b + step, step))
        else:
            out.append(num(part, 1) - 1)
        if len(out) > 100_000:
            raise UserError("Sayfa aralığı çok büyük.", "Page range is too large.")
    if not out:
        raise UserError("Sayfa aralığı boş.", "Page range is empty.")
    return out
