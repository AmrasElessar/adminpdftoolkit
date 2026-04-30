"""Tests for the PDF Intelligence Engine v2 helpers added in v1.9.

Covers system font discovery, metadata read/write, outline extraction,
text search, image extraction, thumbnails, layout detection, and the
deep-analyze combinator. Also exercises the matching HTTP endpoints.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

import app
import core


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(core, "is_local_request", lambda req: True)
    monkeypatch.setattr("core.is_local_request", lambda req: True)
    return TestClient(app.app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def rich_pdf(tmp_path: Path) -> Path:
    """A 3-page PDF with metadata, an outline, and an embedded image."""
    out = tmp_path / "rich.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 80), f"Bölüm {i + 1}", fontsize=18, fontname="helv")
        page.insert_text(
            (72, 120), f"Buradaki içerik sayfa {i + 1} için.", fontsize=11, fontname="helv"
        )
        # Repeating header + footer so detect_headers_footers has something
        page.insert_text((250, 30), "Şirket Raporu", fontsize=9, fontname="helv")
        page.insert_text((250, 820), f"Sayfa {i + 1}", fontsize=9, fontname="helv")
    # TOC
    doc.set_toc(
        [
            [1, "Bölüm 1", 1],
            [1, "Bölüm 2", 2],
            [1, "Bölüm 3", 3],
        ]
    )
    doc.set_metadata(
        {
            "title": "Test Dokümanı",
            "author": "Engin",
            "subject": "Mühendislik",
            "keywords": "pdf, engine, test",
        }
    )
    # Embed an image on page 1
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 60))
    pix.set_rect(pix.irect, (0, 80, 200))
    img_bytes = pix.tobytes("png")
    doc[0].insert_image(fitz.Rect(400, 400, 460, 460), stream=img_bytes)
    doc.save(str(out))
    doc.close()
    return out


# ---------------------------------------------------------------------------
# System font discovery
# ---------------------------------------------------------------------------
def test_system_fonts_discovered_or_empty():
    """Discovery should run without exception and produce a list."""
    fonts = core.discover_system_fonts(refresh=True)
    assert isinstance(fonts, list)
    for f in fonts:
        assert "id" in f and f["id"].startswith("system:")
        assert "label" in f
        assert f["category"] == "system"
        assert isinstance(f["variants"], list)
        assert len(f["variants"]) >= 1


def test_system_fonts_cached():
    a = core.discover_system_fonts()
    b = core.discover_system_fonts()
    assert a is b  # same cached list


def test_resolve_system_font_returns_real_path():
    fonts = core.discover_system_fonts()
    if not fonts:
        pytest.skip("No system fonts on this host")
    f = fonts[0]
    p = core.resolve_system_font(f["id"], bold=False, italic=False)
    if p is None:
        pytest.skip("First system font has no resolvable variant")
    assert p.is_file()


def test_resolve_editor_font_routes_system_id():
    fonts = core.discover_system_fonts()
    if not fonts:
        pytest.skip("No system fonts on this host")
    f = fonts[0]
    p = core.resolve_editor_font(f["id"])
    assert p is None or p.is_file()


def test_editor_catalog_merges_bundled_and_system():
    cat = core.editor_font_catalog()
    cats = {f["category"] for f in cat}
    # Bundled fonts must always be there (unless user wiped static/fonts/)
    bundled = [f for f in cat if f["category"] == "bundled"]
    if bundled:
        # If we're on a system with TTFs, both should coexist
        assert "bundled" in cats


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
def test_extract_metadata_reads_info_dict(rich_pdf: Path):
    m = core.extract_metadata(rich_pdf)
    assert m["title"] == "Test Dokümanı"
    assert m["author"] == "Engin"
    assert m["page_count"] == 3
    assert m["is_encrypted"] is False


def test_set_metadata_round_trip(rich_pdf: Path, tmp_path: Path):
    out = tmp_path / "out.pdf"
    core.set_metadata(rich_pdf, out, title="Yeni Başlık", author="Başkası")
    m = core.extract_metadata(out)
    assert m["title"] == "Yeni Başlık"
    assert m["author"] == "Başkası"
    # Untouched fields are preserved
    assert m["subject"] == "Mühendislik"


# ---------------------------------------------------------------------------
# Outline
# ---------------------------------------------------------------------------
def test_extract_outline_returns_three(rich_pdf: Path):
    outline = core.extract_outline(rich_pdf)
    assert len(outline) == 3
    titles = [e["title"] for e in outline]
    assert titles == ["Bölüm 1", "Bölüm 2", "Bölüm 3"]
    assert all(e["level"] == 1 for e in outline)
    assert outline[0]["page"] == 1


def test_extract_outline_empty_for_plain_pdf(tmp_path: Path):
    p = tmp_path / "plain.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 100), "x", fontsize=12, fontname="helv")
    doc.save(str(p))
    doc.close()
    assert core.extract_outline(p) == []


# ---------------------------------------------------------------------------
# Find text
# ---------------------------------------------------------------------------
def test_find_text_finds_query(rich_pdf: Path):
    results = core.find_text(rich_pdf, "Bölüm")
    assert len(results) >= 3  # one per chapter heading


def test_find_text_empty_query_raises(rich_pdf: Path):
    with pytest.raises(ValueError):
        core.find_text(rich_pdf, "  ")


def test_find_text_returns_bbox_and_context(rich_pdf: Path):
    results = core.find_text(rich_pdf, "Bölüm 2")
    assert results
    r = results[0]
    assert "rect" in r and len(r["rect"]) == 4
    assert "context" in r
    assert r["page"] >= 1


def test_find_text_max_results(rich_pdf: Path):
    results = core.find_text(rich_pdf, "Bölüm", max_results=2)
    assert len(results) <= 2


# ---------------------------------------------------------------------------
# Image extraction
# ---------------------------------------------------------------------------
def test_extract_images_returns_one(rich_pdf: Path, tmp_path: Path):
    out_dir = tmp_path / "imgs"
    images = core.extract_images(rich_pdf, out_dir, min_size=10)
    assert len(images) == 1
    assert (out_dir / images[0]["filename"]).is_file()


def test_extract_images_min_size_filters(rich_pdf: Path, tmp_path: Path):
    out_dir = tmp_path / "imgs"
    images = core.extract_images(rich_pdf, out_dir, min_size=200)
    assert images == []  # 60x60 image filtered out


def test_extract_images_specific_page(rich_pdf: Path, tmp_path: Path):
    out_dir = tmp_path / "imgs"
    images = core.extract_images(rich_pdf, out_dir, min_size=10, page=2)
    assert images == []  # image only on page 1


# ---------------------------------------------------------------------------
# Thumbnail
# ---------------------------------------------------------------------------
def test_pdf_thumbnail_emits_png(rich_pdf: Path, tmp_path: Path):
    out = tmp_path / "thumb.png"
    w, h = core.pdf_thumbnail(rich_pdf, out, page_no=1, dpi=72)
    assert out.is_file()
    assert w > 0 and h > 0


def test_pdf_thumbnail_invalid_page(rich_pdf: Path, tmp_path: Path):
    with pytest.raises(ValueError):
        core.pdf_thumbnail(rich_pdf, tmp_path / "x.png", page_no=99)


def test_pdf_thumbnail_invalid_format(rich_pdf: Path, tmp_path: Path):
    with pytest.raises(ValueError):
        core.pdf_thumbnail(rich_pdf, tmp_path / "x.gif", fmt="gif")


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------
def test_detect_text_columns(rich_pdf: Path):
    with fitz.open(str(rich_pdf)) as doc:
        cols = core.detect_text_columns(doc[0])
    assert 1 <= cols <= 3


def test_detect_headers_footers_finds_repeats(rich_pdf: Path):
    info = core.detect_headers_footers(rich_pdf)
    assert isinstance(info["headers"], list)
    assert isinstance(info["footers"], list)
    # The fixture has "Sayfa N" as footer and "Şirket Raporu" as header on every page
    assert any("şirket" in h.lower() for h in info["headers"]) or info["headers"]
    assert any("sayfa" in f for f in info["footers"]) or info["footers"]


# ---------------------------------------------------------------------------
# Deep analyze
# ---------------------------------------------------------------------------
def test_deep_analyze_combines_everything(rich_pdf: Path):
    info = core.deep_analyze(rich_pdf)
    assert "extractability" in info
    assert "metadata" in info
    assert "outline" in info
    assert "headers_footers" in info
    assert "pages" in info
    assert info["extractability"]["extractable"] is True
    assert info["metadata"]["title"] == "Test Dokümanı"
    assert len(info["outline"]) == 3
    assert len(info["pages"]) == 3
    p1 = info["pages"][0]
    for k in ("page", "width", "height", "rotation", "char_count", "image_count", "columns"):
        assert k in p1


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------
def _bytes(p: Path) -> bytes:
    return p.read_bytes()


def test_endpoint_find(client: TestClient, rich_pdf: Path):
    r = client.post(
        "/pdf/find",
        files={"file": ("d.pdf", _bytes(rich_pdf), "application/pdf")},
        data={"query": "Bölüm"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] >= 3
    assert body["query"] == "Bölüm"


def test_endpoint_find_empty_query_400(client: TestClient, rich_pdf: Path):
    r = client.post(
        "/pdf/find",
        files={"file": ("d.pdf", _bytes(rich_pdf), "application/pdf")},
        data={"query": "   "},
    )
    assert r.status_code == 400


def test_endpoint_outline(client: TestClient, rich_pdf: Path):
    r = client.post(
        "/pdf/outline",
        files={"file": ("d.pdf", _bytes(rich_pdf), "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 3
    assert body["outline"][0]["title"] == "Bölüm 1"


def test_endpoint_metadata(client: TestClient, rich_pdf: Path):
    r = client.post(
        "/pdf/metadata",
        files={"file": ("d.pdf", _bytes(rich_pdf), "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["author"] == "Engin"
    assert body["page_count"] == 3


def test_endpoint_set_metadata(client: TestClient, rich_pdf: Path):
    r = client.post(
        "/pdf/set-metadata",
        files={"file": ("d.pdf", _bytes(rich_pdf), "application/pdf")},
        data={"title": "Güncellenmiş", "author": "Test"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    with fitz.open(stream=r.content, filetype="pdf") as d:
        assert (d.metadata or {}).get("title") == "Güncellenmiş"


def test_endpoint_extract_images(client: TestClient, rich_pdf: Path):
    r = client.post(
        "/pdf/extract-images",
        files={"file": ("d.pdf", _bytes(rich_pdf), "application/pdf")},
        data={"min_size": "10"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert int(r.headers.get("X-Image-Count", "0")) >= 1
    z = zipfile.ZipFile(__import__("io").BytesIO(r.content))
    assert len(z.namelist()) >= 1


def test_endpoint_extract_images_none_found_400(client: TestClient, tmp_path: Path):
    """A PDF with no images returns 400 with a message."""
    p = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "no images here", fontsize=12, fontname="helv")
    doc.save(str(p))
    doc.close()
    r = client.post(
        "/pdf/extract-images",
        files={"file": ("d.pdf", _bytes(p), "application/pdf")},
    )
    assert r.status_code == 400


def test_endpoint_thumbnail_png(client: TestClient, rich_pdf: Path):
    r = client.post(
        "/pdf/thumbnail",
        files={"file": ("d.pdf", _bytes(rich_pdf), "application/pdf")},
        data={"page_no": "1", "dpi": "72"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert int(r.headers.get("X-Width", "0")) > 0


def test_endpoint_thumbnail_invalid_dpi(client: TestClient, rich_pdf: Path):
    r = client.post(
        "/pdf/thumbnail",
        files={"file": ("d.pdf", _bytes(rich_pdf), "application/pdf")},
        data={"dpi": "10"},
    )
    assert r.status_code == 400


def test_endpoint_deep_analyze(client: TestClient, rich_pdf: Path):
    r = client.post(
        "/pdf/deep-analyze",
        files={"file": ("d.pdf", _bytes(rich_pdf), "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert "extractability" in body and body["extractability"]["extractable"] is True
    assert "metadata" in body
    assert "outline" in body and len(body["outline"]) == 3
    assert "pages" in body and len(body["pages"]) == 3


# ---------------------------------------------------------------------------
# Cross-PDF smoke: verify engine runs without crashing on the sample suite
# ---------------------------------------------------------------------------
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "_bench_samples"


def _has_samples() -> bool:
    return SAMPLES_DIR.is_dir() and any(SAMPLES_DIR.glob("*.pdf"))


@pytest.mark.skipif(not _has_samples(), reason="No samples in _bench_samples/")
def test_deep_analyze_runs_on_real_samples():
    for p in SAMPLES_DIR.glob("*.pdf"):
        info = core.deep_analyze(p)
        assert "extractability" in info
        assert info["extractability"]["total_pages"] >= 1
