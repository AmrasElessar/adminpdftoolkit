"""OCR router — ``/ocr-start``, ``/ocr-progress``, ``/ocr-download``.

Worker logic lives in ``pipelines/ocr.py``. This file just validates input,
persists the job dict, and starts the thread.
"""

from __future__ import annotations

import shutil
import time
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

import core
from app_http import gate_pdf_safety
from state import MAX_UPLOAD_MB, ocr_store, submit_worker

router = APIRouter()


@router.post("/ocr-start")
async def ocr_start(
    file: UploadFile = File(...),
    target: str = Form("word"),
) -> dict:
    """OCR işini başlatır, token döndürür. Gerçek iş arka plan thread'inde yürür."""
    if target not in {"word", "excel", "jpg"}:
        raise HTTPException(400, f"Geçersiz hedef: {target}")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Yalnızca PDF dosyaları kabul edilir.")

    job_dir = core.make_job_dir("ocr", uuid4().hex)
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
    ocr_store.create(
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

    from pipelines.ocr import ocr_worker

    try:
        submit_worker(ocr_worker, token, pdf_path, target, job_dir, file.filename)
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        ocr_store.pop(token)
        raise
    return {"token": token}


@router.get("/ocr-progress/{token}")
async def ocr_progress(token: str) -> dict:
    core.check_token(token)
    job = ocr_store.snapshot(token)
    if job:
        core.check_job_timeout(job)
    if job is None:
        job = core.load_persisted_state("ocr", token)
    if job is None:
        raise HTTPException(404, "OCR işi bulunamadı.")
    return {
        "phase": job.get("phase"),
        "current": job.get("current", 0),
        "total": job.get("total", 0),
        "done": job.get("done", False),
        "error": job.get("error"),
        "output_name": job.get("output_name"),
    }


@router.get("/ocr-download/{token}", response_model=None)
async def ocr_download(token: str, request: Request):
    core.check_token(token)
    job = ocr_store.snapshot(token)
    if not job:
        raise HTTPException(404, "OCR işi bulunamadı.")
    if not job.get("done"):
        raise HTTPException(409, "OCR henüz tamamlanmadı.")
    if job.get("error"):
        raise HTTPException(500, f"OCR hatası: {job['error']}")
    out_path = job.get("output_path")
    if not out_path:
        raise HTTPException(500, "OCR çıktı yolu eksik.")
    out_name = job.get("output_name") or "ocr_cikti"
    media = job.get("media_type") or "application/octet-stream"
    target = job.get("target", "")
    job_dir = job.get("job_dir")

    core.log_history(
        action="ocr",
        target=target,
        filename=out_name,
        ip=core.client_ip(request),
    )

    def _rm() -> None:
        if job_dir:
            shutil.rmtree(job_dir, ignore_errors=True)
        ocr_store.pop(token)

    return FileResponse(
        out_path,
        filename=out_name,
        media_type=media,
        background=BackgroundTask(_rm),
    )
