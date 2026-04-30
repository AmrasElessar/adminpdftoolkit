"""PDF safety gate tests (S3).

Cover:
  - assert_safe respects HT_SAFETY_POLICY (off / warn / block_danger)
  - clamav_scan / pdfid_scan / mpcmdrun_scan handle missing tools gracefully
  - clamav_scan returns deterministic shape on TimeoutExpired
  - _gate_pdf_safety endpoint wrapper turns UnsafePDFError into HTTP 400
    with the X-Safety-Verdict response header
  - convert endpoint rejects a dangerous PDF (integration)
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

import pdf_safety
from pdf_safety import UnsafePDFError, assert_safe, clamav_scan, full_scan, pdfid_scan


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def clean_pdf(tmp_path: Path) -> Path:
    """Create a minimal text-only PDF with no suspicious markers."""
    pdf_path = tmp_path / "clean.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Plain harmless content.")
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def dangerous_pdf(tmp_path: Path) -> Path:
    """Build a PDF that ships a /JavaScript object so check_structure flags it."""
    pdf_path = tmp_path / "danger.pdf"
    # Manually construct a tiny PDF that includes uncompressed /JavaScript +
    # /OpenAction tokens. The structural scan reads raw bytes and does a
    # regex hunt, so we don't need a real interactive form.
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R "
        b"/OpenAction << /Type /Action /S /JavaScript /JS (app.alert(1);) >> "
        b">>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f\n"
        b"0000000010 00000 n\n"
        b"0000000130 00000 n\n"
        b"0000000180 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n240\n%%EOF\n"
    )
    pdf_path.write_bytes(body)
    return pdf_path


# ---------------------------------------------------------------------------
# assert_safe — policy switching
# ---------------------------------------------------------------------------
def test_assert_safe_clean_pdf_passes(clean_pdf: Path) -> None:
    scan = assert_safe(clean_pdf, policy="block_danger")
    assert scan["overall"] != "danger"


def test_assert_safe_dangerous_pdf_raises(dangerous_pdf: Path) -> None:
    with pytest.raises(UnsafePDFError) as exc:
        assert_safe(dangerous_pdf, policy="block_danger")
    assert exc.value.scan["overall"] == "danger"


def test_assert_safe_warn_policy_returns_even_when_dangerous(dangerous_pdf: Path) -> None:
    """policy='warn' surfaces verdict but never blocks the conversion."""
    scan = assert_safe(dangerous_pdf, policy="warn")
    assert scan["overall"] == "danger"
    assert scan["policy"] == "warn"


def test_assert_safe_off_policy_skips_scan(
    dangerous_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """policy='off' must short-circuit before calling full_scan."""
    called = {"n": 0}

    def boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("full_scan must not run when policy=off")

    monkeypatch.setattr(pdf_safety, "full_scan", boom)
    out = assert_safe(dangerous_pdf, policy="off")
    assert out["overall"] == "clean"
    assert out["policy"] == "off"
    assert called["n"] == 0


def test_assert_safe_uses_settings_when_policy_omitted(
    clean_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When policy=None, the live settings.safety_policy is consulted."""
    import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "safety_policy", "off")
    out = assert_safe(clean_pdf)  # no policy override
    assert out["policy"] == "off"


# ---------------------------------------------------------------------------
# clamav_scan / pdfid_scan / mpcmdrun_scan — missing tool fallback
# ---------------------------------------------------------------------------
def test_clamav_returns_none_when_missing(monkeypatch: pytest.MonkeyPatch, clean_pdf: Path) -> None:
    # Disable both the daemon path (clamd INSTREAM) and the standalone path —
    # this asserts the "no antivirus available at all" semantics.
    from core import clamav_daemon

    monkeypatch.setattr(pdf_safety, "_find_clamscan", lambda: None)
    monkeypatch.setattr(clamav_daemon, "is_ready", lambda: False)
    monkeypatch.setattr(clamav_daemon, "ensure_clamd_running", lambda **kw: False)
    assert clamav_scan(clean_pdf) is None


def test_pdfid_returns_none_when_missing(monkeypatch: pytest.MonkeyPatch, clean_pdf: Path) -> None:
    monkeypatch.setattr(pdf_safety, "_find_pdfid", lambda: None)
    assert pdfid_scan(clean_pdf) is None


def test_clamav_timeout_returns_unsafe(monkeypatch: pytest.MonkeyPatch, clean_pdf: Path) -> None:
    """A clamscan TimeoutExpired must not raise; it must return a structured
    dict so the caller can decide what to do."""
    from core import clamav_daemon

    # Disable daemon path so the standalone branch is exercised.
    monkeypatch.setattr(clamav_daemon, "is_ready", lambda: False)
    monkeypatch.setattr(clamav_daemon, "ensure_clamd_running", lambda **kw: False)
    monkeypatch.setattr(pdf_safety, "_find_clamscan", lambda: "clamscan")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="clamscan", timeout=60)

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = clamav_scan(clean_pdf, timeout=1)
    assert out is not None
    assert out["clean"] is False
    assert out["exit_code"] == -1


def test_clamav_malformed_output_does_not_crash(
    monkeypatch: pytest.MonkeyPatch, clean_pdf: Path
) -> None:
    """Garbage stdout is ignored; the scan resolves with the exit code."""
    from core import clamav_daemon

    # Disable daemon path so the standalone branch is exercised.
    monkeypatch.setattr(clamav_daemon, "is_ready", lambda: False)
    monkeypatch.setattr(clamav_daemon, "ensure_clamd_running", lambda **kw: False)
    monkeypatch.setattr(pdf_safety, "_find_clamscan", lambda: "clamscan")

    fake_result = SimpleNamespace(returncode=0, stdout="!!!nonsense!!!", stderr="")

    def fake_run(*args, **kwargs):
        return fake_result

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = clamav_scan(clean_pdf)
    assert out is not None
    assert out["clean"] is True
    assert out["threat"] is None


# ---------------------------------------------------------------------------
# full_scan structure
# ---------------------------------------------------------------------------
def test_full_scan_contains_expected_keys(clean_pdf: Path) -> None:
    scan = full_scan(clean_pdf)
    for key in ["overall", "structure", "antivirus", "av_available", "pdfid", "defender"]:
        assert key in scan


# ---------------------------------------------------------------------------
# Endpoint integration — gate returns 400 + X-Safety-Verdict
# ---------------------------------------------------------------------------
def test_convert_endpoint_rejects_dangerous_pdf(
    monkeypatch: pytest.MonkeyPatch, dangerous_pdf: Path
) -> None:
    """POST /convert with a /JavaScript-bearing PDF must return 400 + header."""
    from fastapi.testclient import TestClient

    import app
    import core

    monkeypatch.setattr(core, "is_local_request", lambda req: True)
    monkeypatch.setattr("core.is_local_request", lambda req: True)

    client = TestClient(app.app)
    response = client.post(
        "/convert",
        files={"file": (dangerous_pdf.name, dangerous_pdf.read_bytes(), "application/pdf")},
        data={"target": "word"},
    )
    assert response.status_code == 400, response.text
    assert response.headers.get("x-safety-verdict") == "danger"
    assert "Güvensiz" in response.json().get("detail", "")


def test_convert_endpoint_passes_clean_pdf_through_gate(
    monkeypatch: pytest.MonkeyPatch, clean_pdf: Path
) -> None:
    """Clean PDF must NOT be blocked by the safety gate (it may still fail
    later for unrelated reasons — we only check we cleared the gate)."""
    from fastapi.testclient import TestClient

    import app
    import core

    monkeypatch.setattr(core, "is_local_request", lambda req: True)
    monkeypatch.setattr("core.is_local_request", lambda req: True)

    client = TestClient(app.app)
    response = client.post(
        "/convert",
        files={"file": (clean_pdf.name, clean_pdf.read_bytes(), "application/pdf")},
        data={"target": "word"},
    )
    # The conversion may still fail for other reasons, but the safety verdict
    # header should NOT be 'danger'.
    assert response.headers.get("x-safety-verdict") != "danger"
