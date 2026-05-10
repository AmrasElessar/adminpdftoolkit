"""File helpers: safe filename, work-dir containment, upload streaming, table extract."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from fastapi import HTTPException, UploadFile

from state import WORK_DIR

from .errors import sanitize_error
from .logging_setup import logger

# Control chars (C0 + C1 + DEL) — none of these belong in a filename and
# they confuse downstream tooling that prints the name as display text.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def safe_filename(name: str) -> str:
    """Strip path separators and reserved chars from a user-supplied name.

    NFKC-normalises first so visually-identical Unicode variants
    (``..‮/foo`` with right-to-left override, ``‥`` U+2025 two-dot leader,
    full-width ``／``) collapse to their ASCII canonical form before the
    separator/dot cleanup runs. Without normalisation, a name crafted with
    those code points slips past the regex and ends up confusing display
    code further downstream.
    """
    name = unicodedata.normalize("NFKC", name or "")
    name = _CONTROL_CHARS_RE.sub("", name)
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    # POSIX treats backslash as a literal char, so a Windows-style
    # ``..\foo`` filename round-trips through Path().stem as ``..\foo`` and
    # only the backslash is rewritten above, leaving ``.._foo`` — defense-
    # in-depth: collapse any surviving ``..`` runs.
    name = re.sub(r"\.{2,}", "_", name)
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

    Defense in depth — three layers:
      1. Reject obviously hostile parts (path separators, ``..``, empty)
         BEFORE touching the filesystem. Stops a remote caller passing
         ``..\\evil`` from creating directories outside WORK_DIR (Windows
         interprets backslash as a separator inside ``joinpath``).
      2. Resolve the candidate path with ``resolve(strict=False)`` and
         check ``is_relative_to(WORK_DIR)`` BEFORE ``mkdir`` — prevents
         a disk-fill DoS where every probe creates a leftover dir even
         if the assert later fails.
      3. Post-``mkdir`` ``assert_under_work`` check still runs to catch
         symlink races (a symlink dropped between resolve and mkdir).

    Raises HTTPException(400) on a malformed part, HTTPException(500) on
    symlink escape.
    """
    from uuid import uuid4

    if not parts:
        parts = (uuid4().hex,)
    for p in parts:
        if not isinstance(p, str) or not p:
            raise HTTPException(400, "Geçersiz iş klasörü parçası.")
        if "/" in p or "\\" in p or p in (".", ".."):
            raise HTTPException(400, "Geçersiz iş klasörü adı.")
    job_dir = WORK_DIR.joinpath(*parts)
    real_work = WORK_DIR.resolve()
    try:
        candidate = job_dir.resolve(strict=False)
    except (OSError, RuntimeError) as e:
        raise HTTPException(500, "Geçersiz iş klasörü.") from e
    if not candidate.is_relative_to(real_work):
        raise HTTPException(400, "Geçersiz iş klasörü adı.")
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
