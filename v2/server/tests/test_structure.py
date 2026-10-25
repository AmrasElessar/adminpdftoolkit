"""Metadata, bookmarks and attachments."""

from __future__ import annotations

import io
import zipfile

import pymupdf

from .conftest import Api, make_pdf, make_png


def open_bytes(data: bytes) -> pymupdf.Document:
    return pymupdf.open("pdf", data)


# -- metadata ------------------------------------------------------------------------
def make_meta_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Metin")
    doc.set_metadata({"title": "Eski", "author": "Ayse", "creator": "Word"})
    doc.set_xml_metadata('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF/></x:xmpmeta>')
    data: bytes = doc.tobytes()
    doc.close()
    return data


def test_set_metadata_merges(api: Api) -> None:
    f = api.upload(make_meta_pdf())
    job = api.run("set_metadata", [f["id"]], {"title": "Yeni Başlık", "keywords": "kvkk, sözleşme"})
    assert job["status"] == "done", job
    with open_bytes(api.download(job["result"]["id"])) as doc:
        m = doc.metadata
        assert m["title"] == "Yeni Başlık" and m["keywords"] == "kvkk, sözleşme"
        assert m["author"] == "Ayse" and m["creator"] == "Word"
        assert doc.get_xml_metadata()


def test_set_metadata_clear_others(api: Api) -> None:
    f = api.upload(make_meta_pdf())
    job = api.run("set_metadata", [f["id"]], {"title": "Tek", "clear_others": True})
    with open_bytes(api.download(job["result"]["id"])) as doc:
        assert doc.metadata["title"] == "Tek" and not doc.metadata["author"]
        assert not doc.get_xml_metadata()
    empty = api.run("set_metadata", [f["id"]], {})
    assert empty["status"] == "failed"


def test_remove_metadata(api: Api) -> None:
    f = api.upload(make_meta_pdf())
    job = api.run("remove_metadata", [f["id"]])
    assert job["status"] == "done", job
    with open_bytes(api.download(job["result"]["id"])) as doc:
        assert not any(v for k, v in doc.metadata.items() if k not in ("format", "encryption"))
        assert not doc.get_xml_metadata()
        assert doc[0].get_text().strip() == "Metin"


# -- outline ---------------------------------------------------------------------------
def test_outline_roundtrip(api: Api) -> None:
    f = api.upload(make_pdf(4))
    items = [
        {"level": 1, "title": "Giriş", "page": 1},
        {"level": 2, "title": "Amaç ve kapsam", "page": 2},
        {"level": 1, "title": "Ekler", "page": 4},
    ]
    job = api.run("set_outline", [f["id"]], {"items": items})
    assert job["status"] == "done", job
    got = api.run("get_outline", [job["result"]["id"]])
    assert got["data"]["items"] == items
    # Clearing the outline is allowed.
    cleared = api.run("set_outline", [job["result"]["id"]], {"items": []})
    assert api.run("get_outline", [cleared["result"]["id"]])["data"]["items"] == []


def test_set_outline_validation(api: Api) -> None:
    f = api.upload(make_pdf(2))
    jump = api.run("set_outline", [f["id"]], {"items": [{"level": 2, "title": "A", "page": 1}]})
    assert jump["status"] == "failed"
    out = api.run("set_outline", [f["id"]], {"items": [{"level": 1, "title": "A", "page": 3}]})
    assert out["status"] == "failed"
    long = api.start("set_outline", [f["id"]], {"items": [{"level": 1, "title": "x" * 301, "page": 1}]})
    assert long.status_code == 422


def make_headed_pdf() -> bytes:
    doc = pymupdf.open()
    body = "Bu paragraf govde metnidir ve cok sayida karakter icerir. " * 3
    plan = [
        [("Rapor Basligi", 24), ("1. Giris", 16), (body, 10), ("1.1 Amac", 13), (body, 10)],
        [("2. Yontem", 16), (body, 10), ("Bu uzun baslik\niki satira yayiliyor", 16), (body, 10)],
        [("3. Sonuc", 16), (body, 10), (body, 10)],
    ]
    for n, items in enumerate(plan, 1):
        page = doc.new_page(width=595, height=842)
        y = 60.0
        page.insert_text((72, 30), "KURUM ADI - GIZLI", fontsize=16)  # running header
        for text, size in items:
            rect = pymupdf.Rect(72, y, 523, y + 200)
            used = page.insert_textbox(rect, text, fontsize=size)
            y += 200 - used + size * 0.3 if used >= 0 else 200
        page.insert_text((290, 820), f"Sayfa {n}", fontsize=16)  # running footer
    data: bytes = doc.tobytes()
    doc.close()
    return data


def test_auto_bookmarks(api: Api) -> None:
    f = api.upload(make_headed_pdf())
    job = api.run("auto_bookmarks", [f["id"]], {"max_level": 3})
    assert job["status"] == "done", job
    outline = api.run("get_outline", [job["result"]["id"]])["data"]["items"]
    titles = [(i["level"], i["title"], i["page"]) for i in outline]
    assert titles == [
        (1, "Rapor Basligi", 1),
        (2, "1. Giris", 1),
        (3, "1.1 Amac", 1),
        (2, "2. Yontem", 2),
        (2, "Bu uzun baslik iki satira yayiliyor", 2),
        (2, "3. Sonuc", 3),
    ]
    job1 = api.run("auto_bookmarks", [f["id"]], {"max_level": 1})
    outline1 = api.run("get_outline", [job1["result"]["id"]])["data"]["items"]
    assert [i["title"] for i in outline1] == ["Rapor Basligi"]


def test_auto_bookmarks_keeps_existing(api: Api) -> None:
    f = api.upload(make_headed_pdf())
    first = api.run("set_outline", [f["id"]], {"items": [{"level": 1, "title": "Mevcut", "page": 1}]})
    job = api.run("auto_bookmarks", [first["result"]["id"]], {"max_level": 1, "replace_existing": False})
    outline = api.run("get_outline", [job["result"]["id"]])["data"]["items"]
    assert [i["title"] for i in outline] == ["Mevcut", "Rapor Basligi"]


def test_auto_bookmarks_no_headings(api: Api) -> None:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Sadece govde metni", fontsize=11)
    f = api.upload(doc.tobytes())
    assert api.run("auto_bookmarks", [f["id"]])["status"] == "failed"


# -- attachments ---------------------------------------------------------------------------
def test_attachments_add_list_extract(api: Api) -> None:
    f = api.upload(make_pdf(1))
    png = api.upload(make_png(), "logo.png")
    job = api.run("attachment_add", [f["id"]], {"file": png["id"], "description": "Kurum logosu"})
    assert job["status"] == "done", job
    again = api.run("attachment_add", [job["result"]["id"]], {"file": png["id"]})
    pdf_id = again["result"]["id"]
    listing = api.run("attachments_list", [pdf_id])["data"]
    assert listing["total"] == 2
    assert {a["filename"] for a in listing["attachments"]} == {"logo.png", "logo (2).png"}
    assert any(a["description"] == "Kurum logosu" for a in listing["attachments"])
    ex = api.run("attachments_extract", [pdf_id])
    assert ex["status"] == "done", ex
    with zipfile.ZipFile(io.BytesIO(api.download(ex["result"]["id"]))) as zf:
        assert sorted(zf.namelist()) == ["logo (2).png", "logo.png"]
        assert zf.read("logo.png") == make_png()


def test_attachments_extract_sanitizes_names(api: Api) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    doc.embfile_add("evil", b"payload", filename="../../etc/passwd", ufilename="../../etc/passwd")
    doc.embfile_add("dup", b"two", filename="passwd", ufilename="passwd")
    page.add_file_annot(pymupdf.Point(72, 72), b"annot-data", "C:\\Windows\\note.txt")
    f = api.upload(doc.tobytes())
    doc.close()
    listing = api.run("attachments_list", [f["id"]])["data"]
    assert listing["total"] == 3
    assert any(a["page"] == 1 for a in listing["attachments"])
    ex = api.run("attachments_extract", [f["id"]])
    with zipfile.ZipFile(io.BytesIO(api.download(ex["result"]["id"]))) as zf:
        names = zf.namelist()
        assert all("/" not in n and "\\" not in n and ".." not in n for n in names)
        assert sorted(names) == ["note.txt", "passwd", "passwd (2)"]
        assert zf.read("note.txt") == b"annot-data"


def test_attachments_extract_none(api: Api) -> None:
    f = api.upload(make_pdf(1))
    assert api.run("attachments_extract", [f["id"]])["status"] == "failed"
    assert api.run("attachments_list", [f["id"]])["data"] == {"attachments": [], "total": 0}
