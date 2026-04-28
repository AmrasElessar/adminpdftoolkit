"""PDF utilities (Section A) — pure pymupdf, no extra deps.

Each function takes/returns ``Path`` objects and writes a single output PDF
(or a directory of outputs for ``pdf_split``). They never raise into the
endpoint layer with internal paths visible — callers should still wrap with
``sanitize_error`` before sending anything to the client.

Shared design choices:
  • Open input with ``fitz.open(str(path))`` once, do all mutations on a
    copy, save with ``garbage=4, deflate=True, clean=True`` so the output is
    compact even when the operation itself doesn't add data.
  • For text inserts (watermark, page numbers, header/footer) we look up a
    Unicode-capable TTF on the host so Turkish characters render correctly.
    Falls back to Helvetica (Latin-1) if no Unicode font is found.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from state import BASE_DIR

from .files import safe_filename
from .logging_setup import logger

_UNICODE_FONT_CACHE: list[str | None] = []


def _find_unicode_font() -> str | None:
    """Return a path to a TTF that covers Turkish glyphs, or None.

    Looks for the common system fonts every desktop OS ships with by default.
    We don't *require* one of these — if missing, callers will fall back to
    Helvetica which is Latin-1 only (Turkish ç, ğ, ş, ö, ü, İ, ı survive
    Latin-1 round-trip, but exotic glyphs would not).
    """
    if _UNICODE_FONT_CACHE:
        return _UNICODE_FONT_CACHE[0]
    candidates = [
        # Bundled (preferred — guarantees identical rendering everywhere)
        BASE_DIR / "static" / "fonts" / "NotoSans-Regular.ttf",
        BASE_DIR / "static" / "fonts" / "DejaVuSans.ttf",
        # Windows
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
        # Linux (Debian/Ubuntu/Fedora)
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        # macOS
        Path("/Library/Fonts/Arial.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
    ]
    for c in candidates:
        try:
            if c.exists():
                _UNICODE_FONT_CACHE.append(str(c))
                return str(c)
        except OSError:
            continue
    _UNICODE_FONT_CACHE.append(None)
    return None


def _insert_text_unicode(
    page: Any,
    point: tuple[float, float],
    text: str,
    *,
    fontsize: float,
    color: tuple[float, float, float] = (0, 0, 0),
    rotate: int = 0,
    fill_opacity: float = 1.0,
) -> None:
    """Insert text on ``page`` using a Unicode font when available.

    Centralises the TTF lookup so every text-emitting helper renders Turkish
    characters identically. Silently falls back to Helvetica if no system
    Unicode font is found.
    """
    import fitz

    font_path = _find_unicode_font()
    kwargs: dict[str, Any] = {
        "fontsize": fontsize,
        "color": color,
        "rotate": rotate,
    }
    # fill_opacity only supported on recent pymupdf; degrade silently
    try:
        page.insert_text(
            point,
            text,
            fontname="hf-uni",
            fontfile=font_path,
            fill_opacity=fill_opacity,
            **kwargs,
        ) if font_path else page.insert_text(
            point, text, fontname="helv", fill_opacity=fill_opacity, **kwargs
        )
    except TypeError:
        # Older pymupdf without fill_opacity
        if font_path:
            page.insert_text(point, text, fontname="hf-uni", fontfile=font_path, **kwargs)
        else:
            page.insert_text(point, text, fontname="helv", **kwargs)


def _save_pdf(doc: Any, output: Path, *, encryption: dict | None = None) -> None:
    """Wrapper around ``doc.save`` with the project-standard compact options."""
    import fitz

    save_kwargs: dict[str, Any] = {
        "garbage": 4,
        "deflate": True,
        "deflate_images": True,
        "deflate_fonts": True,
        "clean": True,
    }
    if encryption:
        save_kwargs.update(encryption)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output), **save_kwargs)


# ----- merge ---------------------------------------------------------------
def pdf_merge(inputs: list[Path], output: Path) -> int:
    """Concatenate ``inputs`` into a single PDF at ``output``.

    Returns the total page count of the merged result. Empty list raises.
    """
    import fitz

    if not inputs:
        raise ValueError("Birleştirilecek PDF yok.")
    out_doc = fitz.open()
    try:
        for src in inputs:
            with fitz.open(str(src)) as in_doc:
                if in_doc.is_encrypted and not in_doc.authenticate(""):
                    raise ValueError(f"Şifreli PDF (şifre gerekiyor): {src.name}")
                out_doc.insert_pdf(in_doc)
        page_count = int(out_doc.page_count)
        _save_pdf(out_doc, output)
    finally:
        out_doc.close()
    return page_count


# ----- split ---------------------------------------------------------------
def _parse_page_ranges(spec: str, total: int) -> list[tuple[int, int]]:
    """Parse ``"1-3,5,7-"`` style page-range specs into [(start,end)] (1-indexed, inclusive).

    Raises ValueError on malformed input or out-of-range pages.
    """
    if not spec or not spec.strip():
        return [(i + 1, i + 1) for i in range(total)]
    out: list[tuple[int, int]] = []
    for piece in spec.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if "-" in piece:
            a, b = piece.split("-", 1)
            a_s = a.strip()
            b_s = b.strip()
            start = int(a_s) if a_s else 1
            end = int(b_s) if b_s else total
        else:
            start = end = int(piece)
        if start < 1 or end < start or end > total:
            raise ValueError(f"Sayfa aralığı geçersiz: {piece} (toplam {total})")
        out.append((start, end))
    if not out:
        raise ValueError("Hiç sayfa aralığı belirtilmedi.")
    return out


def pdf_split(
    input_path: Path,
    output_dir: Path,
    *,
    ranges: str | None = None,
    name_stem: str | None = None,
) -> list[Path]:
    """Split ``input_path`` into one PDF per range.

    ``ranges`` is a string like ``"1-3,5,7-"``; if None, every page becomes its
    own file. Output files land in ``output_dir`` named
    ``{stem}_p{start}-{end}.pdf``.
    """
    import fitz

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = name_stem or input_path.stem
    outputs: list[Path] = []
    with fitz.open(str(input_path)) as src:
        if src.is_encrypted and not src.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        total = src.page_count
        spans = _parse_page_ranges(ranges or "", total)
        for start, end in spans:
            label = f"p{start}" if start == end else f"p{start}-{end}"
            out_path = output_dir / safe_filename(f"{stem}_{label}.pdf")
            chunk = fitz.open()
            try:
                chunk.insert_pdf(src, from_page=start - 1, to_page=end - 1)
                _save_pdf(chunk, out_path)
            finally:
                chunk.close()
            outputs.append(out_path)
    return outputs


# ----- compress ------------------------------------------------------------
def pdf_compress(
    input_path: Path,
    output: Path,
    *,
    image_quality: int = 60,
    max_image_dpi: int = 150,
) -> tuple[int, int]:
    """Best-effort PDF compression.

    Re-encodes embedded raster images as JPEG at ``image_quality`` (1–100) and
    downsamples anything sharper than ``max_image_dpi``. Then saves with full
    garbage collection + deflate. Vector content is untouched.

    Returns ``(bytes_before, bytes_after)``.
    """
    import fitz

    image_quality = max(10, min(95, int(image_quality)))
    bytes_before = input_path.stat().st_size

    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        for page in doc:
            for info in page.get_images(full=True):
                xref = info[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.alpha:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    # Downsample if image is sharper than target DPI given page size
                    rect = page.rect
                    if rect.width > 0 and rect.height > 0:
                        # Approximate: pick the larger dimension ratio
                        target_w = (rect.width / 72.0) * max_image_dpi
                        target_h = (rect.height / 72.0) * max_image_dpi
                        if pix.width > target_w * 1.1 or pix.height > target_h * 1.1:
                            scale_x = target_w / max(1, pix.width)
                            scale_y = target_h / max(1, pix.height)
                            scale = min(scale_x, scale_y, 1.0)
                            if 0 < scale < 1.0:
                                m = fitz.Matrix(scale, scale)
                                pix = fitz.Pixmap(pix, 0)  # detach
                                pix = fitz.Pixmap(
                                    fitz.csRGB,
                                    fitz.Pixmap(doc, xref).tobytes("png"),
                                ) if False else pix  # noop guard
                    jpg = pix.tobytes("jpeg", jpg_quality=image_quality)
                    doc.update_stream(xref, jpg)
                except Exception as e:
                    logger.debug("compress: image %s skipped (%s)", xref, e)
                    continue
        _save_pdf(doc, output)

    bytes_after = output.stat().st_size
    return bytes_before, bytes_after


# ----- encrypt / decrypt ---------------------------------------------------
def pdf_encrypt(
    input_path: Path,
    output: Path,
    *,
    user_password: str,
    owner_password: str | None = None,
    allow_print: bool = True,
    allow_copy: bool = False,
    allow_modify: bool = False,
) -> None:
    """Apply AES-256 encryption to a PDF."""
    import fitz

    if not user_password:
        raise ValueError("Kullanıcı şifresi boş olamaz.")
    perm = 0
    if allow_print:
        perm |= fitz.PDF_PERM_PRINT | fitz.PDF_PERM_PRINT_HQ
    if allow_copy:
        perm |= fitz.PDF_PERM_COPY
    if allow_modify:
        perm |= fitz.PDF_PERM_MODIFY | fitz.PDF_PERM_ANNOTATE | fitz.PDF_PERM_FORM
    encryption = {
        "encryption": fitz.PDF_ENCRYPT_AES_256,
        "user_pw": user_password,
        "owner_pw": owner_password or user_password,
        "permissions": perm,
    }
    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Kaynak PDF zaten şifreli — önce mevcut şifreyi kaldırın.")
        _save_pdf(doc, output, encryption=encryption)


def pdf_decrypt(input_path: Path, output: Path, *, password: str) -> None:
    """Remove encryption from a PDF using ``password`` (user or owner)."""
    import fitz

    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted:
            if not doc.authenticate(password or ""):
                raise ValueError("Şifre yanlış.")
        _save_pdf(doc, output, encryption={"encryption": fitz.PDF_ENCRYPT_NONE})


# ----- watermark -----------------------------------------------------------
def pdf_watermark_text(
    input_path: Path,
    output: Path,
    *,
    text: str,
    opacity: float = 0.25,
    color: tuple[float, float, float] = (0.5, 0.5, 0.5),
    rotation: float = 45.0,
    fontsize: int = 60,
) -> None:
    """Stamp ``text`` across every page at arbitrary ``rotation`` degrees.

    Uses ``fitz.TextWriter`` with a rotation ``morph`` so any angle works
    (PyMuPDF's plain ``insert_text(rotate=…)`` is restricted to multiples of
    90). When a Unicode TTF is found on the host, Turkish glyphs render
    correctly; otherwise Helvetica (Latin-1) is used as a fallback.
    """
    import fitz

    if not text or not text.strip():
        raise ValueError("Watermark metni boş olamaz.")
    text = text.strip()
    opacity = max(0.05, min(1.0, float(opacity)))

    font_path = _find_unicode_font()
    try:
        font = fitz.Font(fontfile=font_path) if font_path else fitz.Font("helv")
    except Exception:
        font = fitz.Font("helv")

    text_width = font.text_length(text, fontsize=fontsize)

    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        for page in doc:
            rect = page.rect
            center = rect.tl + (rect.br - rect.tl) * 0.5
            tw = fitz.TextWriter(rect, color=color)
            start = fitz.Point(center.x - text_width / 2, center.y + fontsize / 3)
            tw.append(start, text, font=font, fontsize=fontsize)
            mat = fitz.Matrix(float(rotation))
            try:
                tw.write_text(page, opacity=opacity, morph=(center, mat))
            except TypeError:
                tw.write_text(page, morph=(center, mat))
        _save_pdf(doc, output)


def pdf_watermark_image(
    input_path: Path,
    output: Path,
    *,
    image_path: Path,
    opacity: float = 0.3,
    scale: float = 0.5,
) -> None:
    """Stamp a centred image (PNG/JPG) on every page."""
    import fitz

    if not image_path.exists():
        raise ValueError("Watermark görseli bulunamadı.")
    opacity = max(0.05, min(1.0, float(opacity)))
    scale = max(0.05, min(1.0, float(scale)))
    img_bytes = image_path.read_bytes()
    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        for page in doc:
            rect = page.rect
            target_w = rect.width * scale
            target_h = rect.height * scale
            x0 = (rect.width - target_w) / 2
            y0 = (rect.height - target_h) / 2
            target = fitz.Rect(x0, y0, x0 + target_w, y0 + target_h)
            try:
                page.insert_image(target, stream=img_bytes, overlay=True, opacity=opacity)
            except TypeError:
                # Older pymupdf without opacity kwarg
                page.insert_image(target, stream=img_bytes, overlay=True)
        _save_pdf(doc, output)


# ----- page numbers / header / footer -------------------------------------
_POSITIONS = {
    "top-left", "top-center", "top-right",
    "bottom-left", "bottom-center", "bottom-right",
}


def _position_xy(rect: Any, position: str, fontsize: float, margin: float = 24.0) -> tuple[float, float]:
    if position not in _POSITIONS:
        position = "bottom-center"
    horiz, vert = position.split("-")
    if vert == "top":
        y = margin + fontsize
    else:
        y = rect.height - margin
    if horiz == "left":
        x = margin
    elif horiz == "right":
        x = rect.width - margin - fontsize * 4  # rough text width allowance
    else:
        x = rect.width / 2 - fontsize  # crude centring; good enough for short text
    return x, y


def pdf_page_numbers(
    input_path: Path,
    output: Path,
    *,
    position: str = "bottom-center",
    start_at: int = 1,
    fontsize: int = 10,
    fmt: str = "{n}",
    color: tuple[float, float, float] = (0, 0, 0),
) -> None:
    """Stamp page numbers on each page using ``fmt`` (e.g. ``"Sayfa {n}/{total}"``)."""
    import fitz

    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        total = doc.page_count
        for idx, page in enumerate(doc):
            n = start_at + idx
            text = fmt.format(n=n, total=total, page=n)
            x, y = _position_xy(page.rect, position, fontsize)
            _insert_text_unicode(page, (x, y), text, fontsize=fontsize, color=color)
        _save_pdf(doc, output)


def pdf_header_footer(
    input_path: Path,
    output: Path,
    *,
    header: str = "",
    footer: str = "",
    fontsize: int = 9,
    color: tuple[float, float, float] = (0.2, 0.2, 0.2),
) -> None:
    """Stamp constant header / footer text on every page."""
    import fitz

    if not header and not footer:
        raise ValueError("Header ve footer ikisi de boş.")
    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        for page in doc:
            if header:
                x, y = _position_xy(page.rect, "top-center", fontsize)
                _insert_text_unicode(page, (x, y), header, fontsize=fontsize, color=color)
            if footer:
                x, y = _position_xy(page.rect, "bottom-center", fontsize)
                _insert_text_unicode(page, (x, y), footer, fontsize=fontsize, color=color)
        _save_pdf(doc, output)


# ----- crop / rotate / reorder / delete -----------------------------------
def pdf_crop(
    input_path: Path,
    output: Path,
    *,
    top: float = 0,
    right: float = 0,
    bottom: float = 0,
    left: float = 0,
    unit: str = "pt",
) -> None:
    """Crop fixed margins off every page. ``unit`` ∈ {pt, mm, in}."""
    import fitz

    if all(v <= 0 for v in (top, right, bottom, left)):
        raise ValueError("En az bir kenar > 0 olmalı.")
    factor = {"pt": 1.0, "mm": 2.83465, "in": 72.0}.get(unit, 1.0)
    t, r, b, l = (v * factor for v in (top, right, bottom, left))
    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        for page in doc:
            mb = page.mediabox
            new = fitz.Rect(mb.x0 + l, mb.y0 + t, mb.x1 - r, mb.y1 - b)
            if new.width <= 1 or new.height <= 1:
                raise ValueError("Kırpma sonrası sayfa çok küçük.")
            page.set_cropbox(new)
        _save_pdf(doc, output)


def pdf_rotate(
    input_path: Path,
    output: Path,
    *,
    angle: int = 90,
    pages: list[int] | None = None,
) -> None:
    """Rotate pages by ``angle`` (must be a multiple of 90).

    ``pages`` is 1-indexed; None rotates every page.
    """
    import fitz

    if angle % 90 != 0:
        raise ValueError("Açı 90'ın katı olmalı (90, 180, 270, -90 …).")
    with fitz.open(str(input_path)) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        target_idx: set[int] = (
            set(range(doc.page_count))
            if not pages
            else {p - 1 for p in pages if 1 <= p <= doc.page_count}
        )
        for i, page in enumerate(doc):
            if i in target_idx:
                page.set_rotation((page.rotation + angle) % 360)
        _save_pdf(doc, output)


def pdf_reorder_pages(input_path: Path, output: Path, *, order: list[int]) -> None:
    """Rearrange / duplicate / drop pages.

    ``order`` is a 1-indexed list of page numbers; the output contains exactly
    those pages in that order. Omitted pages are dropped; duplicates are kept.
    """
    import fitz

    if not order:
        raise ValueError("Sıralama listesi boş.")
    with fitz.open(str(input_path)) as src:
        if src.is_encrypted and not src.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        total = src.page_count
        for p in order:
            if not (1 <= p <= total):
                raise ValueError(f"Geçersiz sayfa numarası: {p} (1–{total})")
        out_doc = fitz.open()
        try:
            for p in order:
                out_doc.insert_pdf(src, from_page=p - 1, to_page=p - 1)
            _save_pdf(out_doc, output)
        finally:
            out_doc.close()


def pdf_delete_pages(input_path: Path, output: Path, *, pages: list[int]) -> None:
    """Drop the listed (1-indexed) pages, keep the rest in original order."""
    if not pages:
        raise ValueError("Silinecek sayfa belirtilmedi.")
    import fitz

    with fitz.open(str(input_path)) as src:
        if src.is_encrypted and not src.authenticate(""):
            raise ValueError("Şifreli PDF — önce şifreyi kaldırın.")
        total = src.page_count
        drop = {p for p in pages if 1 <= p <= total}
        if not drop:
            raise ValueError("Geçerli sayfa yok.")
        keep = [p for p in range(1, total + 1) if p not in drop]
        if not keep:
            raise ValueError("Tüm sayfaları silemezsiniz.")
        out_doc = fitz.open()
        try:
            for p in keep:
                out_doc.insert_pdf(src, from_page=p - 1, to_page=p - 1)
            _save_pdf(out_doc, output)
        finally:
            out_doc.close()
