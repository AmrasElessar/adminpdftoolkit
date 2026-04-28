"""Unit tests for ``app_http`` — the helper module shared by every router.

These helpers are pure (parse_color / parse_int_list) or thin
boundary-glue (gate_pdf_safety / pdf_job_dir / cleanup_task /
save_pdf_upload / pdf_response / file_response_with_name). The router
files lean on them on every request, so a regression here breaks
everything at once — these tests pin the contract.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import fitz
import pytest
from fastapi import HTTPException, UploadFile

import app_http
from app_http import (
    cleanup_task,
    file_response_with_name,
    gate_pdf_safety,
    parse_color,
    parse_int_list,
    pdf_job_dir,
    pdf_response,
    save_pdf_upload,
)


# ---------------------------------------------------------------------------
# parse_color — hex / r,g,b (0-255 or 0-1) / fallback to default
# ---------------------------------------------------------------------------
def test_parse_color_hex_uppercase() -> None:
    assert parse_color("#FF8000", (1, 1, 1)) == pytest.approx((1.0, 0x80 / 255.0, 0.0))


def test_parse_color_hex_lowercase() -> None:
    assert parse_color("#80c0ff", (0, 0, 0)) == pytest.approx((128 / 255, 192 / 255, 1.0))


def test_parse_color_rgb_0_255() -> None:
    r, g, b = parse_color("255, 128, 0", (0.5, 0.5, 0.5))
    assert (r, g, b) == pytest.approx((1.0, 128 / 255, 0.0))


def test_parse_color_rgb_0_1_passthrough() -> None:
    """Any component > 1 forces 0-255 normalisation; if all are <= 1 we
    treat the input as already-normalised floats."""
    assert parse_color("0.25, 0.5, 0.75", (0, 0, 0)) == pytest.approx((0.25, 0.5, 0.75))


def test_parse_color_empty_uses_default() -> None:
    assert parse_color("", (0.1, 0.2, 0.3)) == (0.1, 0.2, 0.3)


def test_parse_color_whitespace_uses_default() -> None:
    assert parse_color("   ", (0.4, 0.5, 0.6)) == (0.4, 0.5, 0.6)


def test_parse_color_malformed_hex_uses_default() -> None:
    # 4-char hex isn't supported — falls back
    assert parse_color("#abc", (0.7, 0.8, 0.9)) == (0.7, 0.8, 0.9)


def test_parse_color_two_components_uses_default() -> None:
    assert parse_color("1,2", (0, 0, 0)) == (0, 0, 0)


def test_parse_color_non_numeric_uses_default() -> None:
    assert parse_color("red", (0, 0, 0)) == (0, 0, 0)


# ---------------------------------------------------------------------------
# parse_int_list — singletons / ranges / empty / errors
# ---------------------------------------------------------------------------
def test_parse_int_list_mix_of_singletons_and_ranges() -> None:
    assert parse_int_list("1,3,5-7") == [1, 3, 5, 6, 7]


def test_parse_int_list_empty_returns_empty() -> None:
    assert parse_int_list("") == []


def test_parse_int_list_whitespace_only_returns_empty() -> None:
    assert parse_int_list("   ,  ,") == []


def test_parse_int_list_reversed_range_swaps() -> None:
    assert parse_int_list("7-5") == [5, 6, 7]


def test_parse_int_list_single_page_range() -> None:
    assert parse_int_list("4-4") == [4]


def test_parse_int_list_invalid_int_raises_400() -> None:
    with pytest.raises(HTTPException) as exc:
        parse_int_list("abc")
    assert exc.value.status_code == 400


def test_parse_int_list_invalid_range_raises_400() -> None:
    with pytest.raises(HTTPException) as exc:
        parse_int_list("1-x")
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# gate_pdf_safety — wraps UnsafePDFError into HTTP 400 with X-Safety-Verdict
# ---------------------------------------------------------------------------
def test_gate_pdf_safety_passes_clean_pdf(tmp_path: Path) -> None:
    """A boring text-only PDF must clear the gate without raising."""
    p = tmp_path / "ok.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "harmless")
    doc.save(str(p)); doc.close()
    # No exception is the assertion.
    gate_pdf_safety(p)


def test_gate_pdf_safety_translates_unsafe_to_http_400(monkeypatch: pytest.MonkeyPatch,
                                                        tmp_path: Path) -> None:
    """Inject a stub that always raises UnsafePDFError; the helper must
    emit HTTPException(400) with the verdict in a response header."""
    from pdf_safety import UnsafePDFError

    fake_scan = {
        "overall": "danger",
        "structure": {
            "findings": [
                {"label": "javascript_open_action", "severity": "danger"},
            ],
        },
    }

    def _raise(_path: Path) -> None:
        raise UnsafePDFError(fake_scan)

    monkeypatch.setattr(app_http, "_pdf_assert_safe", _raise)

    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    with pytest.raises(HTTPException) as exc:
        gate_pdf_safety(pdf)
    assert exc.value.status_code == 400
    assert exc.value.headers["X-Safety-Verdict"] == "danger"
    assert "Güvensiz" in exc.value.detail
    assert "javascript_open_action" in exc.value.detail


# ---------------------------------------------------------------------------
# pdf_job_dir + cleanup_task — directory lifecycle
# ---------------------------------------------------------------------------
def test_pdf_job_dir_creates_unique_dirs() -> None:
    a = pdf_job_dir()
    b = pdf_job_dir()
    try:
        assert a.is_dir() and b.is_dir()
        assert a != b
    finally:
        import shutil
        shutil.rmtree(a, ignore_errors=True)
        shutil.rmtree(b, ignore_errors=True)


def test_cleanup_task_removes_dir() -> None:
    job_dir = pdf_job_dir()
    (job_dir / "scratch.txt").write_text("temp")
    task = cleanup_task(job_dir)
    # Run the BackgroundTask synchronously
    asyncio.run(task())
    assert not job_dir.exists()


def test_cleanup_task_silent_on_missing_dir(tmp_path: Path) -> None:
    """``shutil.rmtree(..., ignore_errors=True)`` swallows missing-path
    errors so the FileResponse send isn't sabotaged when the worker has
    already cleaned up the dir itself."""
    ghost = tmp_path / "never-existed"
    asyncio.run(cleanup_task(ghost)())  # no exception


# ---------------------------------------------------------------------------
# save_pdf_upload — extension + size enforcement
# ---------------------------------------------------------------------------
def _make_upload(filename: str, payload: bytes) -> UploadFile:
    """Build an UploadFile that streams ``payload`` once via ``read``."""
    import io
    return UploadFile(filename=filename, file=io.BytesIO(payload))


def test_save_pdf_upload_writes_bytes(tmp_path: Path) -> None:
    dest = tmp_path / "out.pdf"
    up = _make_upload("input.pdf", b"%PDF-1.4\nhello\n%%EOF\n")
    asyncio.run(save_pdf_upload(up, dest))
    assert dest.read_bytes().startswith(b"%PDF-1.4")


def test_save_pdf_upload_rejects_non_pdf_extension(tmp_path: Path) -> None:
    dest = tmp_path / "out.pdf"
    up = _make_upload("input.exe", b"MZ")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(save_pdf_upload(up, dest))
    assert exc.value.status_code == 400


def test_save_pdf_upload_rejects_missing_filename(tmp_path: Path) -> None:
    dest = tmp_path / "out.pdf"
    up = _make_upload("", b"x")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(save_pdf_upload(up, dest))
    assert exc.value.status_code == 400


def test_save_pdf_upload_rejects_oversize(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin MAX_UPLOAD_MB to 0 so any payload trips the 413."""
    monkeypatch.setattr(app_http, "MAX_UPLOAD_MB", 0)
    dest = tmp_path / "out.pdf"
    up = _make_upload("big.pdf", b"%PDF-1.4\n" + b"X" * 1024)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(save_pdf_upload(up, dest))
    assert exc.value.status_code == 413


# ---------------------------------------------------------------------------
# pdf_response / file_response_with_name — Content-Disposition encoding
# ---------------------------------------------------------------------------
def test_pdf_response_uses_utf8_filename_star(tmp_path: Path) -> None:
    """Non-ASCII names must round-trip via the RFC 5987 ``filename*=UTF-8''``
    parameter so mobile browsers don't get a mangled file name."""
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF-1.4\n%%EOF\n")
    job_dir = tmp_path
    resp = pdf_response(p, "çağrı kayıtları.pdf", job_dir)
    cd = resp.headers["content-disposition"]
    assert "filename*=UTF-8''" in cd
    assert resp.media_type == "application/pdf"


def test_pdf_response_force_pdf_extension(tmp_path: Path) -> None:
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF-1.4\n%%EOF\n")
    resp = pdf_response(p, "no_ext_name", tmp_path)
    cd = resp.headers["content-disposition"]
    # The filename in the disposition must include the .pdf suffix even
    # when the caller forgot it.
    assert ".pdf" in cd


def test_file_response_with_name_uses_caller_media_type(tmp_path: Path) -> None:
    p = tmp_path / "out.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    resp = file_response_with_name(p, "tablo.csv", "text/csv", tmp_path)
    assert resp.media_type == "text/csv"
    assert "filename*=UTF-8''" in resp.headers["content-disposition"]
