"""End-to-end: upload → job in a worker process → result."""

from __future__ import annotations

import io
import zipfile

import pymupdf
import pytest

from adminpdf.core.errors import UserError
from adminpdf.core.pdf import parse_page_spec

from .conftest import Api, make_image_pdf, make_pdf, make_png


def open_bytes(data: bytes) -> pymupdf.Document:
    return pymupdf.open("pdf", data)


def page_texts(data: bytes) -> list[str]:
    with open_bytes(data) as doc:
        return [p.get_text().strip() for p in doc]


# -- page spec -----------------------------------------------------------------
@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("", [0, 1, 2, 3, 4]),
        ("1-3,5", [0, 1, 2, 4]),
        ("4-", [3, 4]),
        ("-2", [0, 1]),
        ("son", [4]),
        ("3-1", [2, 1, 0]),
        ("2,2", [1, 1]),
    ],
)
def test_parse_page_spec(spec: str, expected: list[int]) -> None:
    assert parse_page_spec(spec, 5) == expected


@pytest.mark.parametrize("spec", ["0", "6", "a-b", "1-9", ","])
def test_parse_page_spec_rejects(spec: str) -> None:
    with pytest.raises(UserError):
        parse_page_spec(spec, 5)


# -- catalogue & validation ------------------------------------------------------
def test_catalogue_has_schemas(api: Api) -> None:
    ops = {o["name"]: o for o in api.c.get("/api/ops").json()}
    assert {"merge", "split", "compress", "encrypt", "watermark", "page_numbers"} <= set(ops)
    schema = ops["split"]["schema"]
    assert schema["properties"]["mode"]["title_tr"] == "Bölme şekli"


def test_invalid_params_give_readable_422(api: Api) -> None:
    f = api.upload(make_pdf(2))
    r = api.start("watermark", [f["id"]], {"text": "", "font_size": 9999})
    assert r.status_code == 422
    fields = {e["field"] for e in r.json()["detail"]}
    assert fields == {"text", "font_size"}


def test_unknown_param_rejected(api: Api) -> None:
    f = api.upload(make_pdf(2))
    assert api.start("rotate", [f["id"]], {"angle": 90, "evil": 1}).status_code == 422


def test_wrong_input_kind_rejected(api: Api) -> None:
    img = api.upload(make_png(), "a.png")
    assert api.start("compress", [img["id"]]).status_code == 415


def test_input_count_enforced(api: Api) -> None:
    f = api.upload(make_pdf(1))
    assert api.start("merge", [f["id"]]).status_code == 422


# -- page operations ---------------------------------------------------------------
def test_merge_keeps_order_and_adds_bookmarks(api: Api) -> None:
    a = api.upload(make_pdf(2, text="A"), "a.pdf")
    b = api.upload(make_pdf(1, text="B"), "b.pdf")
    job = api.run("merge", [b["id"], a["id"]])
    assert job["status"] == "done", job
    data = api.download(job["result"]["id"])
    assert page_texts(data) == ["B 1", "A 1", "A 2"]
    with open_bytes(data) as doc:
        assert [t[1] for t in doc.get_toc()] == ["b", "a"]


def test_split_ranges_bundles_zip(api: Api) -> None:
    f = api.upload(make_pdf(5), "doc.pdf")
    job = api.run("split", [f["id"]], {"mode": "ranges", "ranges": "1-2, 3, 4-"})
    assert job["status"] == "done", job
    assert len(job["outputs"]) == 3
    with zipfile.ZipFile(io.BytesIO(api.download(job["result"]["id"]))) as zf:
        names = zf.namelist()
        assert names == ["doc_s1-2.pdf", "doc_s3.pdf", "doc_s4-5.pdf"]
        assert page_texts(zf.read("doc_s4-5.pdf")) == ["Sayfa 4", "Sayfa 5"]


def test_split_each(api: Api) -> None:
    f = api.upload(make_pdf(3))
    job = api.run("split", [f["id"]], {"mode": "each"})
    assert len(job["outputs"]) == 3


def test_extract_delete_reorder_rotate(api: Api) -> None:
    f = api.upload(make_pdf(4))
    ex = api.run("extract_pages", [f["id"]], {"pages": "2,4"})
    assert page_texts(api.download(ex["result"]["id"])) == ["Sayfa 2", "Sayfa 4"]

    de = api.run("delete_pages", [f["id"]], {"pages": "1-2"})
    assert page_texts(api.download(de["result"]["id"])) == ["Sayfa 3", "Sayfa 4"]

    ro = api.run("reorder", [f["id"]], {"order": "4,1,1"})
    assert page_texts(api.download(ro["result"]["id"])) == ["Sayfa 4", "Sayfa 1", "Sayfa 1"]

    rt = api.run("rotate", [f["id"]], {"angle": 90, "pages": "2"})
    with open_bytes(api.download(rt["result"]["id"])) as doc:
        assert [p.rotation for p in doc] == [0, 90, 0, 0]


def test_delete_all_pages_is_a_user_error(api: Api) -> None:
    f = api.upload(make_pdf(2))
    job = api.run("delete_pages", [f["id"]], {"pages": "1-2"})
    assert job["status"] == "failed"
    assert job["error"]["en"] == "You cannot delete every page."


def test_out_of_range_page_is_a_user_error(api: Api) -> None:
    f = api.upload(make_pdf(2))
    job = api.run("extract_pages", [f["id"]], {"pages": "5"})
    assert job["status"] == "failed"
    assert "out of range" in job["error"]["en"]


def test_result_can_feed_next_operation(api: Api) -> None:
    f = api.upload(make_pdf(3))
    first = api.run("delete_pages", [f["id"]], {"pages": "1"})
    second = api.run("rotate", [first["result"]["id"]], {"angle": 180})
    with open_bytes(api.download(second["result"]["id"])) as doc:
        assert doc.page_count == 2
        assert doc[0].rotation == 180


# -- compress -------------------------------------------------------------------------
def test_compress_shrinks_and_keeps_images_intact(api: Api) -> None:
    src = make_image_pdf()
    f = api.upload(src, "photo.pdf")
    job = api.run("compress", [f["id"]], {"preset": "screen"})
    assert job["status"] == "done", job
    out = api.download(job["result"]["id"])
    assert len(out) < len(src) * 0.5
    # v1 regression: JPEG bytes were written under the wrong filter and the
    # page rendered as noise. Compare renders.
    with open_bytes(src) as a, open_bytes(out) as b:
        pa = a[0].get_pixmap(dpi=40)
        pb = b[0].get_pixmap(dpi=40)
        diff = sum(abs(x - y) for x, y in zip(pa.samples, pb.samples, strict=True)) / len(pa.samples)
        assert diff < 8, diff


def test_compress_lossless(api: Api) -> None:
    f = api.upload(make_pdf(3))
    job = api.run("compress", [f["id"]], {"preset": "lossless"})
    assert job["status"] == "done"
    assert page_texts(api.download(job["result"]["id"]))[0] == "Sayfa 1"


# -- protect ----------------------------------------------------------------------------
def test_encrypt_permissions_are_enforced(api: Api) -> None:
    f = api.upload(make_pdf(1))
    job = api.run("encrypt", [f["id"]], {"user_password": "acik", "allow_copy": False, "allow_print": True})
    assert job["status"] == "done", job
    with open_bytes(api.download(job["result"]["id"])) as doc:
        assert doc.needs_pass
        assert doc.authenticate("acik") == 2  # user rights only
        assert not doc.permissions & pymupdf.PDF_PERM_COPY
        assert doc.permissions & pymupdf.PDF_PERM_PRINT


def test_encrypt_rejects_equal_passwords(api: Api) -> None:
    f = api.upload(make_pdf(1))
    job = api.run("encrypt", [f["id"]], {"user_password": "x", "owner_password": "x"})
    assert job["status"] == "failed"


def test_wrong_password_reports_clearly(api: Api) -> None:
    f = api.upload(make_pdf(1))
    enc = api.run("encrypt", [f["id"]], {"user_password": "u", "owner_password": "o"})
    rid = enc["result"]["id"]
    assert api.c.get(f"/api/files/{rid}/meta").json()["encrypted"] is True
    job = api.run("rotate", [rid], {"angle": 90}, password="bad")
    assert job["status"] == "failed"
    assert "password" in job["error"]["en"]


def test_decrypt_needs_owner_password_for_restricted_file(api: Api) -> None:
    f = api.upload(make_pdf(1))
    enc = api.run("encrypt", [f["id"]], {"user_password": "u", "owner_password": "o", "allow_copy": False})
    rid = enc["result"]["id"]
    assert api.run("decrypt", [rid], password="u")["status"] == "failed"
    ok = api.run("decrypt", [rid], password="o")
    assert ok["status"] == "done"
    with open_bytes(api.download(ok["result"]["id"])) as doc:
        assert not doc.needs_pass
        assert not doc.is_encrypted


# -- stamp ------------------------------------------------------------------------------
def test_page_numbers_template_is_not_a_format_string(api: Api) -> None:
    f = api.upload(make_pdf(2))
    job = api.run("page_numbers", [f["id"]], {"template": "{n:>999999999} {n}/{total}"})
    assert job["status"] == "done", job
    texts = page_texts(api.download(job["result"]["id"]))
    assert "{n:>999999999} 1/2" in texts[0]


def test_header_footer_positions_on_rotated_page(api: Api) -> None:
    f = api.upload(make_pdf(1))
    rot = api.run("rotate", [f["id"]], {"angle": 90})
    job = api.run("header_footer", [rot["result"]["id"]], {"footer_center": "ALT-{n}", "header_left": "UST"})
    assert job["status"] == "done", job
    with open_bytes(api.download(job["result"]["id"])) as doc:
        page = doc[0]
        vis = page.rect  # PyMuPDF reports the visible (rotated) frame
        for word, where in (("ALT-1", "bottom"), ("UST", "top")):
            hits = page.search_for(word)
            assert hits, word
            r = hits[0] * page.rotation_matrix
            assert r.width > r.height, f"{word} is not upright"
            if where == "bottom":
                assert r.y1 > vis.height * 0.9
            else:
                assert r.y0 < vis.height * 0.1


def test_watermark_turkish_text(api: Api) -> None:
    f = api.upload(make_pdf(2))
    job = api.run("watermark", [f["id"]], {"text": "GİZLİ ŞĞÜ", "pages": "2"})
    assert job["status"] == "done", job
    texts = page_texts(api.download(job["result"]["id"]))
    assert "GİZLİ" not in texts[0]
    assert "GİZLİ ŞĞÜ" in texts[1] or "GIZLI" in texts[1]


# -- convert ------------------------------------------------------------------------------
def test_images_to_pdf_and_back(api: Api) -> None:
    a = api.upload(make_png(300, 150), "a.png")
    b = api.upload(make_png(100, 400), "b.png")
    job = api.run("images_to_pdf", [a["id"], b["id"]], {"page_size": "a4"})
    assert job["status"] == "done", job
    pdf_id = job["result"]["id"]
    with open_bytes(api.download(pdf_id)) as doc:
        assert doc.page_count == 2
        assert doc[0].rect.width > doc[0].rect.height  # landscape for wide image

    imgs = api.run("pdf_to_images", [pdf_id], {"format": "jpg", "dpi": 72})
    assert imgs["status"] == "done", imgs
    with zipfile.ZipFile(io.BytesIO(api.download(imgs["result"]["id"]))) as zf:
        assert len(zf.namelist()) == 2


def test_render_pixel_budget_caps_huge_pages(api: Api) -> None:
    # 200 × 200 inch page at 600 DPI would be 14 400 MP without the cap.
    f = api.upload(make_pdf(1, size=(14400, 14400)))
    job = api.run("pdf_to_images", [f["id"]], {"dpi": 600, "format": "jpg", "quality": 30})
    assert job["status"] == "done", job
