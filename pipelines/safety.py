"""Safety scanning helper used by convert / batch / batch_convert workers.

The synchronous ``gate_pdf_safety`` call is too slow to run inside the HTTP
request handler — for batches it can add 10-30 s before the worker thread
even starts. Workers call :func:`scan_files_with_progress` instead, which
emits per-file ``phase="scanning"`` progress and respects two flags on the
store so the user can drive the scan in flight:

* ``skip_safety`` — user clicked "Atla & Dönüştür" (or "Yine de Dönüştür"
  on the danger modal). Remaining files are marked skipped; the currently
  flagged dangerous file is added to ``unsafe_files`` so the downstream
  worker can stamp the output as GÜVENSİZ.
* ``cancel_safety`` — user clicked "İptal" on the danger modal. Scanning
  stops and the worker reports an error.

When a file is rejected, the pipeline does NOT immediately fail — it sets
``phase="danger_review"`` and waits for one of those flags to be set (or a
5 minute timeout). This is what lets the frontend show a "Yine de
dönüştür / İptal" modal instead of forcing a hard refusal.

Files are scanned in parallel (4 workers) — ClamAV's per-file scan over
INSTREAM is ~500-1000ms and clamd handles concurrent sockets natively, so
parallelising drops a 16-file batch from ~15 s down to ~1-2 s. Danger
reviews are serialised via a lock so the user sees one modal at a time.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app_http import gate_pdf_safety
from pdf_safety import UnsafePDFError, full_scan

# How long to wait (seconds) on the danger modal before giving up.
_DANGER_REVIEW_TIMEOUT_S = 300.0
# Poll cadence while waiting for the user decision.
_DANGER_POLL_INTERVAL_S = 0.5
# How many files to scan concurrently. ClamAV daemon is multi-threaded;
# 4 fits comfortably on typical office hardware and gives ~4x throughput.
_SCAN_PARALLELISM = 4


def _wait_for_decision(store: Any, token: str) -> str:
    """Block until user clicks "Atla" / "İptal" on the danger modal.

    Returns ``"skip"`` if the user wants to proceed anyway,
    ``"cancel"`` if they cancelled, or ``"timeout"`` after
    ``_DANGER_REVIEW_TIMEOUT_S`` seconds with no decision.
    """
    started = time.monotonic()
    while time.monotonic() - started < _DANGER_REVIEW_TIMEOUT_S:
        snap = store.snapshot(token)
        if not snap:
            return "cancel"
        if snap.get("cancel_safety"):
            return "cancel"
        if snap.get("skip_safety"):
            return "skip"
        time.sleep(_DANGER_POLL_INTERVAL_S)
    return "timeout"


def _findings_summary(detail: str) -> str:
    """Pull the parenthesised finding list out of ``gate_pdf_safety``'s detail
    message — used to show "/JavaScript, /Launch" on the danger modal.
    Falls back to the raw detail when the format is unexpected.
    """
    try:
        start = detail.index("bulgular:") + len("bulgular:")
        end = detail.index(")", start)
        return detail[start:end].strip().rstrip(".")
    except ValueError:
        return detail


def scan_files_with_progress(
    store: Any,
    token: str,
    files: list[tuple[str, Path]],
) -> tuple[bool, str | None]:
    """Run ``gate_pdf_safety`` on every file in parallel, emit progress.

    Returns ``(ok, error_message)``:
        ``ok=True`` when every file passed, was user-skipped, or was
            user-accepted as unsafe. Accepted-unsafe filenames are appended
            to the store's ``unsafe_files`` list so the worker can stamp
            outputs as GÜVENSİZ later.
        ``ok=False`` and ``error_message`` set when the user cancelled the
            danger modal (or the review timed out).
    """
    files_safety: list[dict[str, Any]] = [
        {"name": name, "status": "pending"} for name, _ in files
    ]
    store.update(
        token,
        phase="scanning",
        current=0,
        total=len(files),
        files_safety=files_safety,
        unsafe_files=[],
    )

    # Coordination primitives shared across worker threads.
    # ``files_safety`` is mutated by workers; the JobStore lock keeps the
    # ``update`` calls atomic, but we add a python lock for our local
    # bookkeeping (progress counter + danger review serialisation).
    state_lock = threading.Lock()
    danger_lock = threading.Lock()  # only one danger modal at a time
    progress = {"done": 0}
    unsafe_files: list[str] = []
    cancelled: dict[str, Any] = {"flag": False, "reason": ""}

    def _bump_progress(filename: str | None = None) -> None:
        with state_lock:
            progress["done"] += 1
            done = progress["done"]
        store.update(
            token,
            current=done,
            last_file=filename,
            files_safety=files_safety,
        )

    def _scan_one(idx: int, filename: str, path: Path) -> None:
        # Quick exit if the batch was already cancelled or globally skipped.
        snap = store.snapshot(token)
        if snap and snap.get("cancel_safety"):
            files_safety[idx]["status"] = "skipped"
            _bump_progress(filename)
            return
        if snap and snap.get("skip_safety"):
            files_safety[idx]["status"] = "skipped"
            _bump_progress(filename)
            return

        files_safety[idx]["status"] = "scanning"
        store.update(token, last_file=filename, files_safety=files_safety)

        try:
            gate_pdf_safety(path)
            files_safety[idx]["status"] = "clean"
            _bump_progress(filename)
            return
        except HTTPException as e:
            # Found a dangerous file. Acquire danger_lock so we never show
            # two modals at once — if another thread is mid-review, queue.
            findings = _findings_summary(str(e.detail))
            with danger_lock:
                # While we were waiting for the lock, the user may have
                # already accepted/cancelled a previous danger. Check before
                # re-prompting.
                snap2 = store.snapshot(token) or {}
                if snap2.get("cancel_safety"):
                    cancelled["flag"] = True
                    cancelled["reason"] = f"İptal edildi — {filename}: {findings}"
                    files_safety[idx]["status"] = "skipped"
                    _bump_progress(filename)
                    return
                if snap2.get("skip_safety"):
                    # User globally accepted unsafe earlier; auto-accept this one.
                    with state_lock:
                        unsafe_files.append(filename)
                    files_safety[idx]["status"] = "danger_accepted"
                    _bump_progress(filename)
                    return

                # Show modal for THIS file.
                files_safety[idx]["status"] = "danger"
                store.update(
                    token,
                    files_safety=files_safety,
                    phase="danger_review",
                    danger_file=filename,
                    danger_detail=str(e.detail),
                    danger_findings=findings,
                )
                decision = _wait_for_decision(store, token)
                if decision == "skip":
                    with state_lock:
                        unsafe_files.append(filename)
                    files_safety[idx]["status"] = "danger_accepted"
                    store.update(
                        token,
                        files_safety=files_safety,
                        phase="scanning",
                        danger_file=None,
                        danger_detail=None,
                        danger_findings=None,
                    )
                    _bump_progress(filename)
                    return
                # cancel or timeout
                cancelled["flag"] = True
                cancelled["reason"] = (
                    f"İptal edildi — {filename}: {findings}"
                    if decision == "cancel"
                    else f"Karar bekleme süresi doldu — {filename}: {findings}"
                )
                _bump_progress(filename)
                return

    with ThreadPoolExecutor(max_workers=_SCAN_PARALLELISM) as pool:
        futures = [
            pool.submit(_scan_one, i, fn, path) for i, (fn, path) in enumerate(files)
        ]
        for fut in as_completed(futures):
            # Surface unexpected exceptions; user-cancelled is handled via
            # the ``cancelled`` dict, not exceptions.
            fut.result()

    # Push accumulated unsafe_files in one go (avoids racing partial updates).
    store.update(token, unsafe_files=list(unsafe_files), files_safety=files_safety)

    if cancelled["flag"]:
        reason = str(cancelled["reason"]) if cancelled["reason"] else ""
        return False, reason or "Güvenlik taraması iptal edildi."
    return True, None


def scan_single_file(
    store: Any,
    token: str,
    path: Path,
    filename: str,
) -> tuple[bool, str | None]:
    """Convenience wrapper for single-PDF convert workers."""
    return scan_files_with_progress(store, token, [(filename, path)])


__all__ = ["UnsafePDFError", "full_scan", "scan_files_with_progress", "scan_single_file"]
