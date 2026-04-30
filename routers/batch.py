"""Batch router — every ``/batch-*`` endpoint.

Two flavours:

* ``files`` — Word/JPG mass conversion (``/batch-files`` →
  ``batch_files_worker``).
* ``convert`` — Excel merge (``/batch-convert`` → ``batch_convert_worker``).

Plus the merged-Excel review/edit/distribute family
(``/batch-preview``, ``/batch-deduplicate``, ``/batch-filter``,
``/batch-download``, ``/batch-distribute*``).

Worker logic and the load/save/distribute helpers live in
``pipelines/batch_convert.py`` and ``pipelines/convert.py``.
"""

from __future__ import annotations

import io
import json
import shutil
import threading
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import fitz
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask

import core
from pdf_converter import (
    is_call_log_pdf,
    is_scanned_pdf,
    parse_call_log,
)
from pdf_safety import clamav_available
from pdf_safety import full_scan as pdf_safety_scan
from pipelines.batch_convert import (
    batch_convert_worker,
    load_distribution,
    load_job,
    save_view,
    write_merged_excel,
)
from pipelines.convert import batch_files_worker
from state import batch_store

router = APIRouter()


# ---------------------------------------------------------------------------
# /batch-analyze — classify each PDF; preview before merge.
# ---------------------------------------------------------------------------
@router.post("/batch-analyze")
async def batch_analyze(files: list[UploadFile] = File(...)) -> dict:
    if not files:
        raise HTTPException(400, "En az bir PDF gerekli.")

    items = []
    compatible = 0
    incompatible = 0
    total = 0

    for f in files:
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            items.append(
                {
                    "name": f.filename or "(adsız)",
                    "compatible": False,
                    "kind": "invalid",
                    "kind_label": "PDF değil",
                    "message": "Yalnızca PDF kabul edilir.",
                }
            )
            incompatible += 1
            continue

        tmp = core.make_job_dir()
        p = tmp / "input.pdf"
        try:
            await core.save_upload(f, p)
            doc = fitz.open(str(p))
            try:
                # Reuse the open document for safety check — saves a second
                # fitz.open per uploaded file in the batch loop.
                safety = pdf_safety_scan(p, doc=doc)
                page_count = len(doc)
                if is_scanned_pdf(doc):
                    items.append(
                        {
                            "name": f.filename,
                            "compatible": False,
                            "kind": "scanned",
                            "kind_label": "📸 Görselden PDF",
                            "page_count": page_count,
                            "record_count": 0,
                            "safety": safety,
                            "message": "Görselden (taranmış) PDF — metin çıkarılamaz, birleştirmeye dahil edilemez.",
                        }
                    )
                    incompatible += 1
                    continue
                if is_call_log_pdf(doc):
                    records = parse_call_log(doc)
                    items.append(
                        {
                            "name": f.filename,
                            "compatible": True,
                            "kind": "call_log",
                            "kind_label": "Çağrı kayıtları",
                            "page_count": page_count,
                            "record_count": len(records),
                            "safety": safety,
                        }
                    )
                    compatible += 1
                    total += len(records)
                else:
                    table = core.extract_generic_table(p)
                    if table and len(table) >= 2:
                        items.append(
                            {
                                "name": f.filename,
                                "compatible": False,
                                "kind": "other_table",
                                "kind_label": "Farklı tablo yapısı",
                                "page_count": page_count,
                                "record_count": len(table) - 1,
                                "source_headers": table[0],
                                "sample_rows": table[1:4],
                                "safety": safety,
                                "message": "Çağrı kaydı değil — sütunları eşleyerek dahil edebilirsiniz.",
                            }
                        )
                    else:
                        items.append(
                            {
                                "name": f.filename,
                                "compatible": False,
                                "kind": "other",
                                "kind_label": "Tablo yok",
                                "page_count": page_count,
                                "record_count": 0,
                                "safety": safety,
                                "message": "Tablo içermiyor — birleşik Excel'e dahil edilemez.",
                            }
                        )
                    incompatible += 1
            finally:
                doc.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return {
        "items": items,
        "file_count": len(files),
        "compatible_count": compatible,
        "incompatible_count": incompatible,
        "total_records": total,
        "target_schema": list(getattr(core, "TARGET_SCHEMA", [])),
        "av_available": clamav_available(),
    }


# ---------------------------------------------------------------------------
# /batch-files — Word/JPG ZIP (calls batch_files_worker)
# ---------------------------------------------------------------------------
@router.post("/batch-files")
async def batch_files(
    files: list[UploadFile] = File(...),
    target: str = Form(...),
    names: str = Form("[]"),
    jpg_quality: int = Form(90),
    jpg_dpi: int = Form(200),
    skip_safety: bool = Form(False),
) -> dict:
    if target not in {"word", "jpg", "excel"}:
        raise HTTPException(400, f"Geçersiz hedef: {target}")
    if not files:
        raise HTTPException(400, "En az bir PDF gerekli.")
    jpg_quality = max(50, min(100, int(jpg_quality)))
    jpg_dpi = max(72, min(600, int(jpg_dpi)))

    try:
        custom_names: list[str] = [str(x) for x in json.loads(names or "[]")]
    except json.JSONDecodeError:
        raise HTTPException(400, "Geçersiz names JSON.") from None

    job_dir = core.make_job_dir("batch", uuid4().hex)

    files_data: list[tuple[str, Path]] = []
    for idx, f in enumerate(files):
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            continue
        p = job_dir / f"in_{idx}.pdf"
        await core.save_upload(f, p)
        files_data.append((f.filename, p))

    if not files_data:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, "Geçerli PDF bulunamadı.")

    # Safety scan is now done in the worker thread (visible via SSE, cancellable).
    token = uuid4().hex
    batch_store.create(
        token,
        type="files",
        target=target,
        phase="scanning" if not skip_safety else "starting",
        current=0,
        total=len(files_data),
        done=False,
        error=None,
        started_at=time.time(),
        job_dir=str(job_dir),
        skip_safety=skip_safety,
    )
    threading.Thread(
        target=batch_files_worker,
        args=(
            token, files_data, target, job_dir, custom_names,
            jpg_quality, skip_safety, jpg_dpi,
        ),
        daemon=True,
    ).start()
    return {"token": token, "type": "files", "total": len(files_data)}


@router.get("/batch-progress/{token}")
async def batch_progress(token: str) -> dict:
    core.check_token(token)
    job = batch_store.snapshot(token)
    if job:
        core.check_job_timeout(job)
    if job is None:
        job = core.load_persisted_state("batch", token)
    if job is None:
        raise HTTPException(404, "İş bulunamadı.")
    out: dict[str, Any] = {
        "type": job.get("type"),
        "phase": job.get("phase"),
        "current": job.get("current", 0),
        "total": job.get("total", 0),
        "done": job.get("done", False),
        "error": job.get("error"),
        "last_file": job.get("last_file"),
        "files_progress": job.get("files_progress") or [],
        "files_safety": job.get("files_safety") or [],
    }
    if job.get("done") and job.get("type") == "convert":
        out["result"] = job.get("result")
    if job.get("done") and job.get("type") == "files":
        out["output_name"] = job.get("output_name")
        out["produced"] = job.get("produced")
    return out


@router.get("/batch-files-download/{token}", response_model=None)
async def batch_files_download(token: str, request: Request):
    core.check_token(token)
    job = batch_store.snapshot(token)
    if not job:
        raise HTTPException(404, "İş bulunamadı.")
    if not job.get("done"):
        raise HTTPException(409, "İş henüz tamamlanmadı.")
    if job.get("error"):
        raise HTTPException(500, f"İş hatası: {job['error']}")
    out_path = job.get("output_path")
    if not out_path:
        raise HTTPException(500, "Çıktı yolu eksik.")
    out_name = job.get("output_name") or "output.zip"
    produced = job.get("produced", 0)
    target = job.get("target", "")
    job_dir = job.get("job_dir")

    core.log_history(
        action="batch_files",
        target=target,
        filename=out_name,
        record_count=produced,
        ip=core.client_ip(request),
        note=f"{produced} dosya",
    )

    def _rm() -> None:
        if job_dir:
            shutil.rmtree(job_dir, ignore_errors=True)
        batch_store.pop(token)

    ascii_fallback = out_name.encode("ascii", "ignore").decode("ascii") or "output.zip"
    cd = f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(out_name)}"
    return FileResponse(
        out_path,
        filename=out_name,
        media_type="application/zip",
        headers={"Content-Disposition": cd, "X-File-Count": str(produced)},
        background=BackgroundTask(_rm),
    )


# ---------------------------------------------------------------------------
# /batch-convert — Excel merge (calls batch_convert_worker)
# ---------------------------------------------------------------------------
@router.post("/batch-convert")
async def batch_convert(
    files: list[UploadFile] = File(...),
    mappings: str = Form("{}"),
    skip: str = Form("[]"),
    skip_safety: bool = Form(False),
) -> dict:
    if not files:
        raise HTTPException(400, "En az bir PDF gerekli.")

    try:
        mappings_obj: dict[str, dict[str, int | None]] = json.loads(mappings or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Geçersiz mapping JSON.") from None
    if not isinstance(mappings_obj, dict):
        raise HTTPException(400, "Mapping bir nesne (dict) olmalı.")
    for fname, mp in mappings_obj.items():
        if not isinstance(mp, dict):
            raise HTTPException(400, f"Mapping[{fname}] bir nesne (dict) olmalı.")
        for tgt, src_idx in mp.items():
            if src_idx is None or src_idx == "":
                continue
            try:
                int(src_idx)
            except (TypeError, ValueError):
                raise HTTPException(
                    400,
                    f"Mapping[{fname}][{tgt}] geçersiz sütun indeksi: {src_idx!r}",
                ) from None

    try:
        skip_list: list[str] = json.loads(skip or "[]")
    except json.JSONDecodeError:
        raise HTTPException(400, "Geçersiz skip JSON.") from None
    if not isinstance(skip_list, list):
        raise HTTPException(400, "Skip bir liste olmalı.")
    skip_list = [str(x) for x in skip_list]

    job_token = uuid4().hex
    job_dir = core.make_job_dir("jobs", job_token)

    files_data: list[tuple[str, Path]] = []
    for idx, f in enumerate(files):
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            continue
        p = job_dir / f"in_{idx}.pdf"
        await core.save_upload(f, p)
        files_data.append((f.filename, p))

    if not files_data:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(400, "Geçerli PDF bulunamadı.")

    # Safety scan moved into the worker so the user sees per-file scanning
    # progress and can cancel via /job-skip-safety/{kind}/{token}.
    progress_token = uuid4().hex
    batch_store.create(
        progress_token,
        type="convert",
        phase="scanning" if not skip_safety else "starting",
        current=0,
        total=len(files_data),
        done=False,
        error=None,
        started_at=time.time(),
        job_dir=str(job_dir),
        skip_safety=skip_safety,
    )
    threading.Thread(
        target=batch_convert_worker,
        args=(
            progress_token,
            files_data,
            mappings_obj,
            skip_list,
            job_token,
            len(files),
            skip_safety,
        ),
        daemon=True,
    ).start()
    return {"token": progress_token, "type": "convert", "total": len(files_data)}


# ---------------------------------------------------------------------------
# Merged-Excel review / edit endpoints (preview, dedup, filter, download)
# ---------------------------------------------------------------------------
@router.get("/batch-preview/{token}")
async def batch_preview(token: str) -> dict:
    data = load_job(token)
    records = data["records"]
    sources = data["source_files"]

    phone_counts: dict[str, int] = {}
    for rec in records:
        p = core.normalize_phone(rec.get("Telefon"))
        if p:
            phone_counts[p] = phone_counts.get(p, 0) + 1

    duplicate_phone_count = sum(1 for c in phone_counts.values() if c > 1)
    duplicate_row_count = sum(c - 1 for c in phone_counts.values() if c > 1)

    seen: dict[str, int] = {}
    dup_flags: list[int] = []
    for rec in records:
        p = core.normalize_phone(rec.get("Telefon"))
        if not p or phone_counts[p] == 1:
            dup_flags.append(0)
        else:
            seen[p] = seen.get(p, 0) + 1
            dup_flags.append(1 if seen[p] == 1 else 2)

    target_schema = list(getattr(core, "TARGET_SCHEMA", []))
    headers = ["Sıra", "Kaynak PDF", "Kayıt No", *target_schema]
    rows = []
    for rec, src in zip(records, sources, strict=False):
        row = []
        for h in headers:
            if h == "Kaynak PDF":
                row.append(src)
            else:
                row.append(rec.get(h, ""))
        rows.append(row)
    return {
        "record_count": len(records),
        "headers": headers,
        "rows": rows,
        "filename": data["filename"],
        "duplicate_phone_count": duplicate_phone_count,
        "duplicate_row_count": duplicate_row_count,
        "dup_flags": dup_flags,
        "state": data.get("state") or {"deduplicated": False, "filters": {}},
        "original_count": len(data.get("original_records", records)),
    }


@router.post("/batch-deduplicate/{token}")
async def batch_deduplicate(token: str) -> dict:
    data = load_job(token)
    state = data.get("state") or {"deduplicated": False, "filters": {}}
    state["deduplicated"] = True
    before = len(data["records"])
    result = save_view(token, state)
    removed = before - result["record_count"]
    return {
        "removed_count": max(0, removed),
        "remaining_count": result["record_count"],
        "filename": result["filename"],
        "state": result["state"],
    }


@router.post("/batch-undeduplicate/{token}")
async def batch_undeduplicate(token: str) -> dict:
    data = load_job(token)
    state = data.get("state") or {"deduplicated": False, "filters": {}}
    state["deduplicated"] = False
    result = save_view(token, state)
    return {
        "remaining_count": result["record_count"],
        "filename": result["filename"],
        "state": result["state"],
    }


@router.get("/batch-filter-options/{token}")
async def batch_filter_options(token: str, column: str) -> dict:
    data = load_job(token)
    records = data["records"]
    counts: dict[str, int] = {}
    for rec in records:
        val = str(rec.get(column, "")).strip()
        key = val if val else "(boş)"
        counts[key] = counts.get(key, 0) + 1
    items = sorted(
        counts.items(),
        key=lambda kv: (kv[0] == "(boş)", -kv[1], kv[0].lower()),
    )
    return {
        "column": column,
        "total": len(records),
        "options": [{"value": k, "count": v} for k, v in items],
    }


@router.post("/batch-filter/{token}")
async def batch_filter(
    token: str,
    filters: str = Form("{}"),
) -> dict:
    try:
        filters_obj: dict[str, list[str]] = json.loads(filters or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Geçersiz filters JSON.") from None

    cleaned = {col: vals for col, vals in filters_obj.items() if vals}
    data = load_job(token)
    state = data.get("state") or {"deduplicated": False, "filters": {}}
    state["filters"] = cleaned
    result = save_view(token, state)
    return {
        "remaining_count": result["record_count"],
        "filename": result["filename"],
        "state": result["state"],
    }


@router.get("/batch-download/{token}", response_model=None)
async def batch_download(token: str, request: Request):
    job_dir = core.make_job_dir("jobs", token)
    data = load_job(token)
    xlsx = job_dir / data["filename"]
    if not xlsx.exists():
        raise HTTPException(404, "Excel dosyası bulunamadı.")
    core.log_history(
        action="batch_excel",
        target="excel",
        filename=data["filename"],
        record_count=len(data.get("records", [])),
        ip=core.client_ip(request),
    )
    return FileResponse(
        str(xlsx),
        filename=data["filename"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------------------
# Distribute (sequential / round-robin / custom)
# ---------------------------------------------------------------------------
@router.post("/batch-distribute/{token}")
async def batch_distribute(
    token: str,
    teams: str = Form(...),
    strategy: str = Form(...),
    ratios: str = Form("[]"),
) -> dict:
    data = load_job(token)
    records: list[dict] = data["records"]
    sources: list[str] = data["source_files"]

    try:
        team_list: list[str] = [str(t).strip() for t in json.loads(teams) if str(t).strip()]
    except json.JSONDecodeError:
        raise HTTPException(400, "Geçersiz teams JSON.") from None
    if not team_list:
        raise HTTPException(400, "En az bir ekip gerekli.")
    if len(set(team_list)) != len(team_list):
        raise HTTPException(400, "Ekip adları benzersiz olmalı.")

    try:
        ratio_list: list[float] = [float(r) for r in json.loads(ratios)]
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(400, "Geçersiz ratios JSON.") from None

    indexed = list(zip(records, sources, strict=False))

    if strategy == "sequential":
        assigned = core.distribute_sequential(indexed, team_list)
    elif strategy == "roundrobin":
        assigned = core.distribute_roundrobin(indexed, team_list)
    elif strategy == "custom":
        try:
            assigned = core.distribute_custom(indexed, team_list, ratio_list)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    else:
        raise HTTPException(400, f"Bilinmeyen dağıtım tipi: {strategy}")

    job_dir = core.make_job_dir("jobs", token)
    dist_obj = {
        "strategy": strategy,
        "teams": team_list,
        "assignments": [
            {
                "name": team,
                "records": [r[0] for r in assigned[team]],
                "sources": [r[1] for r in assigned[team]],
            }
            for team in team_list
        ],
    }
    with (job_dir / "distribution.json").open("w", encoding="utf-8") as fp:
        json.dump(dist_obj, fp, ensure_ascii=False)

    counts = {team: len(assigned[team]) for team in team_list}
    return {
        "strategy": strategy,
        "teams": team_list,
        "counts": counts,
        "total": sum(counts.values()),
    }


@router.get("/batch-distribute/{token}/team/{team_idx}")
async def batch_distribute_team(token: str, team_idx: int) -> dict:
    dist = load_distribution(token)
    if team_idx < 0 or team_idx >= len(dist["assignments"]):
        raise HTTPException(404, "Ekip bulunamadı.")
    a = dist["assignments"][team_idx]
    target_schema = list(getattr(core, "TARGET_SCHEMA", []))
    headers = ["Sıra", "Kaynak PDF", "Kayıt No", *target_schema]
    rows = []
    for rec, src in zip(a["records"], a["sources"], strict=False):
        row = []
        for h in headers:
            if h == "Kaynak PDF":
                row.append(src)
            else:
                row.append(rec.get(h, ""))
        rows.append(row)
    return {
        "name": a["name"],
        "record_count": len(a["records"]),
        "headers": headers,
        "rows": rows,
    }


@router.get("/batch-distribute/{token}/download", response_model=None)
async def batch_distribute_download(token: str, request: Request):
    dist = load_distribution(token)
    job_dir = core.make_job_dir("jobs", token)
    zip_buf = io.BytesIO()
    total = 0
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for a in dist["assignments"]:
            if not a["records"]:
                continue
            team_xlsx = job_dir / f"_team_{core.safe_filename(a['name'])}.xlsx"
            write_merged_excel(a["records"], a["sources"], team_xlsx)
            zf.write(team_xlsx, arcname=f"{core.safe_filename(a['name'])}.xlsx")
            team_xlsx.unlink(missing_ok=True)
            total += len(a["records"])
    zip_buf.seek(0)
    zip_name = f"dagitim_{total}_kayit.zip"
    ascii_fallback = zip_name.encode("ascii", "ignore").decode("ascii") or "distribution.zip"
    cd = f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(zip_name)}"
    core.log_history(
        action="distribute",
        target="zip",
        filename=zip_name,
        record_count=total,
        ip=core.client_ip(request),
        note=f"{len(dist['assignments'])} ekip · {dist.get('strategy', '')}",
    )
    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": cd},
    )
