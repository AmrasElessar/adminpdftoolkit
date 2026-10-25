from __future__ import annotations

import pytest

from adminpdf.core.files import safe_filename, sniff

from .conftest import Api, make_pdf, make_png


def test_upload_pdf_reports_pages(api: Api) -> None:
    meta = api.upload(make_pdf(4), "rapor.pdf")
    assert meta["kind"] == "pdf"
    assert meta["pages"] == 4
    assert meta["name"] == "rapor.pdf"
    assert api.download(meta["id"]).startswith(b"%PDF")


def test_upload_unicode_name(api: Api) -> None:
    meta = api.upload(make_pdf(1), "%C3%A7%C4%B1kt%C4%B1%20%C5%9Fubat.pdf")
    assert meta["name"] == "çıktı şubat.pdf"


def test_upload_over_limit_is_rejected(api: Api) -> None:
    big = b"%PDF-1.7\n" + b"0" * (6 * 1024 * 1024)
    r = api.c.put("/api/files", content=big, headers={"X-Filename": "big.pdf"})
    assert r.status_code == 413


def test_empty_upload_rejected(api: Api) -> None:
    r = api.c.put("/api/files", content=b"", headers={"X-Filename": "e.pdf"})
    assert r.status_code == 400


def test_fake_pdf_is_not_a_pdf(api: Api) -> None:
    meta = api.upload(b"%PDF-1.7 garbage that is not a pdf", "x.pdf")
    assert meta["kind"] == "other"


def test_delete_and_missing(api: Api) -> None:
    meta = api.upload(make_png(), "a.png")
    assert meta["kind"] == "image"
    assert api.c.delete(f"/api/files/{meta['id']}").status_code == 204
    assert api.c.get(f"/api/files/{meta['id']}").status_code == 404
    assert api.c.get("/api/files/..%2f..%2fetc").status_code == 404


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd", "passwd"),
        ("C:\\Windows\\evil.pdf", "evil.pdf"),
        ("..pdf", "file.pdf"),
        (".", "file"),
        ("CON.pdf", "file.pdf"),
        ("a\x00b<c>.pdf", "a_b_c_.pdf"),
        ("  rapor.pdf  ", "rapor.pdf"),
    ],
)
def test_safe_filename(raw: str, expected: str) -> None:
    assert safe_filename(raw) == expected


def test_sniff_ignores_extension_for_magic() -> None:
    assert sniff(make_png(), "looks.pdf")[0] == "image"
    assert sniff(b"PK\x03\x04....", "doc.docx")[0] == "docx"
    assert sniff(b"PK\x03\x04....", "archive.zip")[0] == "other"
