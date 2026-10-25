"""AcroForm operations: list, fill, flatten, create."""

from __future__ import annotations

from typing import Any

import pymupdf
import pytest

from .conftest import Api, make_pdf


def make_form_pdf() -> bytes:
    """One page with a text, multi-line text, checkbox, combo and list field."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 40), "Basvuru Formu", fontsize=14)

    def add(kind: int, name: str, rect: tuple[float, float, float, float], **attrs: Any) -> None:
        w = pymupdf.Widget()
        w.field_type = kind
        w.field_name = name
        w.rect = pymupdf.Rect(rect)
        for k, v in attrs.items():
            setattr(w, k, v)
        page.add_widget(w)

    add(pymupdf.PDF_WIDGET_TYPE_TEXT, "ad", (50, 60, 250, 90), field_flags=2, text_fontsize=11, text_maxlen=40)
    add(pymupdf.PDF_WIDGET_TYPE_TEXT, "adres", (50, 100, 300, 160), field_flags=1 << 12, text_fontsize=10)
    add(pymupdf.PDF_WIDGET_TYPE_CHECKBOX, "onay", (50, 170, 66, 186), field_value=False)
    add(
        pymupdf.PDF_WIDGET_TYPE_COMBOBOX,
        "il",
        (50, 200, 200, 220),
        choice_values=["Ankara", "İstanbul", "İzmir"],
        field_value="Ankara",
    )
    add(
        pymupdf.PDF_WIDGET_TYPE_LISTBOX,
        "diller",
        (50, 230, 200, 290),
        choice_values=["Türkçe", "English", "Deutsch"],
        field_flags=1 << 21,
        field_value="",
    )
    data: bytes = doc.tobytes()
    doc.close()
    return data


def fields_of(api: Api, file_id: str) -> dict[str, dict[str, Any]]:
    job = api.run("form_fields", [file_id])
    assert job["status"] == "done", job
    return {f["name"]: f for f in job["data"]["fields"]}


def test_list_fields(api: Api) -> None:
    f = api.upload(make_form_pdf())
    job = api.run("form_fields", [f["id"]])
    assert job["status"] == "done", job
    assert job["data"]["has_xfa"] is False
    fields = {x["name"]: x for x in job["data"]["fields"]}
    assert list(fields) == ["ad", "adres", "onay", "il", "diller"]
    ad = fields["ad"]
    assert ad["type"] == "text"
    assert ad["page"] == 1
    assert ad["rect"] == [50, 752, 250, 782]  # PDF user space: origin bottom-left
    assert ad["required"] is True and ad["readonly"] is False
    assert ad["max_length"] == 40
    assert fields["adres"]["multiline"] is True
    assert fields["onay"] == fields["onay"] | {"type": "checkbox", "value": False, "options": ["Yes"]}
    assert fields["il"]["options"] == ["Ankara", "İstanbul", "İzmir"]
    assert fields["il"]["value"] == "Ankara"
    assert fields["diller"]["type"] == "list" and fields["diller"]["multiselect"] is True


def test_list_fields_reports_rect_on_rotated_page(api: Api) -> None:
    doc = pymupdf.open("pdf", make_form_pdf())
    doc[0].set_rotation(90)
    f = api.upload(doc.tobytes())
    assert fields_of(api, f["id"])["ad"]["rect"] == [50, 752, 250, 782]


def test_no_fields_gives_empty_list(api: Api) -> None:
    f = api.upload(make_pdf(1))
    job = api.run("form_fields", [f["id"]])
    assert job["status"] == "done"
    assert job["data"] == {"fields": [], "has_xfa": False}


def test_fill_and_read_back(api: Api) -> None:
    f = api.upload(make_form_pdf())
    values = {
        "ad": "Şükrü Öztürk",
        "adres": "Atatürk Cad. No: 1\nÇankaya / Ankara",
        "onay": True,
        "il": "İzmir",
        "diller": ["Türkçe", "Deutsch"],
    }
    job = api.run("form_fill", [f["id"]], {"values": values})
    assert job["status"] == "done", job
    out = api.upload(api.download(job["result"]["id"]), "filled.pdf")
    fields = fields_of(api, out["id"])
    assert {k: fields[k]["value"] for k in values} == values

    # Turkish text must actually be drawn inside the widget box.
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as doc:
        doc.bake()
        text = doc[0].get_text()
        assert "Şükrü Öztürk" in text
        assert "Çankaya / Ankara" in text
        words = [w for w in doc[0].get_text("words") if w[4] == "Şükrü"]
        assert words and pymupdf.Rect(50, 60, 250, 90).contains(pymupdf.Rect(words[0][:4]))


def test_fill_checkbox_with_on_state_and_false(api: Api) -> None:
    f = api.upload(make_form_pdf())
    on = api.run("form_fill", [f["id"]], {"values": {"onay": "Yes"}})
    on_file = api.upload(api.download(on["result"]["id"]))
    assert fields_of(api, on_file["id"])["onay"]["value"] is True
    off = api.run("form_fill", [on_file["id"]], {"values": {"onay": False}})
    off_file = api.upload(api.download(off["result"]["id"]))
    assert fields_of(api, off_file["id"])["onay"]["value"] is False


def test_fill_unknown_names_listed(api: Api) -> None:
    f = api.upload(make_form_pdf())
    job = api.run("form_fill", [f["id"]], {"values": {"ad": "x", "yok1": "a", "yok2": "b"}})
    assert job["status"] == "failed"
    assert "yok1" in job["error"]["en"] and "yok2" in job["error"]["en"]
    assert job["error"]["tr"].startswith("Bilinmeyen alan adları")


@pytest.mark.parametrize(
    ("values", "needle"),
    [
        ({"il": "Bursa"}, "Invalid option"),
        ({"ad": "x" * 41}, "at most 40"),
        ({"onay": "belki"}, "enter one of"),
        ({"ad": True}, "expects text"),
    ],
)
def test_fill_rejects_bad_values(api: Api, values: dict[str, Any], needle: str) -> None:
    f = api.upload(make_form_pdf())
    job = api.run("form_fill", [f["id"]], {"values": values})
    assert job["status"] == "failed"
    assert needle in job["error"]["en"]


def test_fill_params_bounded(api: Api) -> None:
    f = api.upload(make_form_pdf())
    assert api.start("form_fill", [f["id"]], {"values": {}}).status_code == 422
    assert api.start("form_fill", [f["id"]], {"values": {"ad": "x" * 10_001}}).status_code == 422
    many = {f"f{i}": "x" for i in range(5001)}
    assert api.start("form_fill", [f["id"]], {"values": many}).status_code == 422


def test_fill_with_flatten(api: Api) -> None:
    f = api.upload(make_form_pdf())
    job = api.run("form_fill", [f["id"]], {"values": {"ad": "Ayşe Yılmaz"}, "flatten": True})
    assert job["status"] == "done", job
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as doc:
        assert not list(doc[0].widgets())
        assert "Ayşe Yılmaz" in doc[0].get_text()


def test_flatten_removes_widgets_keeps_text(api: Api) -> None:
    f = api.upload(make_form_pdf())
    filled = api.run("form_fill", [f["id"]], {"values": {"ad": "Mehmet Kaya", "adres": "İğdır"}})
    src = api.upload(api.download(filled["result"]["id"]))
    job = api.run("form_flatten", [src["id"]])
    assert job["status"] == "done", job
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as doc:
        assert not list(doc[0].widgets())
        text = doc[0].get_text()
        assert "Mehmet Kaya" in text and "İğdır" in text and "Basvuru Formu" in text


def test_flatten_without_fields_is_user_error(api: Api) -> None:
    f = api.upload(make_pdf(1))
    job = api.run("form_flatten", [f["id"]])
    assert job["status"] == "failed"
    assert "no form fields" in job["error"]["en"]


CREATE_SPECS: list[dict[str, Any]] = [
    {"page": 1, "type": "text", "name": "ad_soyad", "rect": [50, 700, 300, 725], "required": True, "default": "Çağrı"},
    {"page": 1, "type": "text", "name": "not", "rect": [50, 600, 300, 680], "multiline": True, "font_size": 9},
    {"page": 1, "type": "checkbox", "name": "kvkk", "rect": [50, 570, 66, 586], "default": True},
    {"page": 1, "type": "radio", "name": "cinsiyet", "rect": [50, 530, 200, 550], "options": ["Kadın", "Erkek"]},
    {"page": 1, "type": "combo", "name": "sehir", "rect": [50, 500, 200, 520], "options": ["Ankara", "Iğdır"]},
    {"page": 2, "type": "list", "name": "ilgi", "rect": [50, 400, 200, 480], "options": ["A", "B", "C"]},
    {"page": 2, "type": "signature", "name": "imza", "rect": [350, 50, 550, 120], "tooltip": "Burayı imzalayın"},
]


def test_create_then_list(api: Api) -> None:
    f = api.upload(make_pdf(2))
    specs = [dict(s) for s in CREATE_SPECS]
    specs[3]["default"] = "Erkek"
    specs[4]["default"] = "Iğdır"
    specs[5]["default"] = ["A", "C"]
    job = api.run("form_create", [f["id"]], {"fields": specs})
    assert job["status"] == "done", job
    out = api.upload(api.download(job["result"]["id"]))
    fields = fields_of(api, out["id"])
    assert list(fields) == [s["name"] for s in specs]
    assert {n: f["type"] for n, f in fields.items()} == {s["name"]: s["type"] for s in specs}
    assert fields["ad_soyad"]["rect"] == [50, 700, 300, 725]
    assert fields["ad_soyad"]["required"] is True
    assert fields["ad_soyad"]["value"] == "Çağrı"
    assert fields["not"]["multiline"] is True
    assert fields["kvkk"]["value"] is True
    radio = fields["cinsiyet"]
    assert radio["options"] == ["Kadın", "Erkek"]
    assert radio["value"] == "Erkek"
    assert len(radio["widgets"]) == 2
    assert fields["sehir"]["value"] == "Iğdır"
    assert fields["ilgi"]["value"] == ["A", "C"]
    assert fields["imza"]["page"] == 2 and fields["imza"]["signed"] is False
    assert fields["imza"]["tooltip"] == "Burayı imzalayın"

    # The radio group behaves as one field: selecting the other option
    # switches the first one off.
    job = api.run("form_fill", [out["id"]], {"values": {"cinsiyet": "Kadın"}})
    assert job["status"] == "done", job
    refilled = api.upload(api.download(job["result"]["id"]))
    assert fields_of(api, refilled["id"])["cinsiyet"]["value"] == "Kadın"


@pytest.mark.parametrize(
    ("change", "needle"),
    [
        ({"rect": [500, 700, 700, 725]}, "outside the page"),
        ({"page": 9}, "does not exist"),
        ({"name": "not"}, "already in use"),
        ({"type": "combo"}, "Enter options"),
    ],
)
def test_create_validates(api: Api, change: dict[str, Any], needle: str) -> None:
    f = api.upload(make_pdf(2))
    specs = [CREATE_SPECS[1], {**CREATE_SPECS[0], **change}]
    job = api.run("form_create", [f["id"]], {"fields": specs})
    assert job["status"] == "failed"
    assert needle in job["error"]["en"]


def test_create_rejects_existing_name_and_bad_spec(api: Api) -> None:
    f = api.upload(make_form_pdf())
    job = api.run("form_create", [f["id"]], {"fields": [{**CREATE_SPECS[0], "name": "ad"}]})
    assert job["status"] == "failed" and "already in use" in job["error"]["en"]
    bad = {**CREATE_SPECS[0], "rect": [1, 2, 3]}
    assert api.start("form_create", [f["id"]], {"fields": [bad]}).status_code == 422
    dotted = {**CREATE_SPECS[0], "name": "a.b"}
    assert api.start("form_create", [f["id"]], {"fields": [dotted]}).status_code == 422


def test_create_is_hidden_and_fill_uses_json_widget(api: Api) -> None:
    ops = {o["name"]: o for o in api.c.get("/api/ops").json()}
    assert ops["form_create"]["hidden"] is True
    assert ops["form_fill"]["schema"]["properties"]["values"]["ui"] == {"widget": "json"}
