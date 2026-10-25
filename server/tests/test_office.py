from __future__ import annotations

import io
import zipfile

import pymupdf
import pytest

from adminpdf.ops.office import find_soffice, to_cell

from .conftest import Api, make_docx, make_pdf, make_table_pdf, make_xlsx

needs_lo = pytest.mark.skipif(find_soffice() is None, reason="LibreOffice not installed")


def text_of(data: bytes) -> str:
    with pymupdf.open("pdf", data) as doc:
        return "\n".join(p.get_text() for p in doc)


@pytest.mark.parametrize(
    ("raw", "mode", "expected"),
    [
        ("1.250,50", "tr", 1250.5),
        ("1,250.50", "en", 1250.5),
        ("300", "tr", 300),
        ("12.5", "tr", "12.5"),  # ambiguous in TR → kept as text
        ("05321234567", "tr", 5321234567),
        ("abc\x01", "tr", "abc"),
        ("1.250,50", "text", "1.250,50"),
    ],
)
def test_to_cell(raw: str, mode: str, expected: object) -> None:
    assert to_cell(raw, mode) == expected


def test_pdf_to_excel_tables_and_no_formula_injection(api: Api) -> None:
    from openpyxl import load_workbook

    f = api.upload(make_table_pdf())
    job = api.run("pdf_to_excel", [f["id"]])
    assert job["status"] == "done", job
    wb = load_workbook(io.BytesIO(api.download(job["result"]["id"])))
    ws = wb.worksheets[0]
    values = [[c.value for c in row] for row in ws.iter_rows()]
    assert values[0] == ["Ad", "Tutar", "Not"]
    assert values[1][1] == 1250.5
    assert ws.cell(row=2, column=3).data_type == "s"  # literal text, not a formula


def test_pdf_to_excel_without_tables_is_user_error(api: Api) -> None:
    f = api.upload(make_pdf(1))
    job = api.run("pdf_to_excel", [f["id"]])
    assert job["status"] == "failed"
    assert "No tables" in job["error"]["en"]


def test_pdf_to_word(api: Api) -> None:
    import docx

    f = api.upload(make_pdf(2, text="Paragraf"))
    job = api.run("pdf_to_word", [f["id"]])
    assert job["status"] == "done", job
    d = docx.Document(io.BytesIO(api.download(job["result"]["id"])))
    text = "\n".join(p.text for p in d.paragraphs)
    assert "Paragraf 1" in text and "Paragraf 2" in text


def test_office_to_pdf_builtin_engine(api: Api) -> None:
    d = api.upload(make_docx(), "rapor.docx")
    x = api.upload(make_xlsx(), "tablo.xlsx")
    assert d["kind"] == "docx" and x["kind"] == "xlsx"
    job = api.run("office_to_pdf", [d["id"], x["id"]], {"engine": "builtin"})
    assert job["status"] == "done", job
    with zipfile.ZipFile(io.BytesIO(api.download(job["result"]["id"]))) as zf:
        word = text_of(zf.read("rapor.pdf"))
        excel = text_of(zf.read("tablo.pdf"))
    assert "İĞŞÇÖÜ" in word and "Şükrü" in word
    assert "Satış" in excel and "Çay" in excel


@needs_lo
def test_office_to_pdf_libreoffice(api: Api) -> None:
    d = api.upload(make_docx(), "rapor.docx")
    job = api.run("office_to_pdf", [d["id"]], {"engine": "libreoffice"})
    assert job["status"] == "done", job
    assert "Şükrü" in text_of(api.download(job["result"]["id"]))


def test_zip_bomb_rejected(api: Api) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<x/>")
        zf.writestr("word/document.xml", b"0" * (50 * 1024 * 1024))
    f = api.upload(buf.getvalue(), "bomb.docx")
    job = api.run("office_to_pdf", [f["id"]], {"engine": "builtin"})
    assert job["status"] == "failed"
    assert "zip bomb" in job["error"]["en"]
