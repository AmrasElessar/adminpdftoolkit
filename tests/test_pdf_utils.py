"""Tests for the Section A PDF utility helpers added in v1.1.

Covers both the core-level functions (``core.pdf_*``) and the FastAPI
endpoints they back (``/pdf/*``). All fixtures are generated in-memory with
PyMuPDF so the suite stays self-contained — no on-disk PDF samples needed.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

import app
import core


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Generate a 3-page PDF with simple text content."""
    out = tmp_path / "sample.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)  # A4 portrait
        page.insert_text((72, 100), f"Sayfa {i + 1} — Türkçe içerik", fontsize=14, fontname="helv")
    doc.save(str(out))
    doc.close()
    return out


@pytest.fixture
def sample_pdf_2(tmp_path: Path) -> Path:
    """A second 2-page PDF for merge tests."""
    out = tmp_path / "second.pdf"
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page()
        page.insert_text((72, 100), f"İkinci dosya — sayfa {i + 1}", fontsize=12, fontname="helv")
    doc.save(str(out))
    doc.close()
    return out


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """A 100x100 red PNG for watermark-image tests."""
    out = tmp_path / "logo.png"
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100))
    pix.set_rect(pix.irect, (255, 0, 0))
    pix.save(str(out))
    return out


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(core, "is_local_request", lambda req: True)
    monkeypatch.setattr("core.is_local_request", lambda req: True)
    return TestClient(app.app)


def _page_count(p: Path) -> int:
    with fitz.open(str(p)) as d:
        return d.page_count


# ---------------------------------------------------------------------------
# core.pdf_merge
# ---------------------------------------------------------------------------
def test_merge_concatenates_pages(sample_pdf: Path, sample_pdf_2: Path, tmp_path: Path) -> None:
    out = tmp_path / "merged.pdf"
    total = core.pdf_merge([sample_pdf, sample_pdf_2], out)
    assert total == 5
    assert _page_count(out) == 5


def test_merge_empty_input_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        core.pdf_merge([], tmp_path / "x.pdf")


# ---------------------------------------------------------------------------
# core.pdf_split
# ---------------------------------------------------------------------------
def test_split_per_page_default(sample_pdf: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    files = core.pdf_split(sample_pdf, out_dir)
    assert len(files) == 3
    for f in files:
        assert _page_count(f) == 1


def test_split_with_ranges(sample_pdf: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    files = core.pdf_split(sample_pdf, out_dir, ranges="1-2,3")
    assert len(files) == 2
    assert _page_count(files[0]) == 2  # pages 1-2
    assert _page_count(files[1]) == 1  # page 3


def test_split_invalid_range_raises(sample_pdf: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        core.pdf_split(sample_pdf, tmp_path / "out", ranges="1-99")


# ---------------------------------------------------------------------------
# core.pdf_compress
# ---------------------------------------------------------------------------
def test_compress_emits_pdf(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "compressed.pdf"
    before, after = core.pdf_compress(sample_pdf, out)
    assert out.exists()
    assert before > 0
    assert after > 0
    # Page count is preserved
    assert _page_count(out) == _page_count(sample_pdf)


# ---------------------------------------------------------------------------
# core.pdf_encrypt / pdf_decrypt round-trip
# ---------------------------------------------------------------------------
def test_encrypt_decrypt_roundtrip(sample_pdf: Path, tmp_path: Path) -> None:
    enc = tmp_path / "enc.pdf"
    core.pdf_encrypt(sample_pdf, enc, user_password="secret123")

    # Encrypted PDF must reject empty password
    with fitz.open(str(enc)) as d:
        assert d.is_encrypted
        assert not d.authenticate("")
        assert d.authenticate("secret123")

    dec = tmp_path / "dec.pdf"
    core.pdf_decrypt(enc, dec, password="secret123")
    with fitz.open(str(dec)) as d:
        assert not d.is_encrypted
        assert d.page_count == _page_count(sample_pdf)


def test_decrypt_wrong_password_raises(sample_pdf: Path, tmp_path: Path) -> None:
    enc = tmp_path / "enc.pdf"
    core.pdf_encrypt(sample_pdf, enc, user_password="abc")
    with pytest.raises(ValueError):
        core.pdf_decrypt(enc, tmp_path / "dec.pdf", password="wrong")


def test_encrypt_empty_password_raises(sample_pdf: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        core.pdf_encrypt(sample_pdf, tmp_path / "x.pdf", user_password="")


# ---------------------------------------------------------------------------
# core.pdf_watermark_text / pdf_watermark_image
# ---------------------------------------------------------------------------
def test_watermark_text_applied(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "wm.pdf"
    core.pdf_watermark_text(sample_pdf, out, text="GİZLİ", opacity=0.3)
    assert out.exists()
    # Page count preserved; content stream now contains our text marker
    with fitz.open(str(out)) as d:
        assert d.page_count == _page_count(sample_pdf)
        # At least one page should have the watermark text appearing in extract
        found = any("GİZLİ" in p.get_text() for p in d)
        assert found


def test_watermark_image_applied(sample_pdf: Path, sample_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "wm-img.pdf"
    core.pdf_watermark_image(sample_pdf, out, image_path=sample_image)
    assert out.exists()
    assert _page_count(out) == _page_count(sample_pdf)


# ---------------------------------------------------------------------------
# core.pdf_page_numbers / pdf_header_footer
# ---------------------------------------------------------------------------
def test_page_numbers_stamped(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "num.pdf"
    core.pdf_page_numbers(sample_pdf, out, fmt="Sayfa {n} / {total}")
    with fitz.open(str(out)) as d:
        text_all = "\n".join(p.get_text() for p in d)
    # PyMuPDF can emit non-breaking spaces (\xa0) when using a TTF — normalise
    normalised = text_all.replace("\xa0", " ")
    assert "Sayfa 1 / 3" in normalised
    assert "Sayfa 3 / 3" in normalised


def test_header_footer_stamped(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "hf.pdf"
    core.pdf_header_footer(sample_pdf, out, header="ÜST BİLGİ", footer="ALT BİLGİ")
    with fitz.open(str(out)) as d:
        text_all = "\n".join(p.get_text() for p in d)
    normalised = text_all.replace("\xa0", " ")
    assert "ÜST BİLGİ" in normalised
    assert "ALT BİLGİ" in normalised


def test_header_footer_both_empty_raises(sample_pdf: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        core.pdf_header_footer(sample_pdf, tmp_path / "x.pdf", header="", footer="")


# ---------------------------------------------------------------------------
# core.pdf_crop / pdf_rotate / pdf_reorder_pages / pdf_delete_pages
# ---------------------------------------------------------------------------
def test_crop_shrinks_cropbox(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "crop.pdf"
    core.pdf_crop(sample_pdf, out, top=20, bottom=20, left=20, right=20, unit="pt")
    with fitz.open(str(out)) as d:
        for page in d:
            cb = page.cropbox
            assert cb.width < page.mediabox.width
            assert cb.height < page.mediabox.height


def test_crop_zero_margins_raises(sample_pdf: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        core.pdf_crop(sample_pdf, tmp_path / "x.pdf")


def test_rotate_changes_rotation(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "rot.pdf"
    core.pdf_rotate(sample_pdf, out, angle=90)
    with fitz.open(str(out)) as d:
        for page in d:
            assert page.rotation == 90


def test_rotate_specific_pages(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "rot.pdf"
    core.pdf_rotate(sample_pdf, out, angle=180, pages=[2])
    with fitz.open(str(out)) as d:
        rotations = [p.rotation for p in d]
    assert rotations == [0, 180, 0]


def test_rotate_non_multiple_of_90_raises(sample_pdf: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        core.pdf_rotate(sample_pdf, tmp_path / "x.pdf", angle=45)


def test_reorder_pages(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "ord.pdf"
    core.pdf_reorder_pages(sample_pdf, out, order=[3, 1, 2])
    assert _page_count(out) == 3
    # Check first page text matches "Sayfa 3"
    with fitz.open(str(out)) as d:
        first_text = d[0].get_text()
    assert "Sayfa 3" in first_text


def test_reorder_can_drop_and_duplicate(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "ord.pdf"
    core.pdf_reorder_pages(sample_pdf, out, order=[1, 1, 3])
    assert _page_count(out) == 3


def test_reorder_invalid_page_raises(sample_pdf: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        core.pdf_reorder_pages(sample_pdf, tmp_path / "x.pdf", order=[1, 99])


def test_delete_pages(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "del.pdf"
    core.pdf_delete_pages(sample_pdf, out, pages=[2])
    assert _page_count(out) == 2


def test_delete_all_pages_raises(sample_pdf: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        core.pdf_delete_pages(sample_pdf, tmp_path / "x.pdf", pages=[1, 2, 3])


# ---------------------------------------------------------------------------
# Endpoint smoke tests via TestClient
# ---------------------------------------------------------------------------
def _pdf_bytes(pages: int = 2) -> bytes:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 100), f"Sayfa {i + 1}", fontsize=14, fontname="helv")
    buf = doc.tobytes()
    doc.close()
    return buf


def test_endpoint_merge(client: TestClient) -> None:
    a = _pdf_bytes(1)
    b = _pdf_bytes(2)
    r = client.post(
        "/pdf/merge",
        files=[
            ("files", ("a.pdf", a, "application/pdf")),
            ("files", ("b.pdf", b, "application/pdf")),
        ],
        data={"output_name": "birlesik"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    # Downloaded body is a valid PDF with 3 pages
    with fitz.open(stream=r.content, filetype="pdf") as d:
        assert d.page_count == 3


def test_endpoint_merge_too_few_files(client: TestClient) -> None:
    r = client.post(
        "/pdf/merge",
        files=[("files", ("a.pdf", _pdf_bytes(1), "application/pdf"))],
    )
    assert r.status_code == 400


def test_endpoint_split_zip(client: TestClient) -> None:
    r = client.post(
        "/pdf/split",
        files={"file": ("doc.pdf", _pdf_bytes(3), "application/pdf")},
        data={"ranges": "1,2-3"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert len(z.namelist()) == 2


def test_endpoint_compress_returns_size_headers(client: TestClient) -> None:
    r = client.post(
        "/pdf/compress",
        files={"file": ("doc.pdf", _pdf_bytes(2), "application/pdf")},
        data={"image_quality": "60"},
    )
    assert r.status_code == 200, r.text
    assert "X-Bytes-Before" in r.headers
    assert "X-Bytes-After" in r.headers


def test_endpoint_rotate(client: TestClient) -> None:
    r = client.post(
        "/pdf/rotate",
        files={"file": ("doc.pdf", _pdf_bytes(2), "application/pdf")},
        data={"angle": "90"},
    )
    assert r.status_code == 200
    with fitz.open(stream=r.content, filetype="pdf") as d:
        assert all(p.rotation == 90 for p in d)


def test_endpoint_reorder(client: TestClient) -> None:
    r = client.post(
        "/pdf/reorder",
        files={"file": ("doc.pdf", _pdf_bytes(3), "application/pdf")},
        data={"order": "3,1,2"},
    )
    assert r.status_code == 200
    with fitz.open(stream=r.content, filetype="pdf") as d:
        assert d.page_count == 3


def test_endpoint_delete_pages(client: TestClient) -> None:
    r = client.post(
        "/pdf/delete-pages",
        files={"file": ("doc.pdf", _pdf_bytes(4), "application/pdf")},
        data={"pages": "2,4"},
    )
    assert r.status_code == 200
    with fitz.open(stream=r.content, filetype="pdf") as d:
        assert d.page_count == 2


def test_endpoint_encrypt_then_decrypt(client: TestClient) -> None:
    src = _pdf_bytes(1)
    enc_resp = client.post(
        "/pdf/encrypt",
        files={"file": ("doc.pdf", src, "application/pdf")},
        data={"user_password": "p@ss"},
    )
    assert enc_resp.status_code == 200
    enc_bytes = enc_resp.content
    with fitz.open(stream=enc_bytes, filetype="pdf") as d:
        assert d.is_encrypted

    dec_resp = client.post(
        "/pdf/decrypt",
        files={"file": ("enc.pdf", enc_bytes, "application/pdf")},
        data={"password": "p@ss"},
    )
    assert dec_resp.status_code == 200
    with fitz.open(stream=dec_resp.content, filetype="pdf") as d:
        assert not d.is_encrypted


def test_endpoint_decrypt_wrong_password_400(client: TestClient) -> None:
    src = _pdf_bytes(1)
    enc_resp = client.post(
        "/pdf/encrypt",
        files={"file": ("doc.pdf", src, "application/pdf")},
        data={"user_password": "real"},
    )
    enc_bytes = enc_resp.content
    r = client.post(
        "/pdf/decrypt",
        files={"file": ("enc.pdf", enc_bytes, "application/pdf")},
        data={"password": "wrong"},
    )
    assert r.status_code == 400


def test_endpoint_watermark_text(client: TestClient) -> None:
    r = client.post(
        "/pdf/watermark-text",
        files={"file": ("doc.pdf", _pdf_bytes(1), "application/pdf")},
        data={"text": "ÖRNEK", "opacity": "0.3"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_endpoint_page_numbers(client: TestClient) -> None:
    r = client.post(
        "/pdf/page-numbers",
        files={"file": ("doc.pdf", _pdf_bytes(3), "application/pdf")},
        data={"position": "bottom-center", "fmt": "{n}/{total}"},
    )
    assert r.status_code == 200
    with fitz.open(stream=r.content, filetype="pdf") as d:
        text = "\n".join(p.get_text() for p in d)
    assert "1/3" in text
    assert "3/3" in text


def test_endpoint_crop(client: TestClient) -> None:
    r = client.post(
        "/pdf/crop",
        files={"file": ("doc.pdf", _pdf_bytes(1), "application/pdf")},
        data={"top": "10", "bottom": "10", "left": "10", "right": "10", "unit": "pt"},
    )
    assert r.status_code == 200


def test_endpoint_non_pdf_rejected(client: TestClient) -> None:
    r = client.post(
        "/pdf/compress",
        files={"file": ("doc.txt", b"not a pdf", "text/plain")},
    )
    assert r.status_code == 400
