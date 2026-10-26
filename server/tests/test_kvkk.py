from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

import adminpdf
from adminpdf.ops.kvkk import vkn_valid

from .conftest import Api

FONT = str(Path(adminpdf.__file__).parent / "assets" / "fonts" / "DejaVuSans.ttf")


def _tckn(nine: str) -> str:
    d = [int(c) for c in nine]
    d10 = ((sum(d[0:9:2]) * 7) - sum(d[1:8:2])) % 10
    d11 = (sum(d) + d10) % 10
    return nine + str(d10) + str(d11)


def _vkn(nine: str) -> str:
    for last in range(10):
        if vkn_valid(nine + str(last)):
            return nine + str(last)
    raise AssertionError


TCKN = _tckn("123456789")
VKN = _vkn("123456789")


def kvkk_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    lines = [
        "Ad Soyad: Ayşe Yılmaz",
        f"T.C. Kimlik No {TCKN}",
        "Adres: Atatürk Cad. No 5 Kadıköy İstanbul",
        "Doğum Tarihi: 01.02.1990",
        "Telefon 0532 123 45 67 e-posta ayse@example.com",
        f"Vergi No: {VKN}   Plaka 34 ABC 123",
        "Sağlık raporu ektedir.",
        "Bu satır kişisel veri içermez.",
    ]
    y = 80
    for text in lines:
        page.insert_text((60, y), text, fontsize=12, fontname="dj", fontfile=FONT)
        y += 24
    page.insert_image(pymupdf.Rect(60, 400, 300, 500), stream=_png())
    data: bytes = doc.tobytes()
    return data


def _png() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (240, 100), (20, 120, 200)).save(buf, "PNG")
    return buf.getvalue()


def test_vkn_checksum() -> None:
    assert vkn_valid(VKN)
    assert not vkn_valid(VKN[:-1] + str((int(VKN[-1]) + 1) % 10))


def test_scan_finds_and_suggests(api: Api) -> None:
    f = api.upload(kvkk_pdf())
    job = api.run("kvkk_scan", [f["id"]])
    assert job["status"] == "done", job
    data = job["data"]
    kinds = {x["kind"] for x in data["findings"]}
    assert {"name", "tckn", "address", "birth", "phone", "email", "vkn", "plate", "special"} <= kinds
    name = next(x for x in data["findings"] if x["kind"] == "name")
    assert name["text"].startswith("Ayş") and "*" in name["text"]  # masked in the response
    assert TCKN not in str(data)  # raw values never leave the server
    assert data["kinds"]["tckn"]["suggested"] == "black"
    assert data["kinds"]["special"]["special"] is True


def test_apply_each_action(api: Api) -> None:
    f = api.upload(kvkk_pdf())
    findings = api.run("kvkk_scan", [f["id"]])["data"]["findings"]
    pick = {x["kind"]: x for x in findings}
    items = [
        {"page": 1, "rects": pick["tckn"]["rects"], "action": "black"},
        {"page": 1, "rects": pick["phone"]["rects"], "action": "mask", "mask": pick["phone"]["mask"]},
        {"page": 1, "rects": pick["name"]["rects"], "action": "blur"},
        {"page": 1, "rects": pick["address"]["rects"], "action": "white"},
        {"page": 1, "rects": pick["plate"]["rects"], "action": "blur"},
        {"page": 1, "rects": pick["special"]["rects"], "action": "keep"},
        {"page": 1, "rects": [[70, 320, 150, 380]], "action": "black"},  # manual box over the image
    ]
    job = api.run("kvkk_apply", [f["id"]], {"items": items})
    assert job["status"] == "done", job
    assert job["data"]["applied"] == {"black": 2, "mask": 1, "blur": 2, "white": 1}
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as doc:
        page = doc[0]
        text = page.get_text()
        assert TCKN not in text
        assert "0532 123 45 67" not in text
        assert "Ayşe Yılmaz" not in text
        assert "Kadıköy" not in text
        assert "ABC" not in text and "34 " not in text  # the whole plate, not just the province code
        assert "Sağlık raporu" in text  # "keep"
        assert "Bu satır kişisel veri içermez." in text
        assert "*" in text  # mask overlay
        assert len(page.get_images()) >= 2  # blur patch added
        # Pixels under the manual box are gone, the rest of the image stays.
        img_pix = page.get_pixmap(clip=pymupdf.Rect(200, 420, 290, 490), dpi=36)
        r, _g, b = img_pix.pixel(img_pix.width // 2, img_pix.height // 2)
        assert b > 150 and r < 80  # untouched blue


def test_apply_needs_something(api: Api) -> None:
    f = api.upload(kvkk_pdf())
    job = api.run("kvkk_apply", [f["id"]], {"items": [{"page": 1, "rects": [[0, 0, 10, 10]], "action": "keep"}]})
    assert job["status"] == "failed"


@pytest.mark.parametrize("op", ["kvkk_apply", "redact"])
def test_extra_secure_pdf_keeps_only_pixels(api: Api, op: str) -> None:
    f = api.upload(kvkk_pdf())
    findings = api.run("kvkk_scan", [f["id"]])["data"]["findings"]
    tckn = next(x for x in findings if x["kind"] == "tckn")
    if op == "kvkk_apply":
        params = {"items": [{"page": 1, "rects": tckn["rects"], "action": "mask", "mask": "***"}], "flatten": True}
    else:
        params = {"terms": TCKN, "flatten": True, "flatten_dpi": 150}
    job = api.run(op, [f["id"]], params)
    assert job["status"] == "done", job
    assert job["result"]["name"].endswith("_guvenli.pdf")
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as doc:
        assert doc.page_count == 1
        page = doc[0]
        assert page.get_text().strip() == ""  # no text layer at all, not even the mask
        assert page.get_fonts() == []
        assert len(page.get_images()) == 1
        assert not any(v for k, v in doc.metadata.items() if k != "format")
        assert doc.embfile_count() == 0
        assert list(page.annots()) == [] and list(page.widgets()) == []
        # The picture still shows the rest of the page.
        assert page.rect.width == pytest.approx(595, abs=1)
