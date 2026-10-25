"""PDF editor: font catalogue, text spans, edit operations, annotations."""

from __future__ import annotations

import base64
import io
import shutil
import struct
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pymupdf
import pytest

from adminpdf.core import fonts
from adminpdf.ops.editor import pdf_date_iso

from .conftest import Api

DEJAVU = Path("/usr/share/fonts/truetype/dejavu")
SANS = DEJAVU / "DejaVuSans.ttf"
SANS_BOLD = DEJAVU / "DejaVuSans-Bold.ttf"
SERIF = DEJAVU / "DejaVuSerif.ttf"
TR = "İĞÜŞÖÇ ığüşöç"

needs_dejavu = pytest.mark.skipif(not (SANS.is_file() and SANS_BOLD.is_file()), reason="DejaVu fonts not installed")


# -- fixtures & helpers ------------------------------------------------------------
def _reset_catalogue(monkeypatch: pytest.MonkeyPatch, *dirs: Path) -> None:
    monkeypatch.setenv("APT_SYSTEM_FONT_DIRS", ":".join(str(d) for d in dirs))
    monkeypatch.setattr(fonts, "_cached", None)


@pytest.fixture(autouse=True)
def system_fonts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A deterministic "system" font folder: copies of DejaVu when present.
    The env var also reaches the spawned job workers."""
    d = tmp_path / "sysfonts"
    d.mkdir()
    for f in (SANS, SANS_BOLD):
        if f.is_file():
            shutil.copy(f, d / f.name)
    _reset_catalogue(monkeypatch, d)
    yield d
    fonts._cached = None


def pdf_bytes(doc: pymupdf.Document) -> bytes:
    data: bytes = doc.tobytes()
    doc.close()
    return data


def to_pdf(page: pymupdf.Page, rect: Any) -> list[float]:
    r = pymupdf.Rect(pymupdf.Rect(rect) * ~page.transformation_matrix).normalize()
    return [r.x0, r.y0, r.x1, r.y1]


def to_pdf_point(page: pymupdf.Page, p: Any) -> list[float]:
    q = pymupdf.Point(p) * ~page.transformation_matrix
    return [q.x, q.y]


def edit(api: Api, file_id: str, ops: list[dict[str, Any]]) -> dict[str, Any]:
    return api.run("edit", [file_id], {"operations": ops})


def edited(api: Api, file_id: str, ops: list[dict[str, Any]]) -> tuple[pymupdf.Document, dict[str, Any]]:
    job = edit(api, file_id, ops)
    assert job["status"] == "done", job
    assert job["result"]["name"].endswith("_duzenlenmis.pdf")
    return pymupdf.open("pdf", api.download(job["result"]["id"])), job["data"]


def png_data_url(img: Any) -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def quadrant_image() -> Any:
    from PIL import Image

    im = Image.new("RGB", (200, 200), (255, 255, 255))
    im.paste((255, 0, 0), (0, 0, 100, 100))  # top-left red
    im.paste((0, 0, 255), (100, 0, 200, 100))  # top-right blue
    im.paste((0, 255, 0), (0, 100, 100, 200))  # bottom-left green
    return im


def visual_dir(page: pymupdf.Page, d: tuple[float, float]) -> tuple[float, float]:
    """Text direction as the reader sees the (rotated) page."""
    m = page.rotation_matrix
    v = pymupdf.Point(d) * pymupdf.Matrix(m.a, m.b, m.c, m.d, 0, 0)
    return (round(v.x, 3), round(v.y, 3))


def close_rgb(value: str | tuple[int, ...], want: tuple[int, int, int], tol: int = 2) -> bool:
    got = tuple(int(value[i : i + 2], 16) for i in (1, 3, 5)) if isinstance(value, str) else value
    return all(abs(a - b) <= tol for a, b in zip(got, want, strict=True))


def lines_of(page: pymupdf.Page) -> list[tuple[str, tuple[float, float]]]:
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            out.append(("".join(s["text"] for s in ln["spans"]), tuple(ln["dir"])))
    return out


# -- font catalogue ----------------------------------------------------------------------
def test_fonts_endpoint_lists_standard_and_system(api: Api) -> None:
    r = api.c.get("/api/fonts")
    assert r.status_code == 200
    fams = {f["id"]: f for f in r.json()}
    for fid in ("standard:helvetica", "standard:times", "standard:courier"):
        assert fams[fid]["source"] == "standard"
        assert {(s["weight"], s["italic"]) for s in fams[fid]["styles"]} == {
            (400, False),
            (700, False),
            (400, True),
            (700, True),
        }
    assert fams["standard:courier"]["monospace"] and fams["standard:times"]["serif"]
    for fam in fams.values():
        assert set(fam) >= {"id", "family", "source", "styles", "restricted", "monospace", "serif"}
        for s in fam["styles"]:
            assert 100 <= s["weight"] <= 900 and isinstance(s["italic"], bool) and s["id"]


@needs_dejavu
def test_font_file_endpoint_serves_bytes_and_rejects_bogus_ids(api: Api) -> None:
    fams = {f["id"]: f for f in api.c.get("/api/fonts").json()}
    dejavu = fams["system:dejavu-sans"]
    assert dejavu["source"] == "system" and not dejavu["restricted"] and not dejavu["serif"]
    styles = {(s["weight"], s["italic"]): s for s in dejavu["styles"]}
    assert set(styles) == {(400, False), (700, False)}
    regular = styles[(400, False)]
    assert regular["file"] is True
    r = api.c.get(f"/api/fonts/{regular['id']}/file")
    assert r.status_code == 200
    assert r.content == SANS.read_bytes()
    assert r.headers["content-type"] == "font/ttf"
    for bogus in ("nope", "std-helv", "f" + "0" * 23, "..%2F..%2Fetc%2Fpasswd", "a" * 100):
        assert api.c.get(f"/api/fonts/{bogus}/file").status_code == 404


def _with_fs_type(src: Path, dst: Path, fs_type: int) -> None:
    data = bytearray(src.read_bytes())
    (num_tables,) = struct.unpack_from(">H", data, 4)
    for i in range(num_tables):
        tag, _c, off, _len = struct.unpack_from(">4sIII", data, 12 + 16 * i)
        if tag == b"OS/2":
            struct.pack_into(">H", data, off + 8, fs_type)
    dst.write_bytes(bytes(data))


@pytest.mark.skipif(not SERIF.is_file(), reason="DejaVu Serif not installed")
def test_restricted_font_is_listed_locked_and_not_embeddable(
    api: Api, system_fonts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _with_fs_type(SERIF, system_fonts / "Locked.ttf", 0x0002)
    _reset_catalogue(monkeypatch, system_fonts)
    fams = {f["id"]: f for f in api.c.get("/api/fonts").json()}
    locked = fams["system:dejavu-serif"]
    assert locked["restricted"] is True and locked["serif"] is True
    style = locked["styles"][0]
    assert style["restricted"] is True and style["file"] is False
    assert api.c.get(f"/api/fonts/{style['id']}/file").status_code == 403

    f = api.upload(pdf_bytes(_doc_with_text()))
    job = edit(
        api,
        f["id"],
        [{"type": "text", "page": 1, "rect": [72, 600, 300, 650], "text": "x", "font": {"family_id": locked["id"]}}],
    )
    assert job["status"] == "failed"
    assert "licence" in job["error"]["en"]


def _build_ttc(faces: list[bytes]) -> bytes:
    """Pack standalone sfnt files into a TrueType collection."""
    header_len = 12 + 4 * len(faces)
    out = bytearray()
    offsets = []
    body = bytearray()
    # Each face: its table directory then its tables, offsets rebased.
    for face in faces:
        (num,) = struct.unpack_from(">H", face, 4)
        dir_len = 12 + 16 * num
        tables = [struct.unpack_from(">4sIII", face, 12 + 16 * i) for i in range(num)]
        face_start = header_len + len(body)
        offsets.append(face_start)
        data_start = face_start + dir_len
        directory = bytearray(face[:12])
        blobs = bytearray()
        for tag, checksum, off, length in tables:
            directory += struct.pack(">4sIII", tag, checksum, data_start + len(blobs), length)
            blobs += face[off : off + length] + b"\x00" * (-length % 4)
        body += directory + blobs
    out += b"ttcf" + struct.pack(">HHI", 1, 0, len(faces))
    out += b"".join(struct.pack(">I", o) for o in offsets)
    return bytes(out + body)


@needs_dejavu
def test_ttc_collection_parsed_and_face_extracted(tmp_path: Path) -> None:
    ttc = tmp_path / "pair.ttc"
    ttc.write_bytes(_build_ttc([SANS.read_bytes(), SANS_BOLD.read_bytes()]))
    faces = fonts.read_font_faces(ttc)
    assert [(f.family, f.weight, f.index) for f in faces] == [("DejaVu Sans", 400, 0), ("DejaVu Sans", 700, 1)]
    bold = pymupdf.Font(fontbuffer=fonts.extract_face(ttc, 1))
    assert "Bold" in bold.name and bold.has_glyph(ord("ş"))
    cat = fonts.build_catalogue(tmp_path / "none", [tmp_path])
    fam = cat.family("system:dejavu-sans")
    assert fam is not None and {s.weight for s in fam.styles} == {400, 700}
    with pytest.raises(ValueError):
        fonts.extract_face(ttc, 5)


def test_font_reader_survives_garbage(tmp_path: Path) -> None:
    samples = {
        "empty.ttf": b"",
        "junk.ttf": b"\x00\x01\x00\x00" + b"\xff" * 64,
        "huge_tables.otf": b"OTTO\xff\xff" + b"\x00" * 64,
        "ttc.ttc": b"ttcf\x00\x01\x00\x00\xff\xff\xff\xff" + b"\x00" * 16,
        "trunc.ttf": SANS.read_bytes()[:3000] if SANS.is_file() else b"\x00\x01\x00\x00\x00\x10",
    }
    for name, data in samples.items():
        (tmp_path / name).write_bytes(data)
        assert fonts.read_font_faces(tmp_path / name) == []
    assert fonts.build_catalogue(tmp_path / "none", [tmp_path]).family("standard:helvetica") is not None


def test_pdf_font_name_matching(system_fonts: Path) -> None:
    cat = fonts.build_catalogue(system_fonts / "none", [system_fonts])
    assert fonts.decompose_font_name("ABCDEF+TimesNewRomanPSMT")[:2] == ("Times New Roman", "Times New Roman")

    def m(name: str, **kw: Any) -> tuple[str, int, bool]:
        r = fonts.match_pdf_font(name, catalogue=cat, **kw)
        return (r.family_id, r.weight, r.italic)

    assert m("TimesNewRomanPSMT") == ("standard:times", 400, False)
    assert m("TimesNewRomanPS-BoldItalicMT") == ("standard:times", 700, True)
    assert m("ABCDEF+Arial-BoldMT") == ("standard:helvetica", 700, False)
    assert m("Arial,Bold") == ("standard:helvetica", 700, False)
    assert m("CalibriSemibold")[1:] == (600, False)
    assert m("Courier-Oblique") == ("standard:courier", 400, True)
    assert m("Unknown", serif=True)[0] == "standard:times"
    assert m("Unknown", mono=True)[0] == "standard:courier"
    assert m("Unknown", bold=True) == ("standard:helvetica", 700, False)
    if SANS.is_file():
        assert m("XYZABC+DejaVuSans-Bold") == ("system:dejavu-sans", 700, False)


def test_pdf_date_iso() -> None:
    assert pdf_date_iso("D:20261025143000+03'00'") == "2026-10-25T14:30:00+03:00"
    assert pdf_date_iso("D:2026") == "2026-01-01T00:00:00"
    assert pdf_date_iso("D:20261025143000Z") == "2026-10-25T14:30:00Z"
    assert pdf_date_iso("garbage") == ""


# -- text spans -------------------------------------------------------------------------------
def _doc_with_text() -> pymupdf.Document:
    doc = pymupdf.open()
    page = doc.new_page()
    page.draw_rect(pymupdf.Rect(60, 180, 400, 230), color=None, fill=(0.8, 0.9, 1.0))
    page.insert_text((72, 100), "Merhaba dünya", fontsize=14)
    page.insert_text((72, 210), "Renkli metin", fontsize=12, color=(1, 0, 0))
    if SANS.is_file():
        page.insert_text((72, 300), "Gömülü font", fontsize=12, fontname="DejaVu", fontfile=str(SANS))
    return doc


def test_text_spans_rects_are_pdf_user_space(api: Api) -> None:
    doc = _doc_with_text()
    rot = doc.new_page(width=400, height=600)
    rot.insert_text((50, 80), "Dönük sayfa", fontsize=16)
    rot.set_rotation(90)
    off = doc.new_page(width=300, height=300)
    off.set_mediabox(pymupdf.Rect(100, 50, 400, 350))
    off.insert_text((40, 60), "Kayik kutu", fontsize=12)
    data = doc.tobytes()
    f = api.upload(data)
    job = api.run("text_spans", [f["id"]], {"granularity": "word"})
    assert job["status"] == "done", job
    pages = job["data"]["pages"]
    assert [p["page"] for p in pages] == [1, 2, 3] and job["data"]["truncated"] is False
    assert pages[1]["rotation"] == 90 and pages[1]["width"] == 400 and pages[1]["height"] == 600
    assert pages[2]["box"] == [100.0, 50.0, 400.0, 350.0]
    with pymupdf.open("pdf", data) as ref:
        for p in pages:
            page = ref[p["page"] - 1]
            words = {s["text"]: s for s in p["spans"]}
            assert words, p
            for text, span in words.items():
                hits = page.search_for(text)
                assert hits, text
                assert span["rect"] == pytest.approx(to_pdf(page, hits[0]), abs=0.05), text
    first = {s["text"]: s for s in pages[0]["spans"]}
    merhaba = first["Merhaba"]
    assert merhaba["font"] == "Helvetica" and merhaba["size"] == 14 and merhaba["color"] == "#000000"
    assert merhaba["matched_font"] == {"family_id": "standard:helvetica", "weight": 400, "italic": False}
    assert merhaba["background"] == "#FFFFFF" and merhaba["embedded"] is False
    assert merhaba["origin"] == pytest.approx([72, 842 - 100], abs=0.01) and merhaba["dir"] == [1.0, 0.0]
    red = first["Renkli"]
    assert red["color"] == "#FF0000" and close_rgb(red["background"], (204, 230, 255))
    if SANS.is_file():
        assert first["Gömülü"]["embedded"] is True
        assert first["Gömülü"]["matched_font"]["family_id"] == "system:dejavu-sans"


def test_text_spans_line_and_block_granularity(api: Api) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(72, 72, 300, 200), "Birinci satir\nIkinci satir", fontsize=12)
    f = api.upload(pdf_bytes(doc))
    lines = api.run("text_spans", [f["id"]], {"granularity": "line"})["data"]["pages"][0]["spans"]
    assert [s["text"] for s in lines] == ["Birinci satir", "Ikinci satir"]
    blocks = api.run("text_spans", [f["id"]], {"granularity": "block"})["data"]["pages"][0]["spans"]
    assert [s["text"] for s in blocks] == ["Birinci satir\nIkinci satir"]
    assert blocks[0]["rect"][1] < lines[1]["rect"][1] + 0.01 and blocks[0]["rect"][3] >= lines[0]["rect"][3]


def test_text_spans_page_cap(api: Api) -> None:
    doc = pymupdf.open()
    for _ in range(201):
        doc.new_page(width=100, height=100)
    f = api.upload(pdf_bytes(doc))
    job = api.run("text_spans", [f["id"]], {})
    assert job["status"] == "failed" and "200" in job["error"]["en"]


# -- edit ops ---------------------------------------------------------------------------------
def test_every_edit_op_type(api: Api) -> None:
    doc = _doc_with_text()
    doc.new_page()
    f = api.upload(pdf_bytes(doc))
    from PIL import Image

    img = png_data_url(Image.new("RGB", (40, 20), (0, 128, 0)))
    ops: list[dict[str, Any]] = [
        {"type": "text", "page": 1, "rect": [72, 500, 300, 560], "text": "Yeni kutu", "size": 14, "align": "center"},
        {"type": "whiteout", "page": 1, "rect": [400, 700, 450, 720], "color": "#FFFFFF"},
        {"type": "rect", "page": 1, "rect": [400, 600, 450, 650], "fill": "#FF0000", "width": 2},
        {"type": "ellipse", "page": 1, "rect": [460, 600, 500, 650], "stroke": None, "fill": "#00FF00"},
        {"type": "line", "page": 1, "from": [100, 100], "to": [200, 150]},
        {"type": "arrow", "page": 1, "from": [100, 200], "to": [200, 250], "color": "#0000FF", "opacity": 0.5},
        {"type": "ink", "page": 1, "paths": [[[300, 300], [310, 320], [330, 310]], [[340, 340]]], "width": 2},
        {"type": "highlight", "page": 1, "rects": [[72, 735, 170, 760]]},
        {"type": "underline", "page": 1, "rects": [[72, 580, 200, 595]], "color": "#00AA00"},
        {"type": "strikeout", "page": 1, "quads": [[[72, 575], [200, 575], [72, 560], [200, 560]]]},
        {"type": "squiggly", "page": 1, "rects": [[72, 540, 200, 555]]},
        {"type": "note", "page": 1, "point": [500, 800], "text": "Not " + TR, "author": "Engin"},
        {"type": "freetext", "page": 1, "rect": [300, 400, 500, 450], "text": "Yorum", "size": 11, "fill": "#FFFFAA"},
        {"type": "image", "page": 1, "rect": [300, 100, 380, 140], "data_url": img, "opacity": 0.5},
        {"type": "image", "page": 2, "rect": [300, 100, 380, 140], "data_url": img, "opacity": 0.5},
        {"type": "link", "page": 1, "rect": [72, 50, 150, 70], "uri": "https://example.com/a?b=1"},
        {"type": "link", "page": 1, "rect": [160, 50, 250, 70], "target_page": 2},
    ]
    out, data = edited(api, f["id"], ops)
    assert data == {"applied": len(ops), "failed": []}
    page = out[0]
    assert "Yeni kutu" in page.get_text()
    kinds = sorted(a.type[1] for a in page.annots())
    assert kinds == sorted(
        [
            "Square",
            "Circle",
            "Line",
            "Line",
            "Ink",
            "Highlight",
            "Underline",
            "StrikeOut",
            "Squiggly",
            "Text",
            "FreeText",
        ]
    )
    links = page.get_links()
    assert {lk.get("uri") for lk in links} >= {"https://example.com/a?b=1"}
    assert any(lk["kind"] == pymupdf.LINK_GOTO and lk["page"] == 1 for lk in links)
    # Whiteout is content, not an annotation.
    assert any(d["fill"] == (1.0, 1.0, 1.0) for d in page.get_drawings())
    # Both pages share a single image object.
    assert len(page.get_images()) == 1 and page.get_images()[0][0] == out[1].get_images()[0][0]
    smask = page.get_images()[0][1]
    assert smask, "opacity is baked into an alpha mask"
    square = next(a for a in page.annots() if a.type[1] == "Square")
    assert square.colors["fill"] == pytest.approx([1, 0, 0])
    arrow = next(a for a in page.annots() if a.type[1] == "Line" and a.line_ends[1])
    assert arrow.line_ends == (pymupdf.PDF_ANNOT_LE_NONE, pymupdf.PDF_ANNOT_LE_OPEN_ARROW)
    assert arrow.opacity == pytest.approx(0.5)
    out.close()


@needs_dejavu
def test_turkish_text_roundtrips_with_embedded_subset_font(api: Api) -> None:
    f = api.upload(pdf_bytes(_doc_with_text()))
    fams = {x["id"]: x for x in api.c.get("/api/fonts").json()}
    bold_id = next(s["id"] for s in fams["system:dejavu-sans"]["styles"] if s["weight"] == 700)
    out, data = edited(
        api,
        f["id"],
        [
            {
                "type": "text",
                "page": 1,
                "rect": [72, 500, 400, 560],
                "text": TR,
                "font": {"family_id": "system:dejavu-sans"},
            },
            {"type": "text", "page": 1, "rect": [72, 400, 400, 460], "text": TR + " B", "font_id": bold_id},
            {
                "type": "text",
                "page": 1,
                "rect": [72, 300, 400, 360],
                "text": TR + " std",
                "font": {"family_id": "standard:times", "weight": 700},
            },
        ],
    )
    assert data["applied"] == 3
    text = out[0].get_text()
    assert TR in text and TR + " B" in text and TR + " std" in text
    names = {str(x[3]) for x in out[0].get_fonts()}
    embedded = [n for n in names if "DejaVu" in n]
    assert any("Bold" in n for n in embedded) and any("Bold" not in n for n in embedded)
    assert all("+" in n for n in embedded), "fonts are subset"
    assert any("Bold" in n and "Nimbus Roman" in n for n in names)
    out.close()


def test_text_box_options(api: Api) -> None:
    f = api.upload(pdf_bytes(_doc_with_text()))
    long = "uzun metin " * 80
    job = edit(
        api, f["id"], [{"type": "text", "page": 1, "rect": [72, 500, 172, 520], "text": long, "shrink_to_fit": False}]
    )
    assert job["status"] == "failed" and "fit" in job["error"]["en"]
    out, _ = edited(
        api,
        f["id"],
        [{"type": "text", "page": 1, "rect": [72, 500, 172, 520], "text": long, "size": 12, "opacity": 0.5}],
    )
    sizes = [
        s["size"]
        for b in out[0].get_text("dict")["blocks"]
        for ln in b["lines"]
        for s in ln["spans"]
        if "uzun" in s["text"]
    ]
    assert sizes and max(sizes) < 12, "shrunk to fit"
    out.close()


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_rotated_page_content_reads_upright(api: Api, rotation: int) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.set_rotation(rotation)
    f = api.upload(pdf_bytes(doc))
    ops = [
        {"type": "text", "page": 1, "rect": [50, 300, 350, 400], "text": "Dik metin", "size": 14},
        {"type": "text", "page": 1, "rect": [50, 50, 350, 250], "text": "Saat yönü", "size": 14, "rotation": 90},
        {"type": "freetext", "page": 1, "rect": [50, 450, 350, 550], "text": "Yorum kutusu"},
        {"type": "image", "page": 1, "rect": [150, 150, 250, 250], "data_url": png_data_url(quadrant_image())},
    ]
    out, data = edited(api, f["id"], ops)
    assert data["applied"] == 4
    page = out[0]
    dirs = {t: visual_dir(page, d) for t, d in lines_of(page)}
    assert dirs["Dik metin"] == (1.0, 0.0)
    assert dirs["Yorum kutusu"] == (1.0, 0.0)
    assert dirs["Saat yönü"] == (0.0, 1.0), "rotated 90° clockwise for the reader"
    # The image's top-left quadrant (red) is at the reader's top-left.
    img_rect = pymupdf.Rect(150, 600 - 250, 250, 600 - 150)  # PDF → unrotated MuPDF space
    vis = pymupdf.Rect(img_rect * page.rotation_matrix).normalize()
    pix = page.get_pixmap()
    tl = pix.pixel(int(vis.x0 + vis.width * 0.25), int(vis.y0 + vis.height * 0.25))
    tr = pix.pixel(int(vis.x0 + vis.width * 0.75), int(vis.y0 + vis.height * 0.25))
    assert (tl, tr) == ((255, 0, 0), (0, 0, 255))
    out.close()


def test_markup_on_rotated_page_follows_reader_orientation(api: Api) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((100, 100), "Alti cizili", fontsize=14, rotate=90)
    page.set_rotation(90)
    hit = page.search_for("Alti cizili")[0]
    rect = to_pdf(page, hit)
    f = api.upload(pdf_bytes(doc))
    out, _ = edited(api, f["id"], [{"type": "underline", "page": 1, "rects": [rect]}])
    page = out[0]
    annot = next(page.annots())
    quad = pymupdf.Quad(annot.vertices[:4]) if len(annot.vertices) >= 4 else None
    assert quad is not None
    # Upper-left of the quad, seen by the reader, is above-left of lower-right.
    m = page.rotation_matrix
    ul, lr = quad.ul * m, quad.lr * m
    assert ul.x < lr.x and ul.y < lr.y
    out.close()


# -- replace ------------------------------------------------------------------------------------
def _table_with_image() -> pymupdf.Document:
    """A table cell holding text with an image right next to it — the v1
    redaction defaults blanked such image pixels and erased the borders."""
    from PIL import Image

    doc = pymupdf.open()
    page = doc.new_page()
    for r in range(3):
        for c in range(3):
            page.draw_rect(
                pymupdf.Rect(72 + c * 150, 72 + r * 30, 222 + c * 150, 102 + r * 30), color=(0, 0, 0), width=0.8
            )
    page.insert_text((76, 120), "Eski metin", fontsize=11)
    page.insert_text((76, 135), "Alt satir kalmali", fontsize=11)
    img = Image.effect_mandelbrot((120, 40), (-2, -1, 1, 1), 50).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    hit = page.search_for("Eski metin")[0]
    page.insert_image(pymupdf.Rect(hit.x1 + 1, hit.y0 - 2, hit.x1 + 61, hit.y1 + 2), stream=buf.getvalue())
    return doc


def _pixels(page: pymupdf.Page, rect: pymupdf.Rect) -> bytes:
    return bytes(page.get_pixmap(clip=rect, dpi=144, annots=False).samples)


def test_replace_keeps_neighbouring_image_and_table_lines(api: Api) -> None:
    doc = _table_with_image()
    page = doc[0]
    hit = page.search_for("Eski metin")[0]
    img_rect = page.get_image_rects(page.get_images()[0][0])[0]
    before_img = _pixels(page, img_rect)
    before_lines = sorted((tuple(round(v, 2) for v in d["rect"])) for d in page.get_drawings())
    data = pdf_bytes(doc)
    f = api.upload(data)
    with pymupdf.open("pdf", data) as ref:
        rect = to_pdf(ref[0], hit)
    out, result = edited(
        api,
        f["id"],
        [
            # Added in the same save, overlapping the replaced text: must survive
            # (v1 ran the redaction after the other ops and wiped it).
            {
                "type": "text",
                "page": 1,
                "rect": [rect[0], rect[1] - 30, rect[0] + 200, rect[1] - 2],
                "text": "Aynı kayıt",
            },
            {"type": "replace", "page": 1, "rect": rect, "text": "Yeni değer"},
        ],
    )
    assert result == {"applied": 2, "failed": []}
    p = out[0]
    text = p.get_text()
    assert "Eski" not in text
    assert "Yeni değer" in text and "Alt satir kalmali" in text and "Aynı kayıt" in text
    assert _pixels(p, img_rect) == before_img
    after_lines = sorted((tuple(round(v, 2) for v in d["rect"])) for d in p.get_drawings())
    assert all(r in after_lines for r in before_lines), "table borders intact"
    new = p.search_for("Yeni değer")[0]
    assert new.y1 == pytest.approx(hit.y1, abs=1.0) and new.x0 == pytest.approx(hit.x0, abs=0.5), "baseline-aligned"
    out.close()


def test_replace_detects_style_and_fits(api: Api) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.draw_rect(pymupdf.Rect(60, 80, 400, 130), color=None, fill=(0.8, 0.9, 1.0))
    page.insert_text((72, 110), "Kisa", fontsize=16, color=(0, 0, 1), fontname="hebo")
    hit = page.search_for("Kisa")[0]
    data = pdf_bytes(doc)
    with pymupdf.open("pdf", data) as ref:
        rect = to_pdf(ref[0], hit)
    f = api.upload(data)
    out, result = edited(
        api,
        f["id"],
        [{"type": "replace", "page": 1, "rect": rect, "text": "Çok daha uzun bir metin ğüş"}],
    )
    assert result["applied"] == 1
    spans = [s for b in out[0].get_text("dict")["blocks"] for ln in b["lines"] for s in ln["spans"]]
    new = next(s for s in spans if "uzun" in s["text"])
    assert new["text"] == "Çok daha uzun bir metin ğüş"
    assert new["color"] == 0x0000FF and "Bold" in new["font"]
    assert new["size"] < 16, "shrunk into the original width"
    assert new["origin"][1] == pytest.approx(110, abs=0.01)
    # Background fill matches the coloured box, not white.
    pix = out[0].get_pixmap(clip=pymupdf.Rect(hit.x1 + 2, hit.y0, hit.x1 + 3, hit.y0 + 1))
    assert close_rgb(pix.pixel(0, 0), (204, 230, 255))
    out.close()


@needs_dejavu
def test_replace_reuses_embedded_font_or_falls_back(api: Api) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "abc def", fontsize=12, fontname="DV", fontfile=str(SANS))
    page.insert_text((72, 140), "xyz", fontsize=12, fontname="DV", fontfile=str(SANS))
    doc.subset_fonts()  # the embedded font now only holds these glyphs
    data = pdf_bytes(doc)
    with pymupdf.open("pdf", data) as ref:
        r1 = to_pdf(ref[0], ref[0].search_for("abc def")[0])
        r2 = to_pdf(ref[0], ref[0].search_for("xyz")[0])
        original = next(str(x[3]) for x in ref[0].get_fonts())
    f = api.upload(data)
    out, result = edited(
        api,
        f["id"],
        [
            {"type": "replace", "page": 1, "rect": r1, "text": "fed cba"},  # covered by the subset
            {"type": "replace", "page": 1, "rect": r2, "text": "İĞÜ"},  # needs glyphs the subset lacks
        ],
    )
    assert result["applied"] == 2
    spans = {s["text"]: s for b in out[0].get_text("dict")["blocks"] for ln in b["lines"] for s in ln["spans"]}
    assert "fed cba" in spans and "İĞÜ" in spans
    assert "DejaVu" in spans["İĞÜ"]["font"], "matched catalogue font (DejaVu) used for new glyphs"
    assert original.split("+")[-1] in {str(x[3]).split("+")[-1] for x in out[0].get_fonts()}
    out.close()


@needs_dejavu
@pytest.mark.parametrize("subset", [False, True])
def test_embedded_font_reuse_decision(subset: bool) -> None:
    """A fully embedded font is reused for new text it can draw; a subset
    whose Unicode cmap is gone can't be trusted with any glyph (no tofu)."""
    from adminpdf.core.editing import FontCache, embedded_font_names, extract_embedded_font, font_key, page_lines

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "abc def", fontsize=12, fontname="DV", fontfile=str(SANS))
    if subset:
        doc.subset_fonts()
    doc = pymupdf.open("pdf", doc.tobytes(garbage=4))
    page = doc[0]
    run = page_lines(page)[0].runs[0]
    assert font_key(run.font) in embedded_font_names(page)
    found = extract_embedded_font(doc, page, run.font)
    assert found is not None and found[0].startswith("xref")
    wf = FontCache(fonts.get_catalogue()).from_buffer(*found)
    assert wf is not None
    assert wf.covers("fed cba " + TR) is not subset
    doc.close()


def test_replace_background_none_and_delete(api: Api) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Silinecek kelime burada", fontsize=12)
    hit = page.search_for("kelime")[0]
    data = pdf_bytes(doc)
    with pymupdf.open("pdf", data) as ref:
        rect = to_pdf(ref[0], hit)
    f = api.upload(data)
    out, result = edited(api, f["id"], [{"type": "replace", "page": 1, "rect": rect, "text": "", "background": "none"}])
    assert result["applied"] == 1
    words = [w[4] for w in out[0].get_text("words")]
    assert words == ["Silinecek", "burada"]
    assert out[0].get_drawings() == []
    out.close()


# -- validation & failures ---------------------------------------------------------------------
def test_partial_failures_are_reported(api: Api) -> None:
    f = api.upload(pdf_bytes(_doc_with_text()))
    ops = [
        {"type": "rect", "page": 1, "rect": [100, 100, 200, 200]},
        {"type": "rect", "page": 7, "rect": [100, 100, 200, 200]},
        {"type": "rect", "page": 1, "rect": [5000, 5000, 5100, 5100]},
        {"type": "text", "page": 1, "rect": [100, 300, 200, 350], "text": "x", "font": {"family_id": "nope:x"}},
        {"type": "image", "page": 1, "rect": [100, 300, 200, 350], "data_url": "data:image/png;base64,AAAA"},
        {"type": "delete_annot", "page": 1, "xref": 99999},
        {"type": "link", "page": 1, "rect": [100, 300, 200, 350], "target_page": 50},
    ]
    job = edit(api, f["id"], ops)
    assert job["status"] == "done", job
    data = job["data"]
    assert data["applied"] == 1
    assert [x["index"] for x in data["failed"]] == [1, 2, 3, 4, 5, 6]
    by_index = {x["index"]: x for x in data["failed"]}
    assert "Page 7" in by_index[1]["error_en"] and "Sayfa 7" in by_index[1]["error_tr"]
    assert "outside" in by_index[2]["error_en"]
    assert "not found" in by_index[3]["error_en"]
    assert "image" in by_index[4]["error_en"]
    assert "Annotation not found" in by_index[5]["error_en"]
    assert "Target page" in by_index[6]["error_en"]


def test_all_failing_is_a_user_error(api: Api) -> None:
    f = api.upload(pdf_bytes(_doc_with_text()))
    job = edit(api, f["id"], [{"type": "rect", "page": 9, "rect": [1, 1, 50, 50]}])
    assert job["status"] == "failed"
    assert job["error"]["en"].startswith("No edit could be applied")


@pytest.mark.parametrize(
    "op",
    [
        {"type": "rect", "page": 1, "rect": [0, 0, 1e9, 10]},
        {"type": "rect", "page": 1, "rect": [0, 0, 10]},
        {"type": "rect", "page": 0, "rect": [0, 0, 10, 10]},
        {"type": "teleport", "page": 1},
        {"type": "rect", "page": 1, "rect": [0, 0, 10, 10], "color": "red"},
        {"type": "link", "page": 1, "rect": [0, 0, 10, 10], "uri": "javascript:alert(1)"},
        {"type": "link", "page": 1, "rect": [0, 0, 10, 10]},
        {"type": "ink", "page": 1, "paths": [[[0, 0]] * 100_001]},
        {"type": "highlight", "page": 1},
        {"type": "text", "page": 1, "rect": [0, 0, 10, 10], "text": "x" * 20_001},
        {"type": "text", "page": 1, "rect": [0, 0, 10, 10], "text": "x", "rotation": 45},
    ],
)
def test_invalid_operations_rejected_upfront(api: Api, op: dict[str, Any]) -> None:
    f = api.upload(pdf_bytes(_doc_with_text()))
    assert api.start("edit", [f["id"]], {"operations": [op]}).status_code == 422


def test_non_finite_numbers_rejected(api: Api) -> None:
    f = api.upload(pdf_bytes(_doc_with_text()))
    op = '{"type":"rect","page":1,"rect":[0,0,NaN,10]}'
    body = '{"inputs":[{"id":"' + f["id"] + '"}],"params":{"operations":[' + op + "]}}"
    r = api.c.post("/api/ops/edit", content=body, headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_operation_count_capped(api: Api) -> None:
    f = api.upload(pdf_bytes(_doc_with_text()))
    ops = [{"type": "whiteout", "page": 1, "rect": [0, 0, 10, 10]}] * 20_001
    assert api.start("edit", [f["id"]], {"operations": ops}).status_code == 422


# -- annotations ----------------------------------------------------------------------------------
def test_annotations_list_move_update_delete(api: Api) -> None:
    f = api.upload(pdf_bytes(_doc_with_text()))
    job = edit(
        api,
        f["id"],
        [
            {"type": "ink", "page": 1, "paths": [[[100, 100], [150, 150], [200, 120]]], "color": "#112233"},
            {"type": "highlight", "page": 1, "rects": [[72, 735, 170, 760]], "author": "Ayşe"},
            {"type": "rect", "page": 1, "rect": [300, 300, 400, 350], "stroke": "#FF0000"},
            {"type": "note", "page": 1, "point": [500, 700], "text": "Silinecek not"},
            {"type": "freetext", "page": 1, "rect": [300, 500, 500, 550], "text": "Yorum", "color": "#0000FF"},
        ],
    )
    assert job["status"] == "done"
    fid = job["result"]["id"]
    listing = api.run("annotations", [fid], {})
    assert listing["status"] == "done"
    pages = listing["data"]["pages"]
    assert len(pages) == 1 and pages[0]["page"] == 1 and pages[0]["rotation"] == 0
    annots = {a["type"]: a for a in pages[0]["annotations"]}
    assert set(annots) == {"Ink", "Highlight", "Square", "Text", "FreeText"}
    ink, square = annots["Ink"], annots["Square"]
    assert ink["color"] == "#112233" and ink["paths"][0][0] == pytest.approx([100, 100], abs=0.01)
    assert ink["rect"][0] < 100 < ink["rect"][2] and ink["rect"][1] < 100 < ink["rect"][3]
    assert square["rect"] == pytest.approx([299.5, 299.5, 400.5, 350.5], abs=1)
    assert annots["Highlight"]["author"] == "Ayşe" and annots["Highlight"]["modified"].startswith("20")
    assert annots["FreeText"]["color"] == "#0000FF" and annots["FreeText"]["contents"] == "Yorum"

    dx, dy = 100, 50
    moved_ink = [ink["rect"][0] + dx, ink["rect"][1] + dy, ink["rect"][2] + dx, ink["rect"][3] + dy]
    job = edit(
        api,
        fid,
        [
            {"type": "move_annot", "page": 1, "xref": ink["xref"], "rect": moved_ink},
            {"type": "move_annot", "page": 1, "xref": square["xref"], "rect": [50, 50, 150, 100]},
            {"type": "move_annot", "page": 1, "xref": annots["FreeText"]["xref"], "rect": [50, 400, 250, 450]},
            {"type": "update_annot", "page": 1, "xref": square["xref"], "color": "#00FF00", "contents": "güncel"},
            {"type": "delete_annot", "page": 1, "xref": annots["Text"]["xref"]},
        ],
    )
    assert job["status"] == "done" and job["data"]["failed"] == []
    after = api.run("annotations", [job["result"]["id"]], {})["data"]["pages"][0]["annotations"]
    by_type = {a["type"]: a for a in after}
    assert "Text" not in by_type
    assert by_type["Ink"]["paths"][0][0] == pytest.approx([200, 150], abs=0.01)
    assert by_type["Ink"]["rect"] == pytest.approx(moved_ink, abs=1)
    assert by_type["Square"]["rect"] == pytest.approx([50, 50, 150, 100], abs=1)
    assert by_type["Square"]["color"] == "#00FF00" and by_type["Square"]["contents"] == "güncel"
    assert by_type["FreeText"]["rect"] == pytest.approx([50, 400, 250, 450], abs=1)
    assert by_type["FreeText"]["color"] == "#0000FF"


def test_annotation_rects_on_rotated_page(api: Api) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.set_rotation(90)
    f = api.upload(pdf_bytes(doc))
    job = edit(api, f["id"], [{"type": "rect", "page": 1, "rect": [100, 200, 150, 260]}])
    listing = api.run("annotations", [job["result"]["id"]], {})["data"]["pages"][0]
    assert listing["rotation"] == 90
    assert listing["annotations"][0]["rect"] == pytest.approx([99.5, 199.5, 150.5, 260.5], abs=1)
