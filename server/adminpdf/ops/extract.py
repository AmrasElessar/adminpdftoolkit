"""Content extraction: plain text and embedded images."""

from __future__ import annotations

import zipfile

from ..core.errors import UserError
from ..core.pdf import open_pdf, parse_page_spec
from .base import Context, Field, Operation, Params, register

MAX_IMAGES = 5000
MAX_IMAGE_BYTES = 1024 * 1024 * 1024  # total extracted bytes per job
# Already-compressed formats gain nothing from deflate.
_STORED_EXTS = frozenset({"jpg", "jpeg", "jpx", "jp2", "jb2", "jbig2", "png", "webp", "gif"})


# -- PDF → text ------------------------------------------------------------------
class TextParams(Params):
    keep_layout: bool = Field(
        False,
        tr="Satır düzenini koru",
        en="Keep line layout",
        help_tr="Açık: satırlar sayfadaki gibi kalır. Kapalı: paragraflar tek satıra birleştirilir.",
        help_en="On: lines stay as on the page. Off: paragraphs are joined into single lines.",
    )
    page_separators: bool = Field(True, tr="Sayfa ayraçları ekle", en="Add page separators")
    pages: str = Field("", tr="Sayfalar (boş = tümü)", en="Pages (empty = all)", max_length=2000)


def _blocks_text(page: object) -> str:
    paragraphs: list[str] = []
    for block in page.get_text("blocks", sort=True):  # type: ignore[attr-defined]
        if block[6] != 0:  # image block
            continue
        lines = [ln.strip() for ln in str(block[4]).splitlines() if ln.strip()]
        if not lines:
            continue
        text = lines[0]
        for ln in lines[1:]:
            # Re-join words hyphenated across a line break ("bilgi-\nsayar").
            text = text[:-1] + ln if text.endswith("-") and text[-2:-1].isalpha() else f"{text} {ln}"
        paragraphs.append(text)
    return "\n\n".join(paragraphs)


@register
class PdfToText(Operation):
    name = "pdf_to_text"
    category = "extract"
    title_tr, title_en = "PDF'ten Metne", "PDF to Text"
    description_tr = "PDF'teki metni UTF-8 düz metin (.txt) dosyasına aktarır."
    description_en = "Export the text of a PDF to a UTF-8 plain-text (.txt) file."
    Params = TextParams

    def run(self, ctx: Context, params: TextParams) -> None:
        inp = ctx.inputs[0]
        found = False
        out = ctx.output(f"{inp.stem}.txt")
        with open_pdf(inp.path, inp.password) as doc, out.open("w", encoding="utf-8", newline="\n") as fh:
            targets = parse_page_spec(params.pages, doc.page_count)
            for k, i in enumerate(targets):
                page = doc[i]
                if params.keep_layout:
                    text = "\n".join(ln.rstrip() for ln in page.get_text("text", sort=True).splitlines())
                else:
                    text = _blocks_text(page)
                text = text.replace("\x00", "").strip("\n")
                found = found or bool(text.strip())
                if params.page_separators:
                    fh.write(f"{'' if k == 0 else chr(10)}===== Sayfa {i + 1} / Page {i + 1} =====\n\n")
                elif k:
                    fh.write("\n\n")
                fh.write(text + "\n")
                ctx.progress((k + 1) / len(targets), "")
        if not found:
            raise UserError(
                "PDF'te metin bulunamadı. Taranmış bir belgeyse önce OCR uygulayın.",
                "No text found. If the document is scanned, run OCR first.",
            )


# -- embedded images ----------------------------------------------------------------
class ImagesParams(Params):
    min_size: int = Field(
        32,
        tr="En küçük boyut (piksel)",
        en="Minimum size (pixels)",
        help_tr="Genişliği veya yüksekliği bundan küçük görseller (simgeler, çizgiler) atlanır.",
        help_en="Images narrower or shorter than this (icons, rules) are skipped.",
        ge=1,
        le=10_000,
    )
    pages: str = Field("", tr="Sayfalar (boş = tümü)", en="Pages (empty = all)", max_length=2000)


@register
class ExtractImages(Operation):
    name = "extract_images"
    category = "extract"
    title_tr, title_en = "Görselleri Çıkar", "Extract Images"
    description_tr = "PDF'e gömülü tüm görselleri özgün biçimleriyle ZIP olarak dışa aktarır."
    description_en = "Export every embedded image in its original format, as a ZIP."
    Params = ImagesParams

    def run(self, ctx: Context, params: ImagesParams) -> None:
        inp = ctx.inputs[0]
        seen: set[int] = set()
        written = small = duplicates = failed = 0
        total_bytes = 0
        truncated = False
        formats: dict[str, int] = {}
        zip_path = ctx.output(f"{inp.stem}_gorseller.zip")
        with open_pdf(inp.path, inp.password) as doc, zipfile.ZipFile(zip_path, "w") as zf:
            targets = parse_page_spec(params.pages, doc.page_count)
            for k, i in enumerate(targets):
                if truncated:
                    break
                for n, img in enumerate(doc[i].get_images(full=True), start=1):
                    xref, width, height = int(img[0]), int(img[2]), int(img[3])
                    if xref <= 0:
                        continue
                    if xref in seen:
                        duplicates += 1
                        continue
                    seen.add(xref)
                    if width < params.min_size or height < params.min_size:
                        small += 1
                        continue
                    try:
                        info = doc.extract_image(xref)
                    except Exception:
                        info = None
                    if not info or not info.get("image"):
                        failed += 1
                        continue
                    data: bytes = info["image"]
                    ext = str(info.get("ext") or "bin").lower()
                    if written >= MAX_IMAGES or total_bytes + len(data) > MAX_IMAGE_BYTES:
                        truncated = True
                        break
                    compress = zipfile.ZIP_STORED if ext in _STORED_EXTS else zipfile.ZIP_DEFLATED
                    zf.writestr(f"sayfa{i + 1:04d}_{n:03d}.{ext}", data, compress_type=compress)
                    written += 1
                    total_bytes += len(data)
                    formats[ext] = formats.get(ext, 0) + 1
                ctx.progress((k + 1) / len(targets), "")
        if not written:
            raise UserError(
                "Çıkarılacak görsel bulunamadı (küçük görseller atlandı)."
                if small
                else "PDF'te gömülü görsel bulunamadı.",
                "No images to extract (small images were skipped)." if small else "The PDF has no embedded images.",
            )
        ctx.data = {
            "images": written,
            "formats": formats,
            "skipped_small": small,
            "duplicates": duplicates,
            "unreadable": failed,
            "truncated": truncated,
            "limit": MAX_IMAGES,
        }
