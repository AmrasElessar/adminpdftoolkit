"""Digital signatures: certificate creation, PAdES signing, verification."""

from __future__ import annotations

from typing import Any

import pymupdf
import pytest

from .conftest import Api, make_pdf, make_png

PASSWORD = "gizli-123"


@pytest.fixture
def cert_id(api: Api) -> str:
    params = {
        "common_name": "Ayşe Yılmaz",
        "organisation": "Örnek Belediyesi",
        "email": "ayse@example.org",
        "validity_years": 2,
        "key_type": "ec",
        "password": PASSWORD,
    }
    job = api.run("create_certificate", [], params)
    assert job["status"] == "done", job
    assert job["result"]["name"] == "Ayşe Yılmaz.p12"
    assert job["result"]["kind"] == "cert"
    return str(job["result"]["id"])


def make_sig_field_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Contract", fontsize=20)
    w = pymupdf.Widget()
    w.field_type = pymupdf.PDF_WIDGET_TYPE_SIGNATURE
    w.field_name = "Onay"
    w.rect = pymupdf.Rect(300, 650, 520, 720)
    page.add_widget(w)
    data: bytes = doc.tobytes()
    doc.close()
    return data


def sign(api: Api, file_id: str, cert: str, **params: Any) -> dict[str, Any]:
    body = {"certificate": cert, "certificate_password": PASSWORD, **params}
    return api.run("sign", [file_id], body)


def verify(api: Api, data: bytes, **kw: Any) -> dict[str, Any]:
    f = api.upload(data, "signed.pdf")
    job = api.run("verify_signatures", [f["id"]], **kw)
    assert job["status"] == "done", job
    result: dict[str, Any] = job["data"]
    return result


def test_create_certificate_needs_no_input_and_validates(api: Api) -> None:
    job = api.run("create_certificate", [], {"common_name": "Ali Veli", "password": "123456"})
    assert job["status"] == "done", job
    assert job["result"]["name"] == "Ali Veli.p12"
    assert "CN=Ali Veli" in job["data"]["subject"] and "C=TR" in job["data"]["subject"]
    assert api.start("create_certificate", [], {"common_name": "X", "password": "123"}).status_code == 422
    assert (
        api.start("create_certificate", [], {"common_name": "X", "password": "123456", "country": "TUR"}).status_code
        == 422
    )
    f = api.upload(make_pdf(1))
    assert api.start("create_certificate", [f["id"]], {"common_name": "X", "password": "123456"}).status_code == 422


def test_rsa_certificate_loads_with_cryptography(api: Api) -> None:
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import ExtensionOID

    job = api.run("create_certificate", [], {"common_name": "RSA Test", "password": "123456"})
    key, cert, _ = pkcs12.load_key_and_certificates(api.download(job["result"]["id"]), b"123456")
    assert key is not None and cert is not None
    assert key.key_size == 3072  # type: ignore[union-attr]
    ku = cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value
    assert ku.digital_signature and ku.content_commitment  # type: ignore[attr-defined]


def test_sign_invisible_then_verify(api: Api, cert_id: str) -> None:
    f = api.upload(make_pdf(2))
    job = sign(api, f["id"], cert_id, visible=False, reason="Onay", location="Ankara")
    assert job["status"] == "done", job
    assert job["result"]["name"] == "test_imzali.pdf"
    signed = api.download(job["result"]["id"])
    report = verify(api, signed)
    assert report["count"] == 1
    sig = report["signatures"][0]
    assert sig["field"] == "Signature1"
    assert sig["signer"] == {
        "common_name": "Ayşe Yılmaz",
        "organisation": "Örnek Belediyesi",
        "email": "ayse@example.org",
    }
    assert sig["intact"] is True and sig["valid"] is True
    assert sig["trusted"] is False
    assert "self-signed" in sig["trust_problem"]["en"]
    assert sig["covers_whole_document"] is True and sig["modified_after_signing"] is False
    assert sig["signing_time"]
    with pymupdf.open("pdf", signed) as doc:
        widgets = list(doc[0].widgets()) + list(doc[1].widgets())
        assert [w.field_type_string for w in widgets] == ["Signature"]
        assert pymupdf.Rect(widgets[0].rect).is_empty


def test_sign_visible_with_image(api: Api, cert_id: str) -> None:
    f = api.upload(make_pdf(2))
    img = api.upload(make_png(120, 60), "imza.png")
    job = sign(
        api,
        f["id"],
        cert_id,
        visible=True,
        page="1",
        rect=[350, 50, 550, 120],
        reason="Sözleşme onayı",
        signature_image=img["id"],
    )
    assert job["status"] == "done", job
    signed = api.download(job["result"]["id"])
    sig = verify(api, signed)["signatures"][0]
    assert sig["intact"] and sig["valid"] and not sig["trusted"]
    with pymupdf.open("pdf", signed) as doc:
        page = doc[0]
        w = next(page.widgets())
        assert (pymupdf.Rect(w.rect) * ~page.transformation_matrix).normalize() == pymupdf.Rect(350, 50, 550, 120)
        page_doc = pymupdf.open()
        page_doc.insert_pdf(doc, from_page=0, to_page=0)
        page_doc.bake()
        text = page_doc[0].get_text()
        assert "Ayşe Yılmaz" in text and "Sözleşme onayı" in text
        assert "Yer:" not in text  # empty location line dropped
        assert page_doc[0].get_images()


def test_signature_broken_by_full_rewrite(api: Api, cert_id: str) -> None:
    f = api.upload(make_pdf(1))
    signed = api.download(sign(api, f["id"], cert_id)["result"]["id"])
    doc = pymupdf.open("pdf", signed)
    doc[0].set_rotation(90)
    tampered = doc.tobytes(garbage=3)  # full, non-incremental save
    sig = verify(api, tampered)["signatures"][0]
    assert sig["intact"] is False or sig["modified_after_signing"] is True
    assert not (sig["intact"] and sig["valid"] and sig["covers_whole_document"])


def test_second_signature_marks_first_as_followed_by_changes(api: Api, cert_id: str) -> None:
    f = api.upload(make_pdf(1))
    first = api.upload(api.download(sign(api, f["id"], cert_id, visible=False)["result"]["id"]))
    job = sign(api, first["id"], cert_id, field_name="Signature2", page="last")
    assert job["status"] == "done", job
    report = verify(api, api.download(job["result"]["id"]))
    assert report["count"] == 2 and report["all_valid"] is True
    one, two = report["signatures"]
    assert one["intact"] and one["modified_after_signing"] and one["modification_level"] == "FORM_FILLING"
    assert two["covers_whole_document"]


def test_wrong_certificate_password(api: Api, cert_id: str) -> None:
    f = api.upload(make_pdf(1))
    job = api.run("sign", [f["id"]], {"certificate": cert_id, "certificate_password": "yanlis"})
    assert job["status"] == "failed"
    assert job["error"] == {"tr": "Sertifika şifresi yanlış.", "en": "The certificate password is wrong."}


def test_sign_into_existing_empty_field(api: Api, cert_id: str) -> None:
    f = api.upload(make_sig_field_pdf())
    job = sign(api, f["id"], cert_id, field_name="Onay", rect=[1, 1, 50, 50])
    assert job["status"] == "done", job
    signed = api.download(job["result"]["id"])
    report = verify(api, signed)
    assert [s["field"] for s in report["signatures"]] == ["Onay"]
    assert report["signatures"][0]["intact"] and report["signatures"][0]["valid"]
    with pymupdf.open("pdf", signed) as doc:
        widgets = list(doc[0].widgets())
        assert len(widgets) == 1  # signed in place, no new field
        assert pymupdf.Rect(widgets[0].rect) == pymupdf.Rect(300, 650, 520, 720)

    again = api.upload(signed)
    job = sign(api, again["id"], cert_id, field_name="Onay")
    assert job["status"] == "failed" and "already signed" in job["error"]["en"]


def test_sign_rejects_non_signature_field_and_bad_rect(api: Api, cert_id: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    w = pymupdf.Widget()
    w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    w.field_name = "Signature1"
    w.rect = pymupdf.Rect(50, 50, 200, 80)
    page.add_widget(w)
    f = api.upload(doc.tobytes())
    job = sign(api, f["id"], cert_id)
    assert job["status"] == "failed" and "not a signature field" in job["error"]["en"]

    g = api.upload(make_pdf(1))
    job = sign(api, g["id"], cert_id, rect=[500, 800, 900, 900])
    assert job["status"] == "failed" and "outside the page" in job["error"]["en"]
    job = sign(api, g["id"], cert_id, page="7")
    assert job["status"] == "failed" and "out of range" in job["error"]["en"]


def test_sign_encrypted_input(api: Api, cert_id: str) -> None:
    doc = pymupdf.open("pdf", make_pdf(1))
    enc = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="acil", owner_pw="sahip-999")
    f = api.upload(enc)
    job = api.run("sign", [f["id"]], {"certificate": cert_id, "certificate_password": PASSWORD}, password="acil")
    assert job["status"] == "done", job
    signed = api.download(job["result"]["id"])
    with pymupdf.open("pdf", signed) as out:
        assert out.needs_pass  # incremental updates keep the encryption
    sig = verify(api, signed, password="acil")["signatures"][0]
    assert sig["intact"] and sig["valid"]


def test_certificate_param_must_be_a_cert(api: Api) -> None:
    f = api.upload(make_pdf(1))
    img = api.upload(make_png(), "a.png")
    assert api.start("sign", [f["id"]], {"certificate": img["id"]}).status_code == 415


def test_verify_unsigned_returns_empty_list(api: Api) -> None:
    report = verify(api, make_pdf(1))
    assert report == {"signatures": [], "count": 0, "all_valid": False}
