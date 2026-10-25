"""Personal-data detection and permanent redaction."""

from __future__ import annotations

import io
import random

import pymupdf
import pytest

from adminpdf.core.errors import UserError
from adminpdf.ops.redact import compile_user_regex, iban_valid, luhn_valid, mask_text, phone_valid, tckn_valid

from .conftest import Api


def make_tckn(first9: str) -> str:
    d = [int(c) for c in first9]
    tenth = ((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10
    eleventh = (sum(d) + tenth) % 10
    return f"{first9}{tenth}{eleventh}"


TCKN = make_tckn("123456789")
IBAN = "TR33 0006 1005 1978 6457 8413 26"
CARD = "4111 1111 1111 1111"


# -- validators ------------------------------------------------------------------
def test_tckn_valid_generated() -> None:
    rng = random.Random(7)
    for _ in range(50):
        first9 = str(rng.randint(1, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(8))
        assert tckn_valid(make_tckn(first9))


@pytest.mark.parametrize(
    "value",
    [
        TCKN[:-1] + str((int(TCKN[-1]) + 1) % 10),  # wrong 11th digit
        TCKN[:-2] + str((int(TCKN[-2]) + 1) % 10) + TCKN[-1],  # wrong 10th digit
        "0" + make_tckn("123456789")[1:],  # leading zero
        TCKN[:-1],  # too short
        "1234567890a",
        "١٢٣٤٥٦٧٨٩٠١",  # non-ASCII digits
    ],
)
def test_tckn_invalid(value: str) -> None:
    assert not tckn_valid(value)


def test_iban() -> None:
    assert iban_valid(IBAN)
    assert iban_valid(IBAN.replace(" ", ""))
    assert iban_valid("GB82 WEST 1234 5698 7654 32")
    assert not iban_valid(IBAN.replace("26", "27"))
    assert not iban_valid("TR33 0006 1005 1978 6457 8413")  # too short for TR
    assert not iban_valid("TR")


def test_luhn() -> None:
    assert luhn_valid(CARD)
    assert luhn_valid("5555-5555-5555-4444")
    assert luhn_valid("378282246310005")  # 15-digit Amex
    assert not luhn_valid("4111 1111 1111 1112")
    assert not luhn_valid("411111111111")  # 12 digits
    assert not luhn_valid("4" * 20)


def test_phone() -> None:
    assert phone_valid("+90 532 123 45 67")
    assert phone_valid("(0212) 555 12 34")
    assert phone_valid("05321234567")
    assert not phone_valid("0132 123 45 67")


def test_mask_text() -> None:
    assert mask_text("12345678901") == "123*******1"
    assert mask_text("ab") == "**"
    masked = mask_text("ali.veli@ornek.com")
    assert masked.startswith("ali.") and "veli" not in masked


@pytest.mark.parametrize("pattern", [r"(a+)+$", r"(\d*)*x", r"((ab)*c)+", r"(x|y+)*"])
def test_nested_quantifiers_rejected(pattern: str) -> None:
    with pytest.raises(UserError):
        compile_user_regex(pattern, False)


@pytest.mark.parametrize("pattern", [r"\d{3}-\d{4}", r"(?:\d{3}-)*\d", r"[A-Z]+\d+", r"Dosya No: \w+"])
def test_safe_regex_accepted(pattern: str) -> None:
    compile_user_regex(pattern, False)


def test_invalid_regex_rejected() -> None:
    with pytest.raises(UserError):
        compile_user_regex("(unclosed", True)


# -- fixtures --------------------------------------------------------------------
def make_personal_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    lines = [
        f"TC Kimlik: {TCKN}",
        f"IBAN: {IBAN}",
        f"Kart: {CARD}",
        "Tel: +90 532 123 45 67",
        "E-posta: ali.veli@ornek.com.tr",
        "Gecersiz: 12345678901",
        "Bu satir korunur.",
        "Musteri adi Ali",
        "Veli burada bitiyor.",
    ]
    for i, text in enumerate(lines):
        page.insert_text((72, 100 + 30 * i), text, fontsize=12)
    doc.set_metadata({"title": "Gizli", "author": "Personel"})
    data: bytes = doc.tobytes()
    doc.close()
    return data


def make_image_page_pdf() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (200, 200), (200, 30, 30)).save(buf, "PNG")
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=400)
    page.insert_image(pymupdf.Rect(100, 100, 300, 300), stream=buf.getvalue())
    page.insert_text((20, 30), "Gizli metin", fontsize=12)
    page.insert_text((20, 380), "Acik metin", fontsize=12)
    data: bytes = doc.tobytes()
    doc.close()
    return data


def text_of(data: bytes) -> str:
    with pymupdf.open("pdf", data) as doc:
        return "\n".join(p.get_text() for p in doc)


# -- find_sensitive ----------------------------------------------------------------
def test_find_sensitive_presets(api: Api) -> None:
    f = api.upload(make_personal_pdf())
    job = api.run("find_sensitive", [f["id"]], {"presets": ["tckn", "iban", "card", "phone", "email"]})
    assert job["status"] == "done", job
    data = job["data"]
    assert data["counts"] == {"tckn": 1, "iban": 1, "card": 1, "phone": 1, "email": 1}
    by_kind = {m["kind"]: m for m in data["matches"]}
    assert TCKN not in str(data)  # masked
    assert by_kind["tckn"]["text"] == mask_text(TCKN)
    # Rects are PDF user space: origin bottom-left, so y ≈ 842 - 100.
    x0, y0, _x1, y1 = by_kind["tckn"]["rects"][0]
    assert x0 > 72 and y0 < 742 < y1 and y1 < 842 - 85
    assert all(m["page"] == 1 for m in data["matches"])


def test_find_terms_across_lines_and_case(api: Api) -> None:
    f = api.upload(make_personal_pdf())
    job = api.run("find_sensitive", [f["id"]], {"terms": "ali veli burada\nKORUNUR"})
    assert job["status"] == "done", job
    matches = job["data"]["matches"]
    assert len(matches) == 2
    multi = next(m for m in matches if len(m["rects"]) > 1)
    assert len(multi["rects"]) == 2  # one box per line
    job = api.run("find_sensitive", [f["id"]], {"terms": "KORUNUR", "case_sensitive": True})
    assert job["data"]["total"] == 0


def test_find_regex_and_guard(api: Api) -> None:
    f = api.upload(make_personal_pdf())
    job = api.run("find_sensitive", [f["id"]], {"regex": r"Gecersiz: \d+"})
    assert job["data"]["total"] == 1
    bad = api.run("find_sensitive", [f["id"]], {"regex": r"(\w+)+x"})
    assert bad["status"] == "failed"
    assert "tekrarlayıcı" in bad["error"]["tr"]


def test_too_many_terms_rejected(api: Api) -> None:
    f = api.upload(make_personal_pdf())
    job = api.run("find_sensitive", [f["id"]], {"terms": "\n".join(f"t{i}" for i in range(501))})
    assert job["status"] == "failed"


# -- redact --------------------------------------------------------------------------
def test_redact_removes_text_and_metadata(api: Api) -> None:
    f = api.upload(make_personal_pdf())
    job = api.run("redact", [f["id"]], {"presets": ["tckn", "iban", "card"], "overlay_text": "KARARTILDI"})
    assert job["status"] == "done", job
    assert job["data"] == {"redactions": 3, "pages": [1]}
    text = text_of(api.download(job["result"]["id"]))
    for secret in (TCKN, IBAN, IBAN.replace(" ", ""), CARD, "0006", "1111"):
        assert secret not in text
    assert "Bu satir korunur." in text
    assert "Tel: +90 532 123 45 67" in text  # not selected
    assert "TC Kimlik:" in text and "KARARTILDI" in text
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as doc:
        assert not doc.metadata["title"] and not doc.metadata["author"]


def test_redact_area_image_pixels(api: Api) -> None:
    f = api.upload(make_image_page_pdf())
    # PyMuPDF box (150,150)-(250,250) on a 400 pt page, in user space:
    area = {"page": 1, "rect": [150, 150, 250, 250]}
    top_secret = {"page": 1, "rect": [15, 400 - 35, 120, 400 - 15]}
    job = api.run("redact", [f["id"]], {"areas": [area, top_secret], "fill_color": "#FFFFFF"})
    assert job["status"] == "done", job
    out = api.download(job["result"]["id"])
    text = text_of(out)
    assert "Gizli" not in text and "Acik metin" in text
    with pymupdf.open("pdf", out) as doc:
        page = doc[0]
        assert page.get_images(), "the image itself must remain"
        pix = page.get_pixmap(dpi=72, annots=False)

        def rgb(x: int, y: int) -> tuple[int, ...]:
            return tuple(pix.pixel(x, y))[:3]

        assert rgb(200, 200) == (255, 255, 255)  # pixels under the box are gone
        r, g, b = rgb(120, 120)  # the rest of the image survives
        assert r > 150 and g < 80 and b < 80
        # The pixels are really gone from the image data, not just covered.
        xref = page.get_images()[0][0]
        img = pymupdf.Pixmap(doc, xref)
        cx, cy = img.width // 2, img.height // 2
        assert tuple(img.pixel(cx, cy))[:3] != (200, 30, 30)


def test_redact_strips_overlapping_annotations_and_links(api: Api) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), f"No: {TCKN}", fontsize=12)
    page.insert_text((72, 400), "Baska bir yer", fontsize=12)
    hit = page.search_for(TCKN)[0]
    page.add_text_annot(hit.tl, f"Not: {TCKN}")
    page.add_text_annot(pymupdf.Point(72, 400), "Kalsin")
    page.insert_link({"kind": pymupdf.LINK_URI, "from": hit, "uri": f"https://example.invalid/{TCKN}"})
    f = api.upload(doc.tobytes())
    doc.close()
    job = api.run("redact", [f["id"]], {"presets": ["tckn"]})
    assert job["status"] == "done", job
    out = api.download(job["result"]["id"])
    assert TCKN.encode() not in out
    with pymupdf.open("pdf", out) as res:
        p = res[0]
        assert [a.info["content"] for a in p.annots()] == ["Kalsin"]
        assert not p.get_links()


def test_redact_rotated_page_area(api: Api) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((50, 100), "Silinecek", fontsize=14)
    page.insert_text((50, 500), "Kalacak", fontsize=14)
    r = page.search_for("Silinecek")[0]
    page.set_rotation(90)
    user = (r * ~page.transformation_matrix).normalize()
    f = api.upload(doc.tobytes())
    doc.close()
    job = api.run("redact", [f["id"]], {"areas": [{"page": 1, "rect": [user.x0, user.y0, user.x1, user.y1]}]})
    assert job["status"] == "done", job
    text = text_of(api.download(job["result"]["id"]))
    assert "Silinecek" not in text and "Kalacak" in text


def test_redact_nothing_found(api: Api) -> None:
    f = api.upload(make_personal_pdf())
    job = api.run("redact", [f["id"]], {"terms": "yok-boyle-bir-sey"})
    assert job["status"] == "failed"
    assert job["error"]["en"] == "Nothing to redact was found."


def test_redact_area_bounds(api: Api) -> None:
    f = api.upload(make_personal_pdf())
    job = api.run("redact", [f["id"]], {"areas": [{"page": 5, "rect": [0, 0, 10, 10]}]})
    assert job["status"] == "failed"
    too_many = [{"page": 1, "rect": [0, 0, 1, 1]}] * 5001
    assert api.start("redact", [f["id"]], {"areas": too_many}).status_code == 422
