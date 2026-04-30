"""Safety scanning helper used by convert / batch / batch_convert workers.

The synchronous ``gate_pdf_safety`` call is too slow to run inside the HTTP
request handler — for batches it can add 10-30 s before the worker thread
even starts. Workers call :func:`scan_files_with_progress` instead, which
emits per-file ``phase="scanning"`` progress and respects an in-store
``skip_safety`` flag so the user can abort scanning mid-flight.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app_http import gate_pdf_safety


def scan_files_with_progress(
    store: Any,
    token: str,
    files: list[tuple[str, Path]],
) -> tuple[bool, str | None]:
    """Run ``gate_pdf_safety`` on each file, emitting scanning progress.

    Returns ``(ok, error_message)``:
        ``ok=True`` when all files passed (or user skipped via the
        ``skip_safety`` flag set on the store).
        ``ok=False`` and ``error_message`` set when a file is rejected
        and the user has NOT requested skip.

    The store is expected to support ``snapshot(token)`` and ``update(token, ...)``.
    Per-file scan progress is recorded under ``files_safety`` (a list of
    dicts) so the frontend can show which file is currently being scanned.
    """
    files_safety: list[dict[str, Any]] = [{"name": name, "status": "pending"} for name, _ in files]
    store.update(
        token,
        phase="scanning",
        current=0,
        total=len(files),
        files_safety=files_safety,
    )

    for i, (filename, path) in enumerate(files):
        # Check skip flag BEFORE starting next file scan
        snap = store.snapshot(token)
        if snap and snap.get("skip_safety"):
            for j in range(i, len(files)):
                files_safety[j]["status"] = "skipped"
            store.update(token, files_safety=files_safety, current=len(files))
            return True, None

        files_safety[i]["status"] = "scanning"
        store.update(token, current=i, last_file=filename, files_safety=files_safety)

        try:
            gate_pdf_safety(path)
            files_safety[i]["status"] = "clean"
        except HTTPException as e:
            # Re-check skip flag — user may have clicked "Atla" while scan was
            # running. If so, treat this file as skipped and continue.
            snap2 = store.snapshot(token)
            if snap2 and snap2.get("skip_safety"):
                files_safety[i]["status"] = "skipped"
                for j in range(i + 1, len(files)):
                    files_safety[j]["status"] = "skipped"
                store.update(token, files_safety=files_safety, current=len(files))
                return True, None
            files_safety[i]["status"] = "danger"
            store.update(token, files_safety=files_safety, current=i + 1)
            return False, f"{filename}: {e.detail}"

        # Bitti — current'ı bir sonraki başlangıç sayacına çıkar (yüzde gösterimi için)
        store.update(token, files_safety=files_safety, current=i + 1)

    store.update(token, current=len(files))
    return True, None


def scan_single_file(
    store: Any,
    token: str,
    path: Path,
    filename: str,
) -> tuple[bool, str | None]:
    """Convenience wrapper for single-PDF convert workers."""
    return scan_files_with_progress(store, token, [(filename, path)])
