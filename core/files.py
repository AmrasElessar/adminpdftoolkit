"""File helpers: safe filename, work-dir containment, upload streaming, table extract."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, UploadFile

from state import WORK_DIR

from .errors import sanitize_error
from .logging_setup import logger


def safe_filename(name: str) -> str:
    """Strip path separators and reserved chars from a user-supplied name."""
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    return name[:120] or "output"


def assert_under_work(path: Path) -> None:
    """Defense-in-depth: raise HTTPException(500) if ``path`` escapes WORK_DIR.

    Used after creating job-specific subdirectories to refuse symlink-based
    escapes — relevant when WORK_DIR sits on a shared volume an attacker
    could drop a symlink into.
    """
    real_work = WORK_DIR.resolve()
    try:
        real = path.resolve()
    except (OSError, RuntimeError) as e:
        raise HTTPException(500, "Geçersiz iş klasörü.") from e
    if not real.is_relative_to(real_work):
        raise HTTPException(500, "İş klasörü WORK_DIR dışına çıktı.")


def make_job_dir(*parts: str) -> Path:
    """Create a job directory under WORK_DIR and verify it stays inside it.

    Usage:
      make_job_dir()                       -> WORK_DIR/<uuid4>
      make_job_dir("ocr", uuid4().hex)     -> WORK_DIR/ocr/<uuid>
      make_job_dir("jobs", validated_tok)  -> WORK_DIR/jobs/<tok>

    Raises HTTPException(500) on symlink escape.
    """
    from uuid import uuid4

    if not parts:
        parts = (uuid4().hex,)
    job_dir = WORK_DIR.joinpath(*parts)
    job_dir.mkdir(parents=True, exist_ok=True)
    assert_under_work(job_dir)
    return job_dir


async def save_upload(file: UploadFile, dest: Path) -> int:
    """Stream an UploadFile to disk in chunks; returns bytes written."""
    written = 0
    with dest.open("wb") as fp:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            fp.write(chunk)
    return written


def extract_generic_table(pdf_path: Path) -> list[list[str]]:
    """Delegate to parsers.GenericTableParser for table extraction (S2 plugin layer)."""
    from parsers.generic_table import GenericTableParser

    try:
        return GenericTableParser().extract_rows(pdf_path)
    except Exception as e:
        logger.warning("extract_generic_table failed: %s", sanitize_error(e))
        return []
