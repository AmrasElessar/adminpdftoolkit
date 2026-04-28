"""Convert router — single-PDF preview + sync ``/convert`` + async
``/convert-start`` / ``/convert-progress`` / ``/convert-download`` plus
the SSE ``/events/{kind}/{token}`` stream.

The async pipeline (``convert_worker``) and the Word/JPG-batch worker live
in ``pipelines/convert.py``. The sync ``/convert`` endpoint here writes
its own (simple) output via :func:`_render_sync_output` so we can reuse
one helper across the three target formats — collapsing the previous
near-identical Excel/Word/JPG branches.
"""

from __future__ import annotations

import asyncio
import io
import json
import shutil
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote
from uuid import uuid4

import fitz
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask

import core
from app_http import cleanup_task, gate_pdf_safety
from core import logger, sanitize_error
from pdf_converter import (
    CALL_LOG_QUESTIONS,
    convert_to_jpg,
    convert_to_word,
    is_call_log_pdf,
    is_scanned_pdf,
    parse_call_log,
    write_call_log_excel,
    write_generic_excel,
)
from pdf_safety import full_scan as pdf_safety_scan
from state import ALLOWED_FORMATS, MAX_UPLOAD_MB, convert_store


router = APIRouter()


# ---------------------------------------------------------------------------
# /preview — analyse a PDF and return a recommendation, no conversion.
# ---------------------------------------------------------------------------
@router.post("/preview")
async def preview(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Yalnızca PDF dosyaları kabul edilir.")

    job_dir = core.make_job_dir()
    pdf_path = job_dir / "input.pdf"
    try:
        written = 0
        with pdf_path.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(413, f"Dosya {MAX_UPLOAD_MB} MB sınırını aşıyor.")
                f.write(chunk)

        doc = fitz.open(str(pdf_path))
        try:
            # Reuse the open document for safety check — saves a second fitz.open.
            safety = pdf_safety_scan(pdf_path, doc=doc)
            page_count = len(doc)
            if is_scanned_pdf(doc):
                return {
                    "kind": "scanned",
                    "kind_label": "Görselden PDF",
                    "page_count": page_count,
                    "record_count": None,
                    "headers": [],
                    "rows": [],
                    "preview_shown": 0,
                    "recommended_format": "jpg",
                    "scanned": True,
                    "safety": safety,
                    "message": "📸 Görselden (taranmış) PDF algılandı — metin çıkarılamaz.",
                }
            if is_call_log_pdf(doc):
                records = parse_call_log(doc)
                headers = ["Sıra", "Kayıt No", "Müşteri", "Telefon", "Durum", "Tarih", "Süre"] + CALL_LOG_QUESTIONS
                preview_n = 8
                rows = []
                for i, rec in enumerate(records[:preview_n], 1):
                    row = []
                    for h in headers:
                        if h == "Sıra":
                            row.append(i)
                        elif h == "Kayıt No":
                            row.append(rec.get("#", ""))
                        else:
                            row.append(rec.get(h, ""))
                    rows.append(row)
                return {
                    "kind": "call_log",
                    "kind_label": "Çağrı kayıtları",
                    "page_count": page_count,
                    "record_count": len(records),
                    "headers": headers,
                    "rows": rows,
                    "preview_shown": len(rows),
                    "recommended_format": "excel",
                    "safety": safety,
                }
            text = doc[0].get_text()
            snippet = text.strip().split("\n")[:20]
            return {
                "kind": "generic",
                "kind_label": "Metin belgesi",
                "page_count": page_count,
                "record_count": None,
                "headers": [],
                "rows": [],
                "snippet": snippet,
                "preview_shown": 0,
                "recommended_format": "word",
                "safety": safety,
            }
        finally:
            doc.close()
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Async pipeline — /convert-start, /convert-progress, /convert-download
# ---------------------------------------------------------------------------
@router.post("/convert-start")
async def convert_start(
    file: UploadFile = File(...),
    target: str = Form(...),
    custom_name: str = Form(""),
) -> dict:
    if target not in {"word", "excel", "jpg"}:
        raise HTTPException(400, f"Geçersiz hedef: {target}")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Yalnızca PDF dosyaları kabul edilir.")

    job_dir = core.make_job_dir("convert", uuid4().hex)
    pdf_path = job_dir / "input.pdf"
    written = 0
    with pdf_path.open("wb") as fp:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_MB * 1024 * 1024:
                shutil.rmtree(job_dir, ignore_errors=True)
                raise HTTPException(413, f"Dosya {MAX_UPLOAD_MB} MB sınırını aşıyor.")
            fp.write(chunk)

    try:
        gate_pdf_safety(pdf_path)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise

    token = uuid4().hex
    convert_store.create(
        token,
        target=target,
        phase="starting",
        current=0,
        total=0,
        done=False,
        error=None,
        started_at=time.time(),
        job_dir=str(job_dir),
    )

    from pipelines.convert import convert_worker
    threading.Thread(
        target=convert_worker,
        args=(token, pdf_path, target, custom_name, job_dir, file.filename),
        daemon=True,
    ).start()
    return {"token": token, "target": target}


@router.get("/convert-progress/{token}")
async def convert_progress(token: str) -> dict:
    core.check_token(token)
    job = convert_store.snapshot(token)
    if job:
        core.check_job_timeout(job)
    if job is None:
        job = core.load_persisted_state("convert", token)
    if job is None:
        raise HTTPException(404, "İş bulunamadı.")
    return {
        "phase": job.get("phase"),
        "current": job.get("current", 0),
        "total": job.get("total", 0),
        "done": job.get("done", False),
        "error": job.get("error"),
        "output_name": job.get("output_name"),
        "record_count": job.get("record_count"),
    }


@router.get("/convert-download/{token}", response_model=None)
async def convert_download(token: str, request: Request):
    core.check_token(token)
    job = convert_store.snapshot(token)
    if not job:
        raise HTTPException(404, "İş bulunamadı.")
    if not job.get("done"):
        raise HTTPException(409, "İş henüz tamamlanmadı.")
    if job.get("error"):
        raise HTTPException(500, f"Hata: {job['error']}")
    out_path = job.get("output_path")
    if not out_path:
        raise HTTPException(500, "Çıktı yolu eksik.")
    out_name = job.get("output_name") or "output"
    media = job.get("media_type") or "application/octet-stream"
    record_count = job.get("record_count")
    target = job.get("target", "")
    job_dir = job.get("job_dir")

    core.log_history(
        action="convert", target=target, filename=out_name,
        record_count=record_count, ip=core.client_ip(request),
    )

    def _rm() -> None:
        if job_dir:
            shutil.rmtree(job_dir, ignore_errors=True)
        convert_store.pop(token)

    headers = {}
    if record_count is not None:
        headers["X-Record-Count"] = str(record_count)
    return FileResponse(
        out_path,
        filename=out_name,
        media_type=media,
        headers=headers,
        background=BackgroundTask(_rm),
    )


# ---------------------------------------------------------------------------
# Sync /convert — kept for backwards compat. The three target formats share
# one writer dispatch via _render_sync_output (S5.3 collapse).
# ---------------------------------------------------------------------------
def _render_excel(
    pdf_path: Path,
    out: Path,
    final_stem: str,
    job_dir: Path,
    doc: fitz.Document,
) -> tuple[FileResponse | StreamingResponse, dict[str, Any]]:
    record_count: int | None = None
    if is_call_log_pdf(doc):
        records = parse_call_log(doc)
        record_count = len(records)
        write_call_log_excel(records, out)
    else:
        write_generic_excel(doc, out)
    headers = {"X-Record-Count": str(record_count)} if record_count is not None else {}
    resp = FileResponse(
        str(out),
        filename=out.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
        background=cleanup_task(job_dir),
    )
    return resp, {"record_count": record_count}


def _render_word(
    pdf_path: Path,
    out: Path,
    final_stem: str,
    job_dir: Path,
    doc: fitz.Document,
) -> tuple[FileResponse, dict[str, Any]]:
    convert_to_word(pdf_path, out)
    resp = FileResponse(
        str(out),
        filename=out.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        background=cleanup_task(job_dir),
    )
    return resp, {}


def _render_jpg_zip(
    pdf_path: Path,
    out: Path,
    final_stem: str,
    job_dir: Path,
    doc: fitz.Document,
) -> tuple[StreamingResponse, dict[str, Any]]:
    jpg_dir = job_dir / final_stem
    files = convert_to_jpg(pdf_path, jpg_dir)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, arcname=f"{final_stem}/{f.name}")
    buf.seek(0)
    shutil.rmtree(job_dir, ignore_errors=True)
    zip_name = f"{final_stem}.zip"
    ascii_fallback = zip_name.encode("ascii", "ignore").decode("ascii") or "output.zip"
    cd = f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(zip_name)}"
    resp = StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": cd},
    )
    return resp, {}


_SYNC_RENDERERS: dict[str, tuple[str, Callable[..., tuple[Any, dict[str, Any]]]]] = {
    "excel": (".xlsx", _render_excel),
    "word":  (".docx", _render_word),
    "jpg":   (".zip",  _render_jpg_zip),
}


@router.post("/convert", response_model=None)
async def convert(
    file: UploadFile = File(...),
    target: str = Form(...),
    custom_name: str = Form(""),
):
    if target not in ALLOWED_FORMATS:
        raise HTTPException(400, f"Geçersiz format: {target}")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Yalnızca PDF dosyaları kabul edilir.")

    job_dir = core.make_job_dir()
    pdf_path = job_dir / "input.pdf"

    try:
        written = 0
        with pdf_path.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(413, f"Dosya {MAX_UPLOAD_MB} MB sınırını aşıyor.")
                f.write(chunk)

        gate_pdf_safety(pdf_path)

        stem = Path(file.filename).stem
        safe_custom = core.safe_filename(custom_name.strip()) if custom_name else ""
        final_stem = safe_custom or core.safe_filename(stem)
        suffix, render = _SYNC_RENDERERS[target]
        out = job_dir / f"{final_stem}{suffix}"

        doc = fitz.open(str(pdf_path))
        try:
            if target in {"word", "excel"} and is_scanned_pdf(doc):
                raise HTTPException(
                    400,
                    "Bu PDF taranmış (metin katmanı yok). 'OCR ile Dene' butonunu kullanın.",
                )
            response, _meta = render(pdf_path, out, final_stem, job_dir, doc)
        finally:
            doc.close()
        return response
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/convert sync conversion failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(500, f"Dönüşüm hatası: {sanitize_error(e)}") from e


# ---------------------------------------------------------------------------
# SSE — push-based progress alternative to polling.
# ---------------------------------------------------------------------------
async def _event_stream(kind: str, token: str):
    last_payload: str | None = None
    last_emit = 0.0
    HEARTBEAT_SECONDS = 15.0
    POLL_INTERVAL = 0.5
    while True:
        snap = core.job_snapshot(kind, token)
        if snap is None:
            yield 'event: not_found\ndata: {"detail":"İş bulunamadı."}\n\n'
            return
        payload = json.dumps(snap, default=str, ensure_ascii=False)
        now = time.time()
        if payload != last_payload or (now - last_emit) >= HEARTBEAT_SECONDS:
            yield f"data: {payload}\n\n"
            last_payload = payload
            last_emit = now
        if snap.get("done"):
            return
        await asyncio.sleep(POLL_INTERVAL)


@router.get("/events/{kind}/{token}", response_model=None)
async def job_events(kind: str, token: str):
    if kind not in {"convert", "batch", "ocr"}:
        raise HTTPException(404, "Geçersiz iş türü.")
    core.check_token(token)
    return StreamingResponse(
        _event_stream(kind, token),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
