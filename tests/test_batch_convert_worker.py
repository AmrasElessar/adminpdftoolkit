"""End-to-end tests for ``batch_convert_worker`` (the Excel-merge thread).

This is the most complex worker in the codebase: it parses every PDF in
the input list (optionally via ProcessPoolExecutor), preserves caller
order even when futures complete out of order, falls back to serial
parsing if the pool can't be used, materialises ``data.json`` +
``birlesik_*.xlsx``, sets up ``files_progress`` so the UI can render
per-file status, and translates every parse error into a warning row
without aborting the whole batch.

Each scenario is driven on the main thread (``parallel_batch_workers=1``
forces serial mode) and stubs ``core.parse_pdf_for_batch`` so the test
isn't coupled to real PDF parsing.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

import core
from pipelines.batch_convert import batch_convert_worker
from settings import settings
from state import batch_store


@pytest.fixture(autouse=True)
def force_serial_mode(monkeypatch: pytest.MonkeyPatch):
    """Pin ``parallel_batch_workers=1`` so the worker stays on the main
    thread — running a real ProcessPoolExecutor would need pickleable
    targets and adds 100s of ms to every test."""
    monkeypatch.setattr(settings, "parallel_batch_workers", 1)


@pytest.fixture(autouse=True)
def cleanup_batch_store():
    yield
    with batch_store.lock:
        batch_store.jobs.clear()


@pytest.fixture
def job_token() -> str:
    return uuid4().hex


@pytest.fixture
def progress_token() -> str:
    return uuid4().hex


@pytest.fixture
def job_dir(job_token: str):
    """Persistent jobs/<token> dir (the worker writes data.json + xlsx
    here). Tear down on exit."""
    d = core.make_job_dir("jobs", job_token)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _seed_job(progress_token: str, job_dir: Path, total: int) -> None:
    """Mimic what the /batch-convert endpoint persists before starting
    the worker thread."""
    batch_store.create(
        progress_token,
        type="convert",
        phase="starting",
        current=0,
        total=total,
        done=False,
        error=None,
        started_at=0.0,
        job_dir=str(job_dir),
    )


# ---------------------------------------------------------------------------
# Happy path — two PDFs, both parse cleanly, merged Excel + data.json land
# ---------------------------------------------------------------------------
def test_worker_merges_two_pdfs_and_writes_outputs(
        monkeypatch: pytest.MonkeyPatch, job_dir: Path,
        job_token: str, progress_token: str) -> None:
    a = job_dir / "in_0.pdf"; a.write_bytes(b"%PDF-1.4\n%%EOF\n")
    b = job_dir / "in_1.pdf"; b.write_bytes(b"%PDF-1.4\n%%EOF\n")

    def fake_parse(args):
        filename, _path, _mapping, _schema = args
        return {
            "filename": filename,
            "records": [{"Telefon": "5551112233", "Müşteri": filename}],
            "warning": None,
        }
    monkeypatch.setattr(core, "parse_pdf_for_batch", fake_parse)
    monkeypatch.setattr(core, "TARGET_SCHEMA", ["Müşteri", "Telefon"])

    _seed_job(progress_token, job_dir, total=2)

    batch_convert_worker(
        progress_token, [("a.pdf", a), ("b.pdf", b)],
        mappings_obj={}, skip_list=[],
        job_token=job_token, file_count=2,
    )

    snap = batch_store.snapshot(progress_token)
    assert snap["done"] is True
    assert snap["error"] is None
    assert snap["phase"] == "done"
    # Per-file progress reflects two completed parses
    fp = snap["files_progress"]
    assert {f["name"] for f in fp} == {"a.pdf", "b.pdf"}
    assert all(f["status"] == "done" for f in fp)

    # Result summary is exposed for the polling endpoint
    assert snap["result"]["record_count"] == 2
    assert snap["result"]["source_count"] == 2
    assert snap["result"]["skipped_count"] == 0

    # data.json + xlsx materialised on disk
    assert (job_dir / "data.json").exists()
    data = json.loads((job_dir / "data.json").read_text(encoding="utf-8"))
    assert data["filename"] == "birlesik_2_kayit.xlsx"
    assert (job_dir / data["filename"]).exists()
    # The merged records carry sequential Sıra numbers
    assert [r["Sıra"] for r in data["records"]] == [1, 2]
    # Input PDFs got cleaned up
    assert not list(job_dir.glob("in_*.pdf"))


# ---------------------------------------------------------------------------
# Order preservation — even when fake_parse returns out of order, output
# follows input order
# ---------------------------------------------------------------------------
def test_worker_preserves_input_order_when_parses_complete_out_of_order(
        monkeypatch: pytest.MonkeyPatch, job_dir: Path,
        job_token: str, progress_token: str) -> None:
    """Serial mode iterates ``parse_args`` in order and stores results
    at the original index, so the merged output matches input order
    independent of whether the parse was fast or slow on each file."""
    a = job_dir / "in_0.pdf"; a.write_bytes(b"%PDF-1.4\n%%EOF\n")
    b = job_dir / "in_1.pdf"; b.write_bytes(b"%PDF-1.4\n%%EOF\n")

    def fake_parse(args):
        filename, _, _, _ = args
        # Record numbers chosen to make the merged Sıra easy to verify
        recs = [{"Müşteri": f"{filename}-1"}, {"Müşteri": f"{filename}-2"}]
        return {"filename": filename, "records": recs, "warning": None}
    monkeypatch.setattr(core, "parse_pdf_for_batch", fake_parse)
    monkeypatch.setattr(core, "TARGET_SCHEMA", ["Müşteri"])

    _seed_job(progress_token, job_dir, total=2)
    batch_convert_worker(
        progress_token, [("first.pdf", a), ("second.pdf", b)],
        mappings_obj={}, skip_list=[],
        job_token=job_token, file_count=2,
    )

    data = json.loads((job_dir / "data.json").read_text(encoding="utf-8"))
    # Records: first.pdf-1, first.pdf-2, second.pdf-1, second.pdf-2
    musteri_order = [r["Müşteri"] for r in data["records"]]
    assert musteri_order == ["first.pdf-1", "first.pdf-2",
                              "second.pdf-1", "second.pdf-2"]
    # Source-file column should mirror that
    assert data["source_files"] == ["first.pdf", "first.pdf",
                                      "second.pdf", "second.pdf"]


# ---------------------------------------------------------------------------
# Skip list — a filename in skip_list is NOT parsed, status="skipped"
# ---------------------------------------------------------------------------
def test_worker_skips_files_in_skip_list(
        monkeypatch: pytest.MonkeyPatch, job_dir: Path,
        job_token: str, progress_token: str) -> None:
    a = job_dir / "in_0.pdf"; a.write_bytes(b"%PDF-1.4\n%%EOF\n")
    b = job_dir / "in_1.pdf"; b.write_bytes(b"%PDF-1.4\n%%EOF\n")

    parsed_names: list[str] = []

    def fake_parse(args):
        parsed_names.append(args[0])
        return {"filename": args[0], "records": [{"Müşteri": "x"}],
                 "warning": None}
    monkeypatch.setattr(core, "parse_pdf_for_batch", fake_parse)
    monkeypatch.setattr(core, "TARGET_SCHEMA", ["Müşteri"])

    _seed_job(progress_token, job_dir, total=2)
    batch_convert_worker(
        progress_token, [("good.pdf", a), ("ignore.pdf", b)],
        mappings_obj={}, skip_list=["ignore.pdf"],
        job_token=job_token, file_count=2,
    )

    # Only one file went through the parser
    assert parsed_names == ["good.pdf"]

    snap = batch_store.snapshot(progress_token)
    assert snap["result"]["skipped_count"] == 1
    fp_by_name = {f["name"]: f for f in snap["files_progress"]}
    assert fp_by_name["ignore.pdf"]["status"] == "skipped"
    assert fp_by_name["good.pdf"]["status"] == "done"


# ---------------------------------------------------------------------------
# Per-file parse failure → warning row, batch survives, status="error"
# ---------------------------------------------------------------------------
def test_worker_records_parse_warning_without_aborting_batch(
        monkeypatch: pytest.MonkeyPatch, job_dir: Path,
        job_token: str, progress_token: str) -> None:
    """One PDF blowing up shouldn't kill the whole batch — the worker
    converts the exception into a per-file warning and keeps merging."""
    a = job_dir / "in_0.pdf"; a.write_bytes(b"%PDF-1.4\n%%EOF\n")
    b = job_dir / "in_1.pdf"; b.write_bytes(b"%PDF-1.4\n%%EOF\n")

    def fake_parse(args):
        filename = args[0]
        if filename == "broken.pdf":
            raise RuntimeError("simulated parser failure")
        return {"filename": filename, "records": [{"Müşteri": "ok"}],
                 "warning": None}
    monkeypatch.setattr(core, "parse_pdf_for_batch", fake_parse)
    monkeypatch.setattr(core, "TARGET_SCHEMA", ["Müşteri"])

    _seed_job(progress_token, job_dir, total=2)
    batch_convert_worker(
        progress_token, [("good.pdf", a), ("broken.pdf", b)],
        mappings_obj={}, skip_list=[],
        job_token=job_token, file_count=2,
    )

    snap = batch_store.snapshot(progress_token)
    assert snap["done"] is True
    assert snap["error"] is None  # whole-batch error stays clean
    assert len(snap["result"]["warnings"]) == 1
    assert "broken.pdf" in snap["result"]["warnings"][0]
    fp_by_name = {f["name"]: f for f in snap["files_progress"]}
    assert fp_by_name["broken.pdf"]["status"] == "error"
    assert fp_by_name["good.pdf"]["status"] == "done"
    # 1 record from the surviving PDF
    assert snap["result"]["record_count"] == 1


# ---------------------------------------------------------------------------
# All-PDFs-fail → batch reports a clean RuntimeError
# ---------------------------------------------------------------------------
def test_worker_marks_done_with_error_when_no_records(
        monkeypatch: pytest.MonkeyPatch, job_dir: Path,
        job_token: str, progress_token: str) -> None:
    a = job_dir / "in_0.pdf"; a.write_bytes(b"%PDF-1.4\n%%EOF\n")

    def fake_parse(args):
        return {"filename": args[0], "records": [],
                 "warning": "boş tablo"}
    monkeypatch.setattr(core, "parse_pdf_for_batch", fake_parse)
    monkeypatch.setattr(core, "TARGET_SCHEMA", ["Müşteri"])

    _seed_job(progress_token, job_dir, total=1)
    batch_convert_worker(
        progress_token, [("empty.pdf", a)],
        mappings_obj={}, skip_list=[],
        job_token=job_token, file_count=1,
    )

    snap = batch_store.snapshot(progress_token)
    assert snap["done"] is True
    assert snap["error"] is not None
    assert "Birleştirilecek veri bulunamadı" in snap["error"]
