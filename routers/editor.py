"""PDF editor router — ``/pdf/edit/*`` endpoints.

Three endpoints:

* ``GET  /pdf/edit/fonts`` — bundled font catalogue (id / family / variants).
* ``POST /pdf/edit/spans`` — per-page text-span metadata + extractability.
* ``POST /pdf/edit/save``  — apply an operation list and return the resulting PDF.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

import core
from app_http import pdf_job_dir, pdf_response, save_pdf_upload
from core import logger, sanitize_error

router = APIRouter()


@router.get("/pdf/edit/fonts")
async def pdf_editor_fonts() -> dict:
    families = core.editor_font_catalog()
    return {
        "families": families,
        "fallback": "noto-sans"
        if any(f["id"] == "noto-sans" for f in families)
        else (families[0]["id"] if families else None),
        "count": len(families),
    }


@router.post("/pdf/edit/spans")
async def pdf_editor_spans(
    request: Request,
    file: UploadFile = File(...),
    granularity: str = Form("line"),
    merge_adjacent: bool = Form(True),
    max_pages: int = Form(0),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Yalnızca PDF dosyaları kabul edilir.")
    if granularity not in ("word", "line", "block"):
        raise HTTPException(400, "granularity 'word' / 'line' / 'block' olmalı.")
    cap = None if max_pages <= 0 else min(max_pages, 200)
    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        extractability = core.classify_pdf_extractability(in_path)
        spans = (
            core.extract_text_spans(
                in_path,
                granularity=granularity,
                merge_adjacent=merge_adjacent,
                max_pages=cap,
            )
            if extractability["extractable"]
            else []
        )
        return {
            "spans": spans,
            "count": len(spans),
            "granularity": granularity,
            "max_pages_scanned": cap or "all",
            "extractability": extractability,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/pdf/edit/spans failed")
        raise HTTPException(400, sanitize_error(e)) from e
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


@router.post("/pdf/edit/save", response_model=None)
async def pdf_editor_save(
    request: Request,
    file: UploadFile = File(...),
    operations: str = Form("[]"),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Yalnızca PDF dosyaları kabul edilir.")
    try:
        ops = json.loads(operations or "[]")
        if not isinstance(ops, list):
            raise ValueError("operations bir liste olmalı.")
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(400, f"operations JSON geçersiz: {sanitize_error(e)}") from e

    job_dir = pdf_job_dir()
    try:
        in_path = job_dir / "input.pdf"
        await save_pdf_upload(file, in_path)
        out_path = job_dir / f"{Path(file.filename).stem}_edited.pdf"
        summary = core.apply_editor_operations(in_path, out_path, ops)
        core.log_history(
            action="pdf-edit-save",
            filename=out_path.name,
            record_count=summary["applied"],
            note=f"applied={summary['applied']}, skipped={summary['skipped']}",
            ip=core.client_ip(request),
        )
        resp = pdf_response(out_path, out_path.name, job_dir)
        resp.headers["X-Operations-Applied"] = str(summary["applied"])
        resp.headers["X-Operations-Skipped"] = str(summary["skipped"])
        resp.headers["X-Operations-Received"] = str(len(ops))
        resp.headers["X-Editor-Phase"] = "4e"
        if summary["errors"]:
            first = summary["errors"][0]
            raw = (f"#{first['index']} ({first.get('type') or '?'}): {first.get('error', '')}")[
                :200
            ]
            resp.headers["X-First-Error"] = raw.encode("ascii", "replace").decode("ascii")
        return resp
    except HTTPException:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
    except Exception as e:
        logger.exception("/pdf/edit/save failed")
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, sanitize_error(e)) from e
