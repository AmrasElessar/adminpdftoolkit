from __future__ import annotations

import pymupdf

from .conftest import Api, make_pdf


def checks_by_rule(data: dict) -> dict[str, bool]:  # type: ignore[type-arg]
    return {c["rule"]: c["ok"] for c in data["checks"]}


def test_check_reports_missing_properties(api: Api) -> None:
    f = api.upload(make_pdf(2))
    job = api.run("accessibility_check", [f["id"]])
    assert job["status"] == "done", job
    data = job["data"]
    assert data["standard"].startswith("ISO 14289")
    rules = checks_by_rule(data)
    assert rules["7.1-tagged"] is False
    assert rules["7.2-lang"] is False
    assert rules["7.1-title"] is False
    assert rules["7.1-text"] is True
    assert data["conformant_candidate"] is False


def test_fix_sets_language_title_and_tab_order(api: Api) -> None:
    doc = pymupdf.open("pdf", make_pdf(1))
    doc[0].add_text_annot((100, 100), "not")
    f = api.upload(doc.tobytes(), "rapor.pdf")
    job = api.run("accessibility_fix", [f["id"]], {"language": "tr-TR"})
    assert job["status"] == "done", job
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as out:
        cat = out.pdf_catalog()
        assert out.xref_get_key(cat, "Lang") == ("string", "tr-TR")
        assert out.metadata["title"] == "rapor"
        assert "DisplayDocTitle true" in out.xref_get_key(cat, "ViewerPreferences")[1]
        assert out.xref_get_key(out[0].xref, "Tabs") == ("name", "/S")
    rules = {c["rule"]: c["ok"] for c in job["data"]["checks"]}
    assert rules["7.2-lang"] and rules["7.1-title"] and rules["7.1-display-title"] and rules["7.18.3-tabs"]


def test_isodate_token(api: Api) -> None:
    import datetime as dt

    f = api.upload(make_pdf(1))
    job = api.run("page_numbers", [f["id"]], {"template": "{n} · {isodate}"})
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as out:
        assert dt.date.today().isoformat() in out[0].get_text()
