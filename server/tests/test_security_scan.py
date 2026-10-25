from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import pikepdf
import pymupdf
import pytest
from pikepdf import Array, Dictionary, Name, String

from adminpdf.ops import security_scan
from adminpdf.ops.security_scan import Walker, antivirus_scan

from .conftest import Api, make_pdf


def malicious_pdf() -> bytes:
    """Doc-level JavaScript, a JavaScript OpenAction, an embedded .exe, a page
    open-action that launches a program, a web link and a reference cycle."""
    pdf = pikepdf.open(io.BytesIO(make_pdf(1)))
    script = pdf.make_indirect(Dictionary(Type=Name.Action, S=Name.JavaScript, JS=String("app.alert('merhaba')")))
    pdf.Root.Names = Dictionary(JavaScript=Dictionary(Names=Array([String("init"), script])))
    pdf.Root.OpenAction = Dictionary(S=Name.JavaScript, JS=String("this.print({bUI:false});"))
    pdf.attachments["fatura.exe"] = pikepdf.AttachedFileSpec(pdf, b"MZ\x90\x00 not really", filename="fatura.exe")
    page = pdf.pages[0].obj
    page.AA = Dictionary(O=Dictionary(S=Name.Launch, F=String("cmd.exe")))
    link = Dictionary(
        Type=Name.Annot,
        Subtype=Name.Link,
        Rect=Array([72, 72, 200, 100]),
        A=Dictionary(S=Name.URI, URI=String("https://evil.example.com/payload")),
    )
    page.Annots = Array([pdf.make_indirect(link)])
    loop = pdf.make_indirect(Dictionary())
    loop.Self = loop
    loop.Kids = Array([loop, loop])
    pdf.Root.Loop = loop
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def scan(api: Api, file_id: str, **kw: Any) -> dict[str, Any]:
    job = api.run("security_scan", [file_id], {"antivirus": False}, **kw)
    assert job["status"] == "done", job
    data: dict[str, Any] = job["data"]
    return data


def test_scan_flags_malicious_pdf(api: Api) -> None:
    f = api.upload(malicious_pdf(), "evil.pdf")
    r = scan(api, f["id"])
    assert r["risk"] == "high"
    codes = {x["code"] for x in r["reasons"]}
    assert {"javascript", "launch", "embedded_executable", "additional_actions", "uri"} <= codes
    assert r["reasons"][0]["level"] == "high"
    assert all(x["tr"] and x["en"] for x in r["reasons"])
    assert r["javascript"]["count"] == 2
    assert r["javascript"]["locations"] == {"document": 1, "open_action": 1}
    assert "app.alert('merhaba')" in r["javascript"]["previews"]
    assert r["open_action"] == "JavaScript"
    assert r["actions"]["Launch"] == 1
    assert r["launch_targets"] == ["cmd.exe"]
    assert r["uri_hosts"] == {"evil.example.com": 1}
    assert r["additional_actions"] == {"page": 1}
    assert [e["name"] for e in r["embedded_files"]] == ["fatura.exe"]
    assert r["embedded_files"][0]["size"] == len(b"MZ\x90\x00 not really")
    assert r["structure"]["scan_truncated"] is False


def test_sanitize_removes_active_content(api: Api) -> None:
    f = api.upload(malicious_pdf(), "evil.pdf")
    job = api.run("sanitize", [f["id"]])
    assert job["status"] == "done", job
    assert job["result"]["name"] == "evil_temiz.pdf"
    removed = job["data"]["removed"]
    assert removed["javascript"] == 1  # doc-level script; the JS OpenAction is counted below
    assert removed["open_action"] == 1
    assert removed["additional_actions"] == 1
    assert removed["embedded_files"] >= 1
    # The web link stays unless asked: low risk, nothing executable left.
    assert job["data"]["risk_after"] == "low"
    after = scan(api, job["result"]["id"])
    assert after["risk"] in ("none", "low")
    assert after["javascript"]["count"] == 0 and after["embedded_files"] == []
    assert "Launch" not in after["actions"]
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as doc:
        assert doc.page_count == 1 and "Sayfa 1" in doc[0].get_text()
        assert doc.embfile_count() == 0


def test_sanitize_links_and_metadata(api: Api) -> None:
    with pymupdf.open("pdf", malicious_pdf()) as doc:
        doc.set_metadata({"author": "Gizli Kişi", "title": "Rapor"})
        data = doc.tobytes()
    f = api.upload(data)
    job = api.run("sanitize", [f["id"]], {"remove_links": True, "remove_metadata": True})
    assert job["status"] == "done", job
    assert job["data"]["removed"]["links"] == 1
    assert job["data"]["risk_after"] == "none"
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as doc:
        assert not doc.metadata.get("author")
        assert list(doc[0].links()) == []


def test_clean_pdf_has_no_risk(api: Api) -> None:
    f = api.upload(make_pdf(2))
    r = scan(api, f["id"])
    assert r["risk"] == "none" and r["reasons"] == []
    assert r["pages"] == 2
    assert r["encryption"] is None and r["signatures"] == 0
    assert r["structure"]["incremental_updates"] == 0


def test_scan_counts_incremental_updates_and_encryption(api: Api, tmp_path: Path) -> None:
    path = tmp_path / "a.pdf"
    path.write_bytes(make_pdf(1))
    for k in range(2):
        with pymupdf.open(path) as doc:
            doc.set_metadata({"title": f"v{k}"})
            doc.saveIncr()
    f = api.upload(path.read_bytes())
    assert scan(api, f["id"])["structure"]["incremental_updates"] == 2

    with pymupdf.open("pdf", make_pdf(1)) as doc:
        enc = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="gizli", owner_pw="sahip")
    e = api.upload(enc)
    assert api.run("security_scan", [e["id"]])["status"] == "failed"
    r = scan(api, e["id"], password="gizli")
    assert r["encryption"]["method"] == "aesv3" and r["encryption"]["bits"] == 256


def test_scan_antivirus_section_never_fails(api: Api) -> None:
    f = api.upload(make_pdf(1))
    job = api.run("security_scan", [f["id"]], {"antivirus": True})
    assert job["status"] == "done", job
    av = job["data"]["antivirus"]
    assert av["engine"] == "ClamAV" and isinstance(av["available"], bool)
    if not av["available"]:
        assert av["reason"]["tr"] and av["reason"]["en"]


def test_antivirus_missing_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(security_scan.shutil, "which", lambda _name: None)
    r = antivirus_scan(tmp_path)
    assert r["available"] is False and "not installed" in r["reason"]["en"]


def test_walker_visits_shared_objects_once_and_honours_budget() -> None:
    pdf = pikepdf.new()
    pdf.add_blank_page()
    node = pdf.make_indirect(Dictionary())
    for _ in range(200):
        # Each level references the one below twice: 2**200 paths, 200 objects.
        node = pdf.make_indirect(Dictionary(Kids=Array([node, node])))
    pdf.Root.Chain = node
    walker = Walker(pdf)
    assert sum(1 for _ in walker.dicts()) < 300 and walker.truncated is False

    pdf.Root.Wide = Array([pdf.make_indirect(Dictionary(N=i)) for i in range(10_000)])
    walker = Walker(pdf, budget=5000)
    count = sum(1 for _ in walker.dicts())
    assert walker.truncated is True and count < 5000


# -- repair ----------------------------------------------------------------------------
def damaged_xref_pdf() -> bytes:
    data = make_pdf(3)
    return re.sub(rb"startxref\s+\d+", b"startxref\n99999999", data)


def truncated_pdf() -> bytes:
    with pymupdf.open("pdf", make_pdf(3)) as doc:
        data: bytes = doc.tobytes(garbage=0, use_objstms=0)
    return data[: data.rfind(b"xref")]


@pytest.mark.parametrize("make", [damaged_xref_pdf, truncated_pdf])
def test_repair_recovers_pages(api: Api, make: Any) -> None:
    f = api.upload(make(), "bozuk.pdf")
    job = api.run("repair", [f["id"]])
    assert job["status"] == "done", job
    assert job["result"]["name"] == "bozuk_onarilmis.pdf"
    assert job["data"]["pages"] == 3 and job["data"]["repaired"] is True
    data = api.download(job["result"]["id"])
    with pikepdf.open(io.BytesIO(data)) as pdf:
        assert pdf.get_warnings() == []
    with pymupdf.open("pdf", data) as doc:
        assert not doc.is_repaired
        assert [p.get_text().strip() for p in doc] == ["Sayfa 1", "Sayfa 2", "Sayfa 3"]


def test_repair_linearize(api: Api) -> None:
    f = api.upload(damaged_xref_pdf())
    job = api.run("repair", [f["id"]], {"linearize": True})
    assert job["status"] == "done", job
    with pikepdf.open(io.BytesIO(api.download(job["result"]["id"]))) as pdf:
        assert pdf.is_linearized


def test_scan_reports_damage(api: Api) -> None:
    f = api.upload(damaged_xref_pdf())
    r = scan(api, f["id"])
    assert r["structure"]["repaired"] is True
    assert r["risk"] == "medium" and r["reasons"][0]["code"] == "repaired"
    assert not any("/" in w for w in r["structure"]["warnings"]), "server paths must not leak"


def test_repair_rejects_non_pdf(api: Api) -> None:
    f = api.upload(b"just some bytes", "notes.bin")
    assert f["kind"] == "other"
    job = api.run("repair", [f["id"]])
    assert job["status"] == "failed" and "not a PDF" in job["error"]["en"]
