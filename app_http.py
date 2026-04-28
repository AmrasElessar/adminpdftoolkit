"""HTTP / FastAPI helpers shared by router modules.

Lives in its own module so router files can import these without pulling in
the whole ``app.py`` (which would create an import cycle: ``app.py``
imports ``routers.*`` at startup, ``routers.*`` would re-import ``app.py``
to reach ``_pdf_response`` etc.).

These helpers were lifted from ``app.py`` during the S5 split unchanged —
none of them owns mutable state.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

import core
from pdf_safety import UnsafePDFError, assert_safe as _pdf_assert_safe
from state import MAX_UPLOAD_MB


_IMAGE_EXT_RE = re.compile(r"\.(jpg|jpeg|png|webp|bmp|tiff?|gif)$", re.IGNORECASE)


def gate_pdf_safety(pdf_path: Path) -> None:
    """S3 conversion gate: refuse PDFs whose safety verdict is 'danger'.

    Wraps ``pdf_safety.assert_safe``, translating ``UnsafePDFError`` to
    ``HTTPException(400)`` with an ``X-Safety-Verdict: danger`` header. The
    operator can flip the active policy via ``HT_SAFETY_POLICY`` (off / warn
    / block_danger).
    """
    try:
        _pdf_assert_safe(pdf_path)
    except UnsafePDFError as e:
        verdict = e.scan.get("overall", "danger")
        structure = e.scan.get("structure") or {}
        findings = structure.get("findings") or []
        labels = ", ".join(sorted({f.get("label", "?") for f in findings})) or "?"
        raise HTTPException(
            status_code=400,
            detail=f"Güvensiz PDF reddedildi (bulgular: {labels}).",
            headers={"X-Safety-Verdict": verdict},
        ) from e


def pdf_job_dir() -> Path:
    """Fresh per-request job directory under ``_work/jobs/{uuid}``."""
    return core.make_job_dir("jobs", uuid4().hex)


def cleanup_task(job_dir: Path) -> BackgroundTask:
    """``FileResponse`` background task that wipes ``job_dir`` after send."""
    def _rm() -> None:
        shutil.rmtree(job_dir, ignore_errors=True)
    return BackgroundTask(_rm)


async def save_pdf_upload(
    file: UploadFile, dest: Path, *, label: str = "PDF"
) -> None:
    """Stream a PDF upload to disk, enforcing ``MAX_UPLOAD_MB`` and a
    ``.pdf`` extension."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            400, f"{label} için yalnızca .pdf dosyaları kabul edilir."
        )
    written = 0
    with dest.open("wb") as fp:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_MB * 1024 * 1024:
                raise HTTPException(
                    413, f"Dosya {MAX_UPLOAD_MB} MB sınırını aşıyor."
                )
            fp.write(chunk)


def pdf_response(
    out_path: Path, download_name: str, job_dir: Path
) -> FileResponse:
    """``FileResponse`` for a PDF — UTF-8 filename + auto-cleanup task."""
    safe_name = core.safe_filename(download_name)
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"
    ascii_fallback = safe_name.encode("ascii", "ignore").decode("ascii") or "output.pdf"
    cd = (
        f"attachment; filename=\"{ascii_fallback}\"; "
        f"filename*=UTF-8''{quote(safe_name)}"
    )
    return FileResponse(
        str(out_path),
        media_type="application/pdf",
        headers={"Content-Disposition": cd},
        background=cleanup_task(job_dir),
    )


def file_response_with_name(
    out_path: Path, download_name: str, media_type: str, job_dir: Path
) -> FileResponse:
    """Same as ``pdf_response`` but with a caller-chosen media type and
    no PDF-extension force. Used by markdown/csv/zip outputs."""
    safe_name = core.safe_filename(download_name)
    ascii_fallback = safe_name.encode("ascii", "ignore").decode("ascii") or "output"
    cd = (
        f"attachment; filename=\"{ascii_fallback}\"; "
        f"filename*=UTF-8''{quote(safe_name)}"
    )
    return FileResponse(
        str(out_path),
        media_type=media_type,
        headers={"Content-Disposition": cd},
        background=cleanup_task(job_dir),
    )


def parse_color(
    value: str, default: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Parse ``"#RRGGBB"`` or ``"r,g,b"`` (0-255 or 0-1) into 0-1 floats."""
    s = (value or "").strip()
    if not s:
        return default
    try:
        if s.startswith("#") and len(s) == 7:
            r = int(s[1:3], 16) / 255.0
            g = int(s[3:5], 16) / 255.0
            b = int(s[5:7], 16) / 255.0
            return r, g, b
        parts = [float(p.strip()) for p in s.split(",")]
        if len(parts) != 3:
            return default
        if any(p > 1.0 for p in parts):
            parts = [p / 255.0 for p in parts]
        return parts[0], parts[1], parts[2]
    except (ValueError, IndexError):
        return default


def parse_int_list(value: str) -> list[int]:
    """Parse ``"1,3,5-7"`` into ``[1,3,5,6,7]``. Raises ``HTTPException(400)``
    on malformed input."""
    out: list[int] = []
    for piece in (value or "").split(","):
        piece = piece.strip()
        if not piece:
            continue
        if "-" in piece:
            a, b = piece.split("-", 1)
            try:
                start, end = int(a.strip()), int(b.strip())
            except ValueError as e:
                raise HTTPException(400, f"Geçersiz aralık: {piece}") from e
            if end < start:
                start, end = end, start
            out.extend(range(start, end + 1))
        else:
            try:
                out.append(int(piece))
            except ValueError as e:
                raise HTTPException(400, f"Geçersiz sayı: {piece}") from e
    return out
