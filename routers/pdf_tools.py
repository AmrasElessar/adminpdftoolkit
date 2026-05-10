"""PDF Tools router — every endpoint under ``/pdf/*`` that produces a
single PDF or asset (no editor, no convert/OCR pipelines).

Includes:
  - merge / split / compress / encrypt / decrypt
  - watermark-text / watermark-image
  - page-numbers / header-footer
  - crop / rotate / reorder / delete-pages
  - from-images / to-markdown / to-csv / from-docx / from-xlsx / from-html / from-url
  - find / outline / metadata / set-metadata / extract-images / thumbnail
  - deep-analyze / extractability
  - detect-blank / remove-blank / detect-signatures / classify
  - batch dispatcher (``/pdf/batch``)

Lazy attribute lookup on ``core.X`` (rather than ``from core import X``)
keeps pytest monkeypatches working — e.g. ``monkeypatch.setattr(core,
"_assert_public_url", ...)`` for the URL→PDF SSRF tests.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

import core
from app_http import (
    cleanup_task,
    file_response_with_name,
    gate_pdf_safety,
    parse_color,
    parse_int_list,
    pdf_job_dir,
    pdf_response,
    save_pdf_upload,
)
from core import logger, sanitize_error

router = APIRouter()

_IMAGE_EXT_RE = re.compile(r"\.(jpg|jpeg|png|webp|bmp|tiff?|gif)$", re.IGNORECASE)


# ----- merge ---------------------------------------------------------------
@router.post("/pdf/merge", response_model=None)
async def pdf_merge_endpoint(
    request: Request,
    files: list[UploadFile] = File(...),
    output_name: str = Form("merged"),
):
    if len(files) < 2:
        raise HTTPException(400, "Birleştirmek için en az 2 PDF gerekli.")
    job_dir = pdf_job_dir()
    try:
        inputs: list[Path] = []
        for i, f in enumerate(files):
            dest = job_dir / f"in_{i:03d}.pdf"
            await save_pdf_upload(f, dest)
            inputs.append(dest)
        out = job_dir / "merged.pdf"
        page_count = core.pdf_merge(inputs, out)
        core.log_history(
            action="pdf-merge",
            filename=output_name,
            record_count=page_count,
            ip=core.client_ip(request),
        )
        return pdf_response(out, output_name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/merge failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


# ----- split ---------------------------------------------------------------
@router.post("/pdf/split", response_model=None)
async def pdf_split_endpoint(
    request: Request,
    file: UploadFile = File(...),
    ranges: str = Form(""),
):
    """Split into ZIP. ``ranges`` example: ``"1-3,5,7-"``; empty = per-page."""
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "split").stem
        out_dir = job_dir / "out"
        outs = core.pdf_split(in_path, out_dir, ranges=ranges or None, name_stem=stem)
        if not outs:
            raise HTTPException(400, "Hiç parça üretilemedi.")
        zip_path = job_dir / f"{stem}_split.zip"
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for p in outs:
                zf.write(str(p), arcname=p.name)
        core.log_history(
            action="pdf-split",
            filename=zip_path.name,
            record_count=len(outs),
            ip=core.client_ip(request),
        )
        zip_name = f"{stem}_split.zip"
        ascii_fallback = zip_name.encode("ascii", "ignore").decode("ascii") or "split.zip"
        cd = f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(zip_name)}"
        return FileResponse(
            str(zip_path),
            media_type="application/zip",
            headers={"Content-Disposition": cd},
            background=cleanup_task(job_dir),
        )
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/split failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


# ----- compress ------------------------------------------------------------
@router.post("/pdf/compress", response_model=None)
async def pdf_compress_endpoint(
    request: Request,
    file: UploadFile = File(...),
    image_quality: int = Form(60),
    max_image_dpi: int = Form(150),
    output_name: str = Form(""),
):
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "compressed").stem
        out_path = job_dir / f"{stem}_compressed.pdf"
        before, after = core.pdf_compress(
            in_path,
            out_path,
            image_quality=image_quality,
            max_image_dpi=max_image_dpi,
        )
        core.log_history(
            action="pdf-compress",
            filename=out_path.name,
            note=f"{before}→{after} bytes",
            ip=core.client_ip(request),
        )
        download_name = output_name or f"{stem}_compressed.pdf"
        resp = pdf_response(out_path, download_name, job_dir)
        resp.headers["X-Bytes-Before"] = str(before)
        resp.headers["X-Bytes-After"] = str(after)
        return resp
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/compress failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


# ----- encrypt -------------------------------------------------------------
@router.post("/pdf/encrypt", response_model=None)
async def pdf_encrypt_endpoint(
    request: Request,
    file: UploadFile = File(...),
    user_password: str = Form(...),
    owner_password: str = Form(""),
    allow_print: bool = Form(True),
    allow_copy: bool = Form(False),
    allow_modify: bool = Form(False),
    output_name: str = Form(""),
):
    if not user_password:
        raise HTTPException(400, "Kullanıcı şifresi boş olamaz.")
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "encrypted").stem
        out_path = job_dir / f"{stem}_protected.pdf"
        core.pdf_encrypt(
            in_path,
            out_path,
            user_password=user_password,
            owner_password=owner_password or None,
            allow_print=allow_print,
            allow_copy=allow_copy,
            allow_modify=allow_modify,
        )
        core.log_history(
            action="pdf-encrypt",
            filename=out_path.name,
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/encrypt failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


# ----- decrypt -------------------------------------------------------------
@router.post("/pdf/decrypt", response_model=None)
async def pdf_decrypt_endpoint(
    request: Request,
    file: UploadFile = File(...),
    password: str = Form(...),
    output_name: str = Form(""),
):
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "decrypted").stem
        out_path = job_dir / f"{stem}_unlocked.pdf"
        core.pdf_decrypt(in_path, out_path, password=password)
        core.log_history(
            action="pdf-decrypt",
            filename=out_path.name,
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/decrypt failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


# ----- watermark text/image -----------------------------------------------
@router.post("/pdf/watermark-text", response_model=None)
async def pdf_watermark_text_endpoint(
    request: Request,
    file: UploadFile = File(...),
    text: str = Form(...),
    opacity: float = Form(0.25),
    color: str = Form("#808080"),
    rotation: int = Form(45),
    fontsize: int = Form(60),
    output_name: str = Form(""),
):
    if not text.strip():
        raise HTTPException(400, "Watermark metni boş olamaz.")
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "watermarked").stem
        out_path = job_dir / f"{stem}_watermarked.pdf"
        core.pdf_watermark_text(
            in_path,
            out_path,
            text=text,
            opacity=opacity,
            color=parse_color(color, (0.5, 0.5, 0.5)),
            rotation=rotation,
            fontsize=fontsize,
        )
        core.log_history(
            action="pdf-watermark-text",
            filename=out_path.name,
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/watermark-text failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/watermark-image", response_model=None)
async def pdf_watermark_image_endpoint(
    request: Request,
    file: UploadFile = File(...),
    image: UploadFile = File(...),
    opacity: float = Form(0.3),
    scale: float = Form(0.5),
    output_name: str = Form(""),
):
    if not image.filename or not image.filename.lower().endswith(
        (".png", ".jpg", ".jpeg", ".webp")
    ):
        raise HTTPException(400, "Watermark görseli .png/.jpg/.jpeg/.webp olmalı.")
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        img_path = job_dir / f"watermark{Path(image.filename).suffix.lower()}"
        await core.save_upload(image, img_path)
        stem = Path(file.filename or "watermarked").stem
        out_path = job_dir / f"{stem}_stamped.pdf"
        core.pdf_watermark_image(
            in_path,
            out_path,
            image_path=img_path,
            opacity=opacity,
            scale=scale,
        )
        core.log_history(
            action="pdf-watermark-image",
            filename=out_path.name,
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/watermark-image failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


# ----- page numbers / header-footer ---------------------------------------
@router.post("/pdf/page-numbers", response_model=None)
async def pdf_page_numbers_endpoint(
    request: Request,
    file: UploadFile = File(...),
    position: str = Form("bottom-center"),
    start_at: int = Form(1),
    fontsize: int = Form(10),
    fmt: str = Form("{n} / {total}"),
    color: str = Form("#000000"),
    output_name: str = Form(""),
):
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "numbered").stem
        out_path = job_dir / f"{stem}_numbered.pdf"
        core.pdf_page_numbers(
            in_path,
            out_path,
            position=position,
            start_at=start_at,
            fontsize=fontsize,
            fmt=fmt,
            color=parse_color(color, (0, 0, 0)),
        )
        core.log_history(
            action="pdf-page-numbers",
            filename=out_path.name,
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/page-numbers failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/header-footer", response_model=None)
async def pdf_header_footer_endpoint(
    request: Request,
    file: UploadFile = File(...),
    header: str = Form(""),
    footer: str = Form(""),
    fontsize: int = Form(9),
    color: str = Form("#333333"),
    output_name: str = Form(""),
):
    if not header.strip() and not footer.strip():
        raise HTTPException(400, "Header ve footer ikisi de boş.")
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "stamped").stem
        out_path = job_dir / f"{stem}_stamped.pdf"
        core.pdf_header_footer(
            in_path,
            out_path,
            header=header,
            footer=footer,
            fontsize=fontsize,
            color=parse_color(color, (0.2, 0.2, 0.2)),
        )
        core.log_history(
            action="pdf-header-footer",
            filename=out_path.name,
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/header-footer failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


# ----- crop / rotate / reorder / delete -----------------------------------
@router.post("/pdf/crop", response_model=None)
async def pdf_crop_endpoint(
    request: Request,
    file: UploadFile = File(...),
    top: float = Form(0),
    right: float = Form(0),
    bottom: float = Form(0),
    left: float = Form(0),
    unit: str = Form("pt"),
    output_name: str = Form(""),
):
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "cropped").stem
        out_path = job_dir / f"{stem}_cropped.pdf"
        core.pdf_crop(
            in_path,
            out_path,
            top=top,
            right=right,
            bottom=bottom,
            left=left,
            unit=unit,
        )
        core.log_history(
            action="pdf-crop",
            filename=out_path.name,
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/crop failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/rotate", response_model=None)
async def pdf_rotate_endpoint(
    request: Request,
    file: UploadFile = File(...),
    angle: int = Form(90),
    pages: str = Form(""),
    output_name: str = Form(""),
):
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "rotated").stem
        out_path = job_dir / f"{stem}_rotated.pdf"
        page_list = parse_int_list(pages) if pages.strip() else None
        core.pdf_rotate(in_path, out_path, angle=angle, pages=page_list)
        core.log_history(
            action="pdf-rotate",
            filename=out_path.name,
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/rotate failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/reorder", response_model=None)
async def pdf_reorder_endpoint(
    request: Request,
    file: UploadFile = File(...),
    order: str = Form(...),
    output_name: str = Form(""),
):
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "reordered").stem
        out_path = job_dir / f"{stem}_reordered.pdf"
        order_list = parse_int_list(order)
        if not order_list:
            raise HTTPException(400, "Sıralama listesi boş.")
        core.pdf_reorder_pages(in_path, out_path, order=order_list)
        core.log_history(
            action="pdf-reorder",
            filename=out_path.name,
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/reorder failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/delete-pages", response_model=None)
async def pdf_delete_pages_endpoint(
    request: Request,
    file: UploadFile = File(...),
    pages: str = Form(...),
    output_name: str = Form(""),
):
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "trimmed").stem
        out_path = job_dir / f"{stem}_trimmed.pdf"
        page_list = parse_int_list(pages)
        if not page_list:
            raise HTTPException(400, "Silinecek sayfa belirtilmedi.")
        core.pdf_delete_pages(in_path, out_path, pages=page_list)
        core.log_history(
            action="pdf-delete-pages",
            filename=out_path.name,
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/delete-pages failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


# ----- conversions: image / md / csv / docx / xlsx / html / url ----------
@router.post("/pdf/from-images", response_model=None)
async def pdf_from_images_endpoint(
    request: Request,
    files: list[UploadFile] = File(...),
    output_name: str = Form("images"),
):
    if not files:
        raise HTTPException(400, "En az bir görsel gerekli.")
    from state import MAX_UPLOAD_MB

    job_dir = pdf_job_dir()
    try:
        inputs: list[Path] = []
        for i, f in enumerate(files):
            if not f.filename or not _IMAGE_EXT_RE.search(f.filename):
                raise HTTPException(
                    400,
                    f"Desteklenmeyen format: {f.filename or '?'} (jpg/png/webp/bmp/tif/gif beklenir).",
                )
            dest = job_dir / f"img_{i:03d}{Path(f.filename).suffix.lower()}"
            written = 0
            with dest.open("wb") as fp:
                while chunk := await f.read(1024 * 1024):
                    written += len(chunk)
                    if written > MAX_UPLOAD_MB * 1024 * 1024:
                        raise HTTPException(413, f"Görsel {MAX_UPLOAD_MB} MB sınırını aşıyor.")
                    fp.write(chunk)
            inputs.append(dest)
        out = job_dir / f"{core.safe_filename(output_name) or 'images'}.pdf"
        page_count = core.image_to_pdf(inputs, out)
        core.log_history(
            action="pdf-from-images",
            filename=out.name,
            record_count=page_count,
            ip=core.client_ip(request),
        )
        return pdf_response(out, output_name or out.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/from-images failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/to-markdown", response_model=None)
async def pdf_to_markdown_endpoint(
    request: Request,
    file: UploadFile = File(...),
    output_name: str = Form(""),
):
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "doc").stem
        download = output_name or f"{stem}.md"
        if not download.lower().endswith(".md"):
            download += ".md"
        out_path = job_dir / core.safe_filename(download)
        page_count = core.pdf_to_markdown(in_path, out_path)
        core.log_history(
            action="pdf-to-markdown",
            filename=out_path.name,
            record_count=page_count,
            ip=core.client_ip(request),
        )
        return file_response_with_name(out_path, download, "text/markdown", job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/to-markdown failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/to-csv", response_model=None)
async def pdf_to_csv_endpoint(
    request: Request,
    file: UploadFile = File(...),
    table_index: int = Form(0),
    delimiter: str = Form(","),
    output_name: str = Form(""),
):
    if delimiter not in (",", ";", "\t", "|"):
        raise HTTPException(400, "Sınırlayıcı yalnızca , ; \\t veya | olabilir.")
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "tables").stem
        download = output_name or f"{stem}.csv"
        if not download.lower().endswith(".csv"):
            download += ".csv"
        out_path = job_dir / core.safe_filename(download)
        rows = core.pdf_to_csv(
            in_path,
            out_path,
            table_index=(table_index or None),
            delimiter=delimiter,
        )
        core.log_history(
            action="pdf-to-csv",
            filename=out_path.name,
            record_count=rows,
            ip=core.client_ip(request),
        )
        return file_response_with_name(out_path, download, "text/csv", job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/to-csv failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/from-docx", response_model=None)
async def pdf_from_docx_endpoint(
    request: Request,
    file: UploadFile = File(...),
    output_name: str = Form(""),
):
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "Yalnızca .docx (modern Word) kabul edilir — .doc desteklenmez.")
    from state import MAX_UPLOAD_MB

    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.docx"
        written = 0
        with in_path.open("wb") as fp:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(413, f"Dosya {MAX_UPLOAD_MB} MB sınırını aşıyor.")
                fp.write(chunk)
        stem = Path(file.filename).stem
        out_path = job_dir / f"{stem}.pdf"
        core.docx_to_pdf(in_path, out_path)
        core.log_history(
            action="pdf-from-docx",
            filename=out_path.name,
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/from-docx failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/from-xlsx", response_model=None)
async def pdf_from_xlsx_endpoint(
    request: Request,
    file: UploadFile = File(...),
    sheet: str = Form(""),
    output_name: str = Form(""),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Yalnızca .xlsx (modern Excel) kabul edilir — .xls desteklenmez.")
    from state import MAX_UPLOAD_MB

    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.xlsx"
        written = 0
        with in_path.open("wb") as fp:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(413, f"Dosya {MAX_UPLOAD_MB} MB sınırını aşıyor.")
                fp.write(chunk)
        stem = Path(file.filename).stem
        out_path = job_dir / f"{stem}.pdf"
        core.xlsx_to_pdf(in_path, out_path, sheet=(sheet.strip() or None))
        core.log_history(
            action="pdf-from-xlsx",
            filename=out_path.name,
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/from-xlsx failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


_FROM_HTML_MAX_BYTES = 10 * 1024 * 1024


@router.post("/pdf/from-html", response_model=None)
async def pdf_from_html_endpoint(
    request: Request,
    html: str = Form(""),
    output_name: str = Form("document"),
):
    if not html.strip():
        raise HTTPException(400, "HTML içeriği boş.")

    if len(html.encode("utf-8")) > _FROM_HTML_MAX_BYTES:
        raise HTTPException(
            413,
            f"HTML içeriği {_FROM_HTML_MAX_BYTES // (1024 * 1024)} MB sınırını aşıyor.",
        )
    job_dir = pdf_job_dir()
    try:
        out_path = job_dir / f"{core.safe_filename(output_name) or 'document'}.pdf"
        core.html_to_pdf(html, out_path)
        core.log_history(
            action="pdf-from-html",
            filename=out_path.name,
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/from-html failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/from-url", response_model=None)
async def pdf_from_url_endpoint(
    request: Request,
    url: str = Form(...),
    output_name: str = Form(""),
):
    job_dir = pdf_job_dir()
    try:
        stem = output_name or "page"
        out_path = job_dir / f"{core.safe_filename(stem) or 'page'}.pdf"
        core.url_to_pdf(url, out_path)
        core.log_history(
            action="pdf-from-url",
            filename=out_path.name,
            note=url[:200],
            ip=core.client_ip(request),
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/from-url failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


# ----- intelligence: find / outline / metadata / images / thumb / deep ---
@router.post("/pdf/find")
async def pdf_find_endpoint(
    request: Request,
    file: UploadFile = File(...),
    query: str = Form(...),
    case_sensitive: bool = Form(False),
    whole_words: bool = Form(False),
    max_pages: int = Form(0),
    max_results: int = Form(500),
) -> dict:
    if not query.strip():
        raise HTTPException(400, "Aranacak metin boş olamaz.")
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        results = core.find_text(
            in_path,
            query,
            case_sensitive=case_sensitive,
            whole_words=whole_words,
            max_pages=(None if max_pages <= 0 else max_pages),
            max_results=max(1, min(5000, max_results)),
        )
        core.log_history(
            action="pdf-find",
            filename=file.filename or "?",
            record_count=len(results),
            note=query[:80],
            ip=core.client_ip(request),
        )
        return {"query": query, "count": len(results), "matches": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/pdf/find failed")
        raise HTTPException(400, sanitize_error(e)) from e
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


@router.post("/pdf/outline")
async def pdf_outline_endpoint(
    request: Request,
    file: UploadFile = File(...),
) -> dict:
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        outline = core.extract_outline(in_path)
        return {"count": len(outline), "outline": outline}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/pdf/outline failed")
        raise HTTPException(400, sanitize_error(e)) from e
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


@router.post("/pdf/metadata")
async def pdf_get_metadata_endpoint(
    request: Request,
    file: UploadFile = File(...),
) -> dict:
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        return core.extract_metadata(in_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/pdf/metadata failed")
        raise HTTPException(400, sanitize_error(e)) from e
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


@router.post("/pdf/set-metadata", response_model=None)
async def pdf_set_metadata_endpoint(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    author: str = Form(""),
    subject: str = Form(""),
    keywords: str = Form(""),
    output_name: str = Form(""),
):
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "doc").stem
        out_path = job_dir / f"{stem}_meta.pdf"
        core.set_metadata(
            in_path,
            out_path,
            title=title or None,
            author=author or None,
            subject=subject or None,
            keywords=keywords or None,
        )
        core.log_history(
            action="pdf-set-metadata", filename=out_path.name, ip=core.client_ip(request)
        )
        return pdf_response(out_path, output_name or out_path.name, job_dir)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/set-metadata failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/extract-images", response_model=None)
async def pdf_extract_images_endpoint(
    request: Request,
    file: UploadFile = File(...),
    min_size: int = Form(32),
    page: int = Form(0),
):
    """Return a ZIP of every embedded image (>= ``min_size`` × ``min_size``)."""
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        out_dir = job_dir / "images"
        page_arg: int | None = None if page <= 0 else page
        images = core.extract_images(
            in_path,
            out_dir,
            min_size=max(1, min_size),
            page=page_arg,
        )
        if not images:
            raise HTTPException(400, "Görsel bulunamadı (veya hepsi minimum boyut altında).")
        stem = Path(file.filename or "images").stem
        zip_path = job_dir / f"{stem}_images.zip"
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for img in images:
                src = out_dir / img["filename"]
                if src.is_file():
                    zf.write(str(src), arcname=img["filename"])
        core.log_history(
            action="pdf-extract-images",
            filename=zip_path.name,
            record_count=len(images),
            ip=core.client_ip(request),
        )
        zip_name = f"{stem}_images.zip"
        ascii_fallback = zip_name.encode("ascii", "ignore").decode("ascii") or "images.zip"
        cd = f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(zip_name)}"
        resp = FileResponse(
            str(zip_path),
            media_type="application/zip",
            headers={"Content-Disposition": cd},
            background=cleanup_task(job_dir),
        )
        resp.headers["X-Image-Count"] = str(len(images))
        return resp
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/extract-images failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/thumbnail", response_model=None)
async def pdf_thumbnail_endpoint(
    request: Request,
    file: UploadFile = File(...),
    page_no: int = Form(1),
    dpi: int = Form(100),
    fmt: str = Form("png"),
):
    if dpi < 30 or dpi > 300:
        raise HTTPException(400, "DPI 30-300 arasında olmalı.")
    if fmt not in ("png", "jpg", "jpeg"):
        raise HTTPException(400, "Format png veya jpg olmalı.")
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        out_path = job_dir / f"thumb.{fmt}"
        w, h = core.pdf_thumbnail(in_path, out_path, page_no=page_no, dpi=dpi, fmt=fmt)
        media = "image/png" if fmt == "png" else "image/jpeg"
        return FileResponse(
            str(out_path),
            media_type=media,
            headers={
                "Content-Disposition": f'inline; filename="thumb.{fmt}"',
                "X-Width": str(w),
                "X-Height": str(h),
            },
            background=cleanup_task(job_dir),
        )
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/thumbnail failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/deep-analyze")
async def pdf_deep_analyze_endpoint(
    request: Request,
    file: UploadFile = File(...),
) -> dict:
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        return core.deep_analyze(in_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/pdf/deep-analyze failed")
        raise HTTPException(400, sanitize_error(e)) from e
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


@router.post("/pdf/extractability")
async def pdf_extractability_endpoint(
    request: Request,
    file: UploadFile = File(...),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Yalnızca PDF dosyaları kabul edilir.")
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        return core.classify_pdf_extractability(in_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/pdf/extractability failed")
        raise HTTPException(400, sanitize_error(e)) from e
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


# ----- detect-blank / remove-blank / detect-signatures / classify --------
@router.post("/pdf/detect-blank")
async def pdf_detect_blank_endpoint(
    request: Request,
    file: UploadFile = File(...),
    threshold: float = Form(0.995),
    dpi: int = Form(50),
) -> dict:
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        blanks = core.detect_blank_pages(in_path, threshold=threshold, dpi=dpi)
        with __import__("fitz").open(str(in_path)) as doc:
            total = doc.page_count
        core.log_history(
            action="pdf-detect-blank",
            filename=file.filename or "?",
            record_count=len(blanks),
            ip=core.client_ip(request),
        )
        return {
            "total_pages": total,
            "blank_pages": blanks,
            "blank_count": len(blanks),
            "threshold": threshold,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/pdf/detect-blank failed")
        raise HTTPException(400, sanitize_error(e)) from e
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


@router.post("/pdf/remove-blank", response_model=None)
async def pdf_remove_blank_endpoint(
    request: Request,
    file: UploadFile = File(...),
    threshold: float = Form(0.995),
    dpi: int = Form(50),
    output_name: str = Form(""),
):
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        stem = Path(file.filename or "doc").stem
        out_path = job_dir / f"{stem}_no-blank.pdf"
        kept, removed = core.remove_blank_pages(
            in_path,
            out_path,
            threshold=threshold,
            dpi=dpi,
        )
        core.log_history(
            action="pdf-remove-blank",
            filename=out_path.name,
            record_count=removed,
            ip=core.client_ip(request),
        )
        resp = pdf_response(out_path, output_name or out_path.name, job_dir)
        resp.headers["X-Pages-Kept"] = str(kept)
        resp.headers["X-Pages-Removed"] = str(removed)
        return resp
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/remove-blank failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e


@router.post("/pdf/detect-signatures")
async def pdf_detect_signatures_endpoint(
    request: Request,
    file: UploadFile = File(...),
) -> dict:
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        result = core.detect_signatures(in_path)
        core.log_history(
            action="pdf-detect-signatures",
            filename=file.filename or "?",
            record_count=result.get("field_count", 0),
            ip=core.client_ip(request),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/pdf/detect-signatures failed")
        raise HTTPException(400, sanitize_error(e)) from e
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


@router.post("/pdf/classify")
async def pdf_classify_endpoint(
    request: Request,
    file: UploadFile = File(...),
    max_pages: int = Form(5),
) -> dict:
    if max_pages < 1 or max_pages > 50:
        raise HTTPException(400, "max_pages 1-50 arasında olmalı.")
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        result = core.classify_pdf(in_path, max_pages=max_pages)
        core.log_history(
            action="pdf-classify",
            filename=file.filename or "?",
            note=result.get("category", ""),
            ip=core.client_ip(request),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/pdf/classify failed")
        raise HTTPException(400, sanitize_error(e)) from e
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


# ===========================================================================
# Batch dispatcher — Hero'da birden fazla PDF olduğunda tek tool'u her dosyaya
# uygulamak için. Tek çıktı varsa direkt dosya, çoklu çıktıda ZIP döner.
# ===========================================================================


def _b_get(params: dict, key: str, default: str = "") -> str:
    v = params.get(key, default)
    if v is None:
        return default
    return str(v)


def _b_int(params: dict, key: str, default: int) -> int:
    try:
        v = params.get(key)
        if v is None or v == "":
            return default
        return int(v)  # type: ignore[arg-type]  # form values are str/int-coercible
    except (TypeError, ValueError):
        return default


def _b_float(params: dict, key: str, default: float) -> float:
    try:
        v = params.get(key)
        if v is None or v == "":
            return default
        return float(v)  # type: ignore[arg-type]  # form values are str/float-coercible
    except (TypeError, ValueError):
        return default


def _bh_compress(
    in_path: Path, out_dir: Path, original: str, params: dict
) -> tuple[Path, str, str]:
    stem = Path(original).stem or "compressed"
    out = out_dir / f"{stem}_compressed.pdf"
    core.pdf_compress(
        in_path,
        out,
        image_quality=_b_int(params, "image_quality", 60),
        max_image_dpi=_b_int(params, "max_image_dpi", 150),
    )
    return out, out.name, "application/pdf"


def _bh_encrypt(in_path: Path, out_dir: Path, original: str, params: dict) -> tuple[Path, str, str]:
    stem = Path(original).stem or "encrypted"
    out = out_dir / f"{stem}_protected.pdf"
    user_pw = _b_get(params, "user_password")
    if not user_pw:
        raise HTTPException(400, "Kullanıcı şifresi boş olamaz.")
    core.pdf_encrypt(
        in_path,
        out,
        user_password=user_pw,
        owner_password=_b_get(params, "owner_password") or None,
        allow_print=_b_get(params, "allow_print", "true").lower() == "true",
        allow_copy=_b_get(params, "allow_copy", "false").lower() == "true",
        allow_modify=_b_get(params, "allow_modify", "false").lower() == "true",
    )
    return out, out.name, "application/pdf"


def _bh_decrypt(in_path: Path, out_dir: Path, original: str, params: dict) -> tuple[Path, str, str]:
    stem = Path(original).stem or "decrypted"
    out = out_dir / f"{stem}_unlocked.pdf"
    core.pdf_decrypt(in_path, out, password=_b_get(params, "password"))
    return out, out.name, "application/pdf"


def _bh_watermark_text(
    in_path: Path, out_dir: Path, original: str, params: dict
) -> tuple[Path, str, str]:
    stem = Path(original).stem or "watermarked"
    out = out_dir / f"{stem}_watermarked.pdf"
    text = _b_get(params, "text").strip()
    if not text:
        raise HTTPException(400, "Watermark metni boş olamaz.")
    core.pdf_watermark_text(
        in_path,
        out,
        text=text,
        opacity=_b_float(params, "opacity", 0.25),
        color=parse_color(_b_get(params, "color", "#808080"), (0.5, 0.5, 0.5)),
        rotation=_b_int(params, "rotation", 45),
        fontsize=_b_int(params, "fontsize", 60),
    )
    return out, out.name, "application/pdf"


def _bh_page_numbers(
    in_path: Path, out_dir: Path, original: str, params: dict
) -> tuple[Path, str, str]:
    stem = Path(original).stem or "numbered"
    out = out_dir / f"{stem}_numbered.pdf"
    core.pdf_page_numbers(
        in_path,
        out,
        position=_b_get(params, "position", "bottom-center"),
        start_at=_b_int(params, "start_at", 1),
        fontsize=_b_int(params, "fontsize", 10),
        fmt=_b_get(params, "fmt", "{n} / {total}"),
        color=parse_color(_b_get(params, "color", "#000000"), (0, 0, 0)),
    )
    return out, out.name, "application/pdf"


def _bh_header_footer(
    in_path: Path, out_dir: Path, original: str, params: dict
) -> tuple[Path, str, str]:
    stem = Path(original).stem or "stamped"
    out = out_dir / f"{stem}_stamped.pdf"
    header = _b_get(params, "header")
    footer = _b_get(params, "footer")
    if not header.strip() and not footer.strip():
        raise HTTPException(400, "Header ve footer ikisi de boş.")
    core.pdf_header_footer(
        in_path,
        out,
        header=header,
        footer=footer,
        fontsize=_b_int(params, "fontsize", 9),
        color=parse_color(_b_get(params, "color", "#333333"), (0.2, 0.2, 0.2)),
    )
    return out, out.name, "application/pdf"


def _bh_crop(in_path: Path, out_dir: Path, original: str, params: dict) -> tuple[Path, str, str]:
    stem = Path(original).stem or "cropped"
    out = out_dir / f"{stem}_cropped.pdf"
    core.pdf_crop(
        in_path,
        out,
        top=_b_float(params, "top", 0),
        right=_b_float(params, "right", 0),
        bottom=_b_float(params, "bottom", 0),
        left=_b_float(params, "left", 0),
        unit=_b_get(params, "unit", "pt"),
    )
    return out, out.name, "application/pdf"


def _bh_rotate(in_path: Path, out_dir: Path, original: str, params: dict) -> tuple[Path, str, str]:
    stem = Path(original).stem or "rotated"
    out = out_dir / f"{stem}_rotated.pdf"
    pages_spec = _b_get(params, "pages").strip()
    page_list = parse_int_list(pages_spec) if pages_spec else None
    core.pdf_rotate(in_path, out, angle=_b_int(params, "angle", 90), pages=page_list)
    return out, out.name, "application/pdf"


def _bh_delete_pages(
    in_path: Path, out_dir: Path, original: str, params: dict
) -> tuple[Path, str, str]:
    stem = Path(original).stem or "trimmed"
    out = out_dir / f"{stem}_trimmed.pdf"
    page_list = parse_int_list(_b_get(params, "pages"))
    if not page_list:
        raise HTTPException(400, "Silinecek sayfa belirtilmedi.")
    core.pdf_delete_pages(in_path, out, pages=page_list)
    return out, out.name, "application/pdf"


def _bh_to_csv(in_path: Path, out_dir: Path, original: str, params: dict) -> tuple[Path, str, str]:
    delim = _b_get(params, "delimiter", ",")
    if delim not in (",", ";", "\t", "|"):
        raise HTTPException(400, "Sınırlayıcı yalnızca , ; \\t veya | olabilir.")
    stem = Path(original).stem or "tables"
    out = out_dir / f"{stem}.csv"
    core.pdf_to_csv(
        in_path,
        out,
        table_index=(_b_int(params, "table_index", 0) or None),
        delimiter=delim,
    )
    return out, out.name, "text/csv"


def _bh_to_markdown(
    in_path: Path, out_dir: Path, original: str, params: dict
) -> tuple[Path, str, str]:
    stem = Path(original).stem or "doc"
    out = out_dir / f"{stem}.md"
    core.pdf_to_markdown(in_path, out)
    return out, out.name, "text/markdown"


def _bh_remove_blank(
    in_path: Path, out_dir: Path, original: str, params: dict
) -> tuple[Path, str, str]:
    stem = Path(original).stem or "doc"
    out = out_dir / f"{stem}_no-blank.pdf"
    core.remove_blank_pages(
        in_path,
        out,
        threshold=_b_float(params, "threshold", 0.995),
        dpi=_b_int(params, "dpi", 50),
    )
    return out, out.name, "application/pdf"


_BATCH_HANDLERS = {
    "compress": _bh_compress,
    "encrypt": _bh_encrypt,
    "decrypt": _bh_decrypt,
    "watermark-text": _bh_watermark_text,
    "page-numbers": _bh_page_numbers,
    "header-footer": _bh_header_footer,
    "crop": _bh_crop,
    "rotate": _bh_rotate,
    "delete-pages": _bh_delete_pages,
    "to-csv": _bh_to_csv,
    "to-markdown": _bh_to_markdown,
    "remove-blank": _bh_remove_blank,
}


@router.post("/pdf/batch", response_model=None)
async def pdf_batch_endpoint(request: Request):
    """Tek bir tool'u N PDF'e uygula.
    1 dosya → tek çıktı doğrudan iner; 2+ dosya → her birinin çıktısı ZIP'lenir.
    """
    from starlette.datastructures import UploadFile as _SUploadFile

    form = await request.form()
    raw_tool = form.get("tool")
    tool = raw_tool.strip() if isinstance(raw_tool, str) else ""
    if tool not in _BATCH_HANDLERS:
        raise HTTPException(400, f"Bilinmeyen tool: {tool}")
    handler = _BATCH_HANDLERS[tool]

    uploads: list = []
    for key in ("files", "file"):
        for v in form.getlist(key):
            if isinstance(v, _SUploadFile):
                uploads.append(v)
    if not uploads:
        raise HTTPException(400, "Hiç dosya yüklenmedi.")

    params: dict[str, str] = {}
    for k in form:
        if k in ("tool", "files", "file"):
            continue
        raw = form.get(k)
        if isinstance(raw, UploadFile):
            continue
        params[k] = "" if raw is None else str(raw)

    job_dir = pdf_job_dir()
    is_multi = len(uploads) > 1
    try:
        outputs: list[tuple[Path, str, str]] = []
        errors: list[tuple[str, str]] = []
        for idx, up in enumerate(uploads):
            original = up.filename or f"file_{idx + 1}.pdf"
            in_path = job_dir / f"in_{idx}.pdf"
            try:
                await save_pdf_upload(up, in_path)
            except HTTPException as e:
                if not is_multi:
                    raise
                errors.append((original, str(e.detail)))
                continue
            sub = job_dir / f"out_{idx}"
            sub.mkdir(parents=True, exist_ok=True)
            try:
                outputs.append(handler(in_path, sub, original, params))
            except HTTPException as e:
                if not is_multi:
                    raise
                errors.append((original, str(e.detail)))
            except Exception as e:
                if not is_multi:
                    raise HTTPException(400, f"{original}: {sanitize_error(e)}") from e
                errors.append((original, sanitize_error(e)))

        if not outputs:
            detail = "; ".join(f"{n}: {m}" for n, m in errors[:5]) or "Hiç çıktı üretilemedi."
            raise HTTPException(400, detail)

        if len(outputs) == 1 and not errors:
            out_path, name, mime = outputs[0]
            core.log_history(
                action=f"pdf-{tool}",
                filename=name,
                ip=core.client_ip(request),
            )
            return file_response_with_name(out_path, name, mime, job_dir)

        zip_name = f"{tool}_batch.zip"
        zip_path = job_dir / zip_name
        seen: set[str] = set()
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for out_path, name, _mime in outputs:
                arc = name
                stem = Path(arc).stem
                suffix = Path(arc).suffix
                i = 1
                while arc in seen:
                    i += 1
                    arc = f"{stem}_{i}{suffix}"
                seen.add(arc)
                zf.write(str(out_path), arcname=arc)
            if errors:
                err_lines = ["# İşlenemeyen dosyalar — sebep birlikte yazıldı.\n"]
                for n, m in errors:
                    err_lines.append(f"- {n}: {m}\n")
                zf.writestr("HATA_RAPORU.txt", "".join(err_lines))
        core.log_history(
            action=f"pdf-{tool}-batch",
            filename=zip_name,
            record_count=len(outputs),
            note=(f"{len(errors)} hata" if errors else None),
            ip=core.client_ip(request),
        )
        resp = file_response_with_name(zip_path, zip_name, "application/zip", job_dir)
        resp.headers["X-Batch-Total"] = str(len(uploads))
        resp.headers["X-Batch-Success"] = str(len(outputs))
        resp.headers["X-Batch-Errors"] = str(len(errors))
        return resp
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/batch failed (tool=%s)", tool)
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e
