"""Tests for the PDF editor backend wiring (v1.4 — Phase 4a).

Phase 4a only ships the plumbing:
  • ``GET /pdf/edit/fonts`` — bundled font catalogue, filtered to TTFs that
    actually exist on disk.
  • ``POST /pdf/edit/save`` — operation-list round-trip stub. Returns the
    input PDF re-saved with pymupdf's compact options; reports the operation
    counts via response headers.

Editing semantics (annot / overlay / replace) come in Phase 4b/4c/4d and
their tests will land alongside that code.
"""

from __future__ import annotations

import json

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


def _pdf_bytes(pages: int = 1) -> bytes:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 100), f"Sayfa {i + 1}", fontsize=12, fontname="helv")
    buf = doc.tobytes()
    doc.close()
    return buf


# ---------------------------------------------------------------------------
# /pdf/edit/fonts
# ---------------------------------------------------------------------------
def test_fonts_endpoint_shape(client: TestClient) -> None:
    r = client.get("/pdf/edit/fonts")
    assert r.status_code == 200
    body = r.json()
    assert "families" in body
    assert "fallback" in body
    assert "count" in body
    assert isinstance(body["families"], list)
    assert body["count"] == len(body["families"])


def test_fonts_endpoint_only_lists_present_files(client: TestClient) -> None:
    r = client.get("/pdf/edit/fonts").json()
    # Whatever the catalogue advertises must have a known id + label + category
    for f in r["families"]:
        assert {"id", "label", "category"}.issubset(f.keys())
        # Filenames must have been stripped (frontend never sees them)
        assert "file" not in f
    if r["families"]:
        assert r["fallback"] is not None


def test_fonts_endpoint_includes_noto_when_present(client: TestClient) -> None:
    """If the asset bootstrap has run, Noto Sans must show up in the list.

    Skipped automatically when the test environment hasn't fetched the fonts
    yet (clean clones, CI without the setup step).
    """
    from state import BASE_DIR

    if not (BASE_DIR / "static" / "fonts" / "NotoSans-Regular.ttf").is_file():
        pytest.skip("static/fonts/ not populated — run scripts/setup_editor_assets.py")
    r = client.get("/pdf/edit/fonts").json()
    ids = {f["id"] for f in r["families"]}
    assert "noto-sans" in ids


# ---------------------------------------------------------------------------
# /pdf/edit/save  (Phase 4a stub — operations ignored, file round-tripped)
# ---------------------------------------------------------------------------
def test_save_round_trips_pdf(client: TestClient) -> None:
    src = _pdf_bytes(2)
    r = client.post(
        "/pdf/edit/save",
        files={"file": ("doc.pdf", src, "application/pdf")},
        data={"operations": "[]"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["X-Operations-Applied"] == "0"
    assert r.headers["X-Operations-Received"] == "0"
    assert r.headers["X-Editor-Phase"] == "4e"
    with fitz.open(stream=r.content, filetype="pdf") as d:
        assert d.page_count == 2


def test_save_counts_received_operations(client: TestClient) -> None:
    # Unknown op types are accepted but skipped at apply time
    ops = [
        {"type": "exotic", "page": 1, "bbox": [10, 20, 100, 40]},
        {"type": "annot", "page": 2, "text": "note"},
    ]
    r = client.post(
        "/pdf/edit/save",
        files={"file": ("doc.pdf", _pdf_bytes(2), "application/pdf")},
        data={"operations": json.dumps(ops)},
    )
    assert r.status_code == 200, r.text
    assert r.headers["X-Operations-Received"] == "2"
    assert r.headers["X-Operations-Applied"] == "0"
    assert r.headers["X-Operations-Skipped"] == "2"


def test_save_rejects_non_pdf(client: TestClient) -> None:
    r = client.post(
        "/pdf/edit/save",
        files={"file": ("doc.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400


def test_save_rejects_invalid_operations_json(client: TestClient) -> None:
    r = client.post(
        "/pdf/edit/save",
        files={"file": ("doc.pdf", _pdf_bytes(1), "application/pdf")},
        data={"operations": "not-json"},
    )
    assert r.status_code == 400


def test_save_rejects_non_list_operations(client: TestClient) -> None:
    r = client.post(
        "/pdf/edit/save",
        files={"file": ("doc.pdf", _pdf_bytes(1), "application/pdf")},
        data={"operations": '{"not": "a list"}'},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Phase 4b — apply_editor_operations (annotation modes)
# ---------------------------------------------------------------------------


def _png_data_url() -> str:
    """Return a tiny 4x4 red PNG as a data URL (for image-op tests)."""
    import base64

    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 4))
    pix.set_rect(pix.irect, (255, 0, 0))
    png = pix.tobytes("png")
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def test_apply_highlight(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        inp,
        out,
        [
            {
                "type": "highlight",
                "page": 1,
                "rect": [50, 80, 200, 105],
                "color": [1.0, 0.92, 0.23],
            },
        ],
    )
    assert summary["applied"] == 1, summary
    assert summary["skipped"] == 0, summary
    # PyMuPDF requires annot inspection while the page is still open
    type_strs: list[str] = []
    with fitz.open(str(out)) as d:
        for annot in d[0].annots() or []:
            t = annot.type
            type_strs.append(str(t[1] if isinstance(t, tuple) and len(t) > 1 else t).lower())
    assert len(type_strs) == 1
    assert "highlight" in type_strs[0]


def test_apply_all_annot_types(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    ops = [
        {"type": "highlight", "page": 1, "rect": [50, 80, 200, 105]},
        {"type": "underline", "page": 1, "rect": [50, 110, 200, 130]},
        {"type": "strikeout", "page": 1, "rect": [50, 140, 200, 160]},
        {"type": "sticky", "page": 1, "point": [300, 100], "content": "Test note"},
        {
            "type": "ink",
            "page": 1,
            "strokes": [[[20, 200], [40, 220], [60, 210]]],
            "color": [0, 0, 1],
        },
        {
            "type": "image",
            "page": 1,
            "rect": [100, 250, 180, 320],
            "image_data_url": _png_data_url(),
        },
    ]
    summary = core.apply_editor_operations(inp, out, ops)
    assert summary["applied"] == 6, summary
    assert summary["skipped"] == 0
    with fitz.open(str(out)) as d:
        annots = list(d[0].annots() or [])
    # 5 annot-based ops (highlight, underline, strikeout, sticky, ink) + image
    # is inserted as page content, not an annotation. So we expect 5 annots.
    assert len(annots) == 5


def test_apply_invalid_page_skips(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(2))
    out = tmp_path / "out.pdf"
    ops = [
        {"type": "highlight", "page": 1, "rect": [50, 80, 200, 105]},
        {"type": "highlight", "page": 99, "rect": [10, 10, 50, 50]},
        {"type": "highlight", "page": 0, "rect": [10, 10, 50, 50]},
    ]
    summary = core.apply_editor_operations(inp, out, ops)
    assert summary["applied"] == 1
    assert summary["skipped"] == 2
    assert any("99" in e["error"] for e in summary["errors"])


def test_apply_unknown_type_skips(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    ops = [
        {"type": "highlight", "page": 1, "rect": [50, 80, 200, 105]},
        {"type": "exotic", "page": 1, "rect": [10, 10, 50, 50]},
    ]
    summary = core.apply_editor_operations(inp, out, ops)
    assert summary["applied"] == 1
    assert summary["skipped"] == 1
    assert "exotic" in summary["errors"][0]["error"]


def test_apply_sticky_requires_content(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    ops = [
        {"type": "sticky", "page": 1, "point": [100, 100], "content": ""},
        {"type": "sticky", "page": 1, "point": [100, 200], "content": "ok"},
    ]
    summary = core.apply_editor_operations(inp, out, ops)
    assert summary["applied"] == 1
    assert summary["skipped"] == 1


def test_apply_rect_outside_page_skips(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        inp,
        out,
        [
            {"type": "highlight", "page": 1, "rect": [-200, -200, -100, -100]},
        ],
    )
    assert summary["applied"] == 0
    assert summary["skipped"] == 1


def test_apply_ink_requires_2_points(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        inp,
        out,
        [
            {"type": "ink", "page": 1, "strokes": [[[10, 10]]]},
        ],
    )
    assert summary["skipped"] == 1


def test_apply_image_requires_data_url(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        inp,
        out,
        [
            {"type": "image", "page": 1, "rect": [10, 10, 50, 50]},
        ],
    )
    assert summary["skipped"] == 1


# ---------------------------------------------------------------------------
# Endpoint integration — operations actually flow through to PDF
# ---------------------------------------------------------------------------
def test_endpoint_save_applies_highlight(client: TestClient) -> None:
    src = _pdf_bytes(1)
    ops = [{"type": "highlight", "page": 1, "rect": [50, 80, 200, 105]}]
    r = client.post(
        "/pdf/edit/save",
        files={"file": ("doc.pdf", src, "application/pdf")},
        data={"operations": json.dumps(ops)},
    )
    assert r.status_code == 200, r.text
    assert r.headers["X-Operations-Applied"] == "1"
    assert r.headers["X-Operations-Skipped"] == "0"
    assert r.headers["X-Editor-Phase"] == "4e"
    with fitz.open(stream=r.content, filetype="pdf") as d:
        assert len(list(d[0].annots() or [])) == 1


def test_endpoint_save_partial_failures_reported(client: TestClient) -> None:
    src = _pdf_bytes(1)
    ops = [
        {"type": "highlight", "page": 1, "rect": [50, 80, 200, 105]},
        {"type": "highlight", "page": 99, "rect": [50, 80, 200, 105]},
    ]
    r = client.post(
        "/pdf/edit/save",
        files={"file": ("doc.pdf", src, "application/pdf")},
        data={"operations": json.dumps(ops)},
    )
    assert r.status_code == 200, r.text
    assert r.headers["X-Operations-Applied"] == "1"
    assert r.headers["X-Operations-Skipped"] == "1"
    assert "X-First-Error" in r.headers


# ---------------------------------------------------------------------------
# Phase 4c — overlay operations (text / rect / ellipse / line)
# ---------------------------------------------------------------------------
def test_apply_text_inserts_visible_string(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        inp,
        out,
        [
            {
                "type": "text",
                "page": 1,
                "point": [80, 200],
                "text": "Türkçe metin",
                "font_id": "noto-sans",
                "fontsize": 14,
                "color": [0.1, 0.2, 0.7],
                "bold": False,
                "italic": False,
            },
        ],
    )
    assert summary["applied"] == 1, summary
    with fitz.open(str(out)) as d:
        # PyMuPDF's get_text() sometimes encodes the space between glyphs as
        # U+00A0 depending on font metrics — collapse it back to a regular
        # space before the substring check.
        text = d[0].get_text().replace("\xa0", " ")
    assert "Türkçe metin" in text


def test_apply_text_uses_bold_variant(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        inp,
        out,
        [
            {
                "type": "text",
                "page": 1,
                "point": [80, 100],
                "text": "Kalın",
                "font_id": "noto-sans",
                "fontsize": 12,
                "bold": True,
            },
        ],
    )
    assert summary["applied"] == 1, summary


def test_apply_text_empty_skipped(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        inp,
        out,
        [
            {"type": "text", "page": 1, "point": [80, 100], "text": "  "},
        ],
    )
    assert summary["skipped"] == 1


def test_apply_rect_draws_outline(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        inp,
        out,
        [
            {
                "type": "rect",
                "page": 1,
                "rect": [50, 80, 200, 200],
                "color": [1, 0, 0],
                "stroke_width": 2.0,
            },
        ],
    )
    assert summary["applied"] == 1, summary
    with fitz.open(str(out)) as d:
        drawings = d[0].get_drawings()
    # At least one drawing path on the page
    assert len(drawings) >= 1


def test_apply_ellipse(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        inp,
        out,
        [
            {
                "type": "ellipse",
                "page": 1,
                "rect": [100, 100, 250, 200],
                "color": [0, 0, 1],
                "fill": [0.8, 0.9, 1.0],
            },
        ],
    )
    assert summary["applied"] == 1, summary


def test_apply_line(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        inp,
        out,
        [
            {
                "type": "line",
                "page": 1,
                "p1": [50, 50],
                "p2": [200, 200],
                "color": [0, 0, 0],
                "stroke_width": 1.5,
            },
        ],
    )
    assert summary["applied"] == 1, summary


def test_apply_line_zero_length_skipped(tmp_path):
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes(1))
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        inp,
        out,
        [
            {"type": "line", "page": 1, "p1": [100, 100], "p2": [100, 100]},
        ],
    )
    assert summary["skipped"] == 1


# ---------------------------------------------------------------------------
# Font catalog + resolver
# ---------------------------------------------------------------------------
def test_editor_font_catalog_returns_families():
    from state import BASE_DIR

    if not (BASE_DIR / "static" / "fonts" / "NotoSans-Regular.ttf").is_file():
        pytest.skip("static/fonts/ not populated — run scripts/setup_editor_assets.py")
    cat = core.editor_font_catalog()
    ids = {f["id"] for f in cat}
    assert "noto-sans" in ids
    noto = next(f for f in cat if f["id"] == "noto-sans")
    assert "regular" in noto["variants"]
    assert "bold" in noto["variants"]


def test_resolve_editor_font_picks_bold():
    from state import BASE_DIR

    if not (BASE_DIR / "static" / "fonts" / "NotoSans-Bold.ttf").is_file():
        pytest.skip("NotoSans-Bold.ttf missing")
    path = core.resolve_editor_font("noto-sans", bold=True)
    assert path is not None
    assert "Bold" in str(path)


def test_resolve_editor_font_unknown_falls_back():
    path = core.resolve_editor_font("nonexistent-family", bold=False)
    # Either a system font or None — but never raises
    assert path is None or path.is_file()


def test_fonts_endpoint_returns_variants(client: TestClient):
    r = client.get("/pdf/edit/fonts").json()
    if not r["families"]:
        pytest.skip("static/fonts/ not populated")
    for f in r["families"]:
        assert "variants" in f
        assert isinstance(f["variants"], list)
        assert len(f["variants"]) >= 1  # some system fonts ship bold-only
    # The bundled families always include "regular"
    bundled = [f for f in r["families"] if f.get("category") == "bundled"]
    if bundled:
        for f in bundled:
            assert "regular" in f["variants"]


# ---------------------------------------------------------------------------
# Phase 4d — extract_text_spans + replace operation
# ---------------------------------------------------------------------------
@pytest.fixture
def text_pdf(tmp_path):
    """A 1-page PDF with a known string at a known position."""
    out = tmp_path / "text.pdf"
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((72, 100), "Original Text Here", fontsize=12, fontname="helv")
    doc.save(str(out))
    doc.close()
    return out


def test_extract_text_spans_finds_visible_text(text_pdf):
    spans = core.extract_text_spans(text_pdf)
    assert len(spans) >= 1
    s = spans[0]
    assert "Original" in s["text"] or "Text" in s["text"]
    for key in ("page", "rect", "text", "font_id", "fontsize", "color", "bold", "italic"):
        assert key in s
    assert s["page"] == 1
    assert len(s["rect"]) == 4
    assert s["fontsize"] > 0


def test_font_name_mapping_helvetica_is_sans():
    fam, bold, italic = core._map_font_name_to_family("Helvetica")
    assert fam == "noto-sans"
    assert bold is False
    assert italic is False


def test_font_name_mapping_arial_bold():
    fam, bold, _italic = core._map_font_name_to_family("Arial-BoldMT")
    assert fam == "noto-sans"
    assert bold is True


def test_font_name_mapping_times_italic():
    fam, _bold, italic = core._map_font_name_to_family("Times-Italic")
    assert fam == "noto-serif"
    assert italic is True


def test_font_name_mapping_courier_is_mono():
    fam, _b, _i = core._map_font_name_to_family("Courier-Bold")
    assert fam == "noto-mono"


def test_apply_replace_swaps_text(text_pdf, tmp_path):
    spans = core.extract_text_spans(text_pdf)
    assert spans
    target = spans[0]
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        text_pdf,
        out,
        [
            {
                "type": "replace",
                "page": target["page"],
                "rect": target["rect"],
                "text": "Yeni Metin",
                "font_id": "noto-sans",
                "fontsize": 12,
                "color": [0, 0, 0],
            },
        ],
    )
    assert summary["applied"] == 1, summary
    with fitz.open(str(out)) as d:
        text = d[0].get_text().replace("\xa0", " ")
    assert "Yeni Metin" in text
    assert "Original" not in text  # redacted


def test_apply_replace_empty_text_just_removes(text_pdf, tmp_path):
    spans = core.extract_text_spans(text_pdf)
    target = spans[0]
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        text_pdf,
        out,
        [
            {"type": "replace", "page": target["page"], "rect": target["rect"], "text": ""},
        ],
    )
    assert summary["applied"] == 1, summary
    with fitz.open(str(out)) as d:
        text = d[0].get_text()
    assert "Original" not in text


def test_apply_replace_shrinks_long_text(text_pdf, tmp_path):
    """When the new text is wider than the original rect, fontsize is auto-
    shrunk so the layout doesn't blow out."""
    spans = core.extract_text_spans(text_pdf, granularity="line")
    assert spans
    target = spans[0]
    # Pick a string much longer than the original
    long_text = "X" * (len(target["text"]) * 5 + 50)
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        text_pdf,
        out,
        [
            {
                "type": "replace",
                "page": target["page"],
                "rect": target["rect"],
                "text": long_text,
                "font_id": "noto-sans",
                "fontsize": float(target["fontsize"]),
            },
        ],
    )
    assert summary["applied"] == 1, summary
    # Verify the new text actually appears in the saved PDF
    with fitz.open(str(out)) as d:
        pdf_text = d[0].get_text()
    assert long_text[:20] in pdf_text  # at least the head was rendered


def test_fit_fontsize_helper_shrinks_when_wide():
    import fitz as _fitz

    bundled = core.resolve_editor_font("noto-sans")
    if bundled is None or not bundled.is_file():
        pytest.skip("Noto Sans not bundled")
    rect = _fitz.Rect(0, 0, 100, 20)  # narrow box
    long_text = "Bu çok uzun bir metin parçasıdır ve sığmamalı"
    fitted = core._fit_fontsize_to_rect(
        long_text,
        rect=rect,
        requested_fontsize=12.0,
        font_path=bundled,
        font_buffer=None,
        min_fontsize=4.0,
    )
    assert fitted < 12.0
    assert fitted >= 4.0


def test_fit_fontsize_helper_keeps_size_when_fits():
    import fitz as _fitz

    bundled = core.resolve_editor_font("noto-sans")
    if bundled is None or not bundled.is_file():
        pytest.skip("Noto Sans not bundled")
    rect = _fitz.Rect(0, 0, 500, 20)
    short_text = "Kısa"
    fitted = core._fit_fontsize_to_rect(
        short_text,
        rect=rect,
        requested_fontsize=12.0,
        font_path=bundled,
        font_buffer=None,
        min_fontsize=4.0,
    )
    assert fitted == 12.0  # already fits, must not grow or shrink


def test_apply_replace_invalid_rect_skipped(text_pdf, tmp_path):
    out = tmp_path / "out.pdf"
    summary = core.apply_editor_operations(
        text_pdf,
        out,
        [
            {"type": "replace", "page": 1, "rect": [-100, -100, -50, -50], "text": "x"},
        ],
    )
    assert summary["applied"] == 0
    assert summary["skipped"] == 1


def test_endpoint_spans_returns_metadata(client: TestClient, text_pdf):
    r = client.post(
        "/pdf/edit/spans",
        files={"file": ("t.pdf", text_pdf.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "spans" in body
    assert body["count"] >= 1
    s = body["spans"][0]
    for key in ("page", "rect", "text", "font_id", "fontsize", "color", "bold", "italic"):
        assert key in s


def test_endpoint_spans_rejects_non_pdf(client: TestClient):
    r = client.post(
        "/pdf/edit/spans",
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Extractability classifier
# ---------------------------------------------------------------------------
def test_classify_extractability_vector(text_pdf):
    info = core.classify_pdf_extractability(text_pdf)
    assert info["extractable"] is True
    assert info["type"] in ("vector", "hybrid")  # text PDF always either
    assert info["pages_with_text"] >= 1
    assert "message" in info


def test_classify_extractability_image_pdf(tmp_path):
    """A PDF that contains only an image and no text → 'image'."""
    out = tmp_path / "img.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100))
    pix.set_rect(pix.irect, (255, 0, 0))
    page.insert_image(page.rect, pixmap=pix)
    doc.save(str(out))
    doc.close()
    info = core.classify_pdf_extractability(out)
    assert info["extractable"] is False
    assert info["type"] == "image"
    assert info["pages_with_text"] == 0
    assert info["pages_with_only_images"] >= 1


def test_classify_extractability_empty(tmp_path):
    out = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(out))
    doc.close()
    info = core.classify_pdf_extractability(out)
    assert info["type"] == "empty"
    assert info["extractable"] is False


# ---------------------------------------------------------------------------
# Granularity-aware extract_text_spans
# ---------------------------------------------------------------------------
@pytest.fixture
def multi_line_pdf(tmp_path):
    out = tmp_path / "multi.pdf"
    doc = fitz.open()
    p = doc.new_page()
    # Three lines, each with multiple words
    p.insert_text((50, 100), "First line with several words", fontsize=12, fontname="helv")
    p.insert_text((50, 130), "Second line of text content", fontsize=12, fontname="helv")
    p.insert_text((50, 160), "Third short line", fontsize=12, fontname="helv")
    doc.save(str(out))
    doc.close()
    return out


def test_granularity_word_returns_at_least_as_many_as_line(multi_line_pdf):
    word = core.extract_text_spans(multi_line_pdf, granularity="word", merge_adjacent=False)
    line = core.extract_text_spans(multi_line_pdf, granularity="line")
    block = core.extract_text_spans(multi_line_pdf, granularity="block")
    # Word-level always produces at least as many spans as line/block
    # (PyMuPDF emits one span per insert_text call by default; some PDFs
    # naturally split intra-line and yield more — the property holds either
    # way: word >= line >= block in count).
    assert len(word) >= len(line)
    assert len(line) >= len(block)


def test_granularity_line_merges_words(multi_line_pdf):
    spans = core.extract_text_spans(multi_line_pdf, granularity="line")
    # 3 visual lines, expect ≤3 entries (lines might split if PDF wraps)
    assert 1 <= len(spans) <= 3
    for s in spans:
        # Line text should contain spaces (merged from multiple words)
        assert " " in s["text"]
    assert all(s["granularity"] == "line" for s in spans)


def test_granularity_block_returns_paragraph(multi_line_pdf):
    spans = core.extract_text_spans(multi_line_pdf, granularity="block")
    # All 3 lines collapse into 1 block
    assert len(spans) >= 1
    assert spans[0]["granularity"] == "block"
    # Block text should have line breaks
    assert "\n" in spans[0]["text"] or len(spans) > 1


def test_granularity_invalid_raises(multi_line_pdf):
    with pytest.raises(ValueError):
        core.extract_text_spans(multi_line_pdf, granularity="bogus")


def test_word_granularity_merge_adjacent_reduces_count(multi_line_pdf):
    raw = core.extract_text_spans(multi_line_pdf, granularity="word", merge_adjacent=False)
    merged = core.extract_text_spans(multi_line_pdf, granularity="word", merge_adjacent=True)
    assert len(merged) <= len(raw)


# ---------------------------------------------------------------------------
# Glyph coverage helper
# ---------------------------------------------------------------------------
def test_font_glyph_coverage_full():
    from state import BASE_DIR

    p = BASE_DIR / "static" / "fonts" / "NotoSans-Regular.ttf"
    if not p.is_file():
        pytest.skip("NotoSans-Regular.ttf not bundled")
    buf = p.read_bytes()
    covered, total = core.font_glyph_coverage(buf, "Hello world")
    assert covered == total == 11


def test_font_glyph_coverage_with_missing():
    from state import BASE_DIR

    p = BASE_DIR / "static" / "fonts" / "NotoSans-Regular.ttf"
    if not p.is_file():
        pytest.skip("NotoSans-Regular.ttf not bundled")
    buf = p.read_bytes()
    # Private Use Area codepoints — guaranteed not in any normal font
    text = ""
    covered, total = core.font_glyph_coverage(buf, text)
    assert total == 4
    assert covered < total  # PUA chars should be missing


def test_font_glyph_coverage_empty_text():
    assert core.font_glyph_coverage(b"x" * 1000, "") == (0, 0)


# ---------------------------------------------------------------------------
# Endpoint: spans now returns extractability info + accepts granularity
# ---------------------------------------------------------------------------
def test_spans_endpoint_default_granularity_is_line(client: TestClient, text_pdf):
    r = client.post(
        "/pdf/edit/spans",
        files={"file": ("t.pdf", text_pdf.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["granularity"] == "line"
    assert "extractability" in body
    assert body["extractability"]["extractable"] is True


def test_spans_endpoint_word_vs_block(client: TestClient, text_pdf):
    r_word = client.post(
        "/pdf/edit/spans",
        files={"file": ("t.pdf", text_pdf.read_bytes(), "application/pdf")},
        data={"granularity": "word", "merge_adjacent": "false"},
    ).json()
    r_block = client.post(
        "/pdf/edit/spans",
        files={"file": ("t.pdf", text_pdf.read_bytes(), "application/pdf")},
        data={"granularity": "block"},
    ).json()
    assert r_word["count"] >= r_block["count"]


def test_spans_endpoint_invalid_granularity_400(client: TestClient, text_pdf):
    r = client.post(
        "/pdf/edit/spans",
        files={"file": ("t.pdf", text_pdf.read_bytes(), "application/pdf")},
        data={"granularity": "xxx"},
    )
    assert r.status_code == 400


def test_extractability_endpoint(client: TestClient, text_pdf):
    r = client.post(
        "/pdf/extractability",
        files={"file": ("t.pdf", text_pdf.read_bytes(), "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["extractable"] is True
    assert body["type"] in ("vector", "hybrid")


def test_pdf_to_markdown_refuses_image_only(tmp_path):
    """Cross-cut: pdf_to_markdown now uses extractability classifier."""
    out_pdf = tmp_path / "img.pdf"
    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 50, 50))
    pix.set_rect(pix.irect, (255, 0, 0))
    page.insert_image(page.rect, pixmap=pix)
    doc.save(str(out_pdf))
    doc.close()
    with pytest.raises(ValueError, match="görsel|metin"):
        core.pdf_to_markdown(out_pdf, tmp_path / "x.md")


def test_endpoint_save_applies_replace(client: TestClient, text_pdf):
    spans_resp = client.post(
        "/pdf/edit/spans",
        files={"file": ("t.pdf", text_pdf.read_bytes(), "application/pdf")},
    ).json()
    target = spans_resp["spans"][0]
    ops = [
        {
            "type": "replace",
            "page": target["page"],
            "rect": target["rect"],
            "text": "Replaced",
            "font_id": target["font_id"],
            "fontsize": target["fontsize"],
            "color": target["color"],
            "bold": target["bold"],
            "italic": target["italic"],
        }
    ]
    r = client.post(
        "/pdf/edit/save",
        files={"file": ("t.pdf", text_pdf.read_bytes(), "application/pdf")},
        data={"operations": json.dumps(ops)},
    )
    assert r.status_code == 200, r.text
    assert r.headers["X-Operations-Applied"] == "1"
    assert r.headers["X-Editor-Phase"] == "4e"
    with fitz.open(stream=r.content, filetype="pdf") as d:
        text = d[0].get_text()
    assert "Replaced" in text
