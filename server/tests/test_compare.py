"""Document comparison."""

from __future__ import annotations

import pymupdf

from adminpdf.ops.compare import PageWords, align_pages

from .conftest import Api

BASE = [
    "Birinci bolum sozlesmenin taraflarini ve konusunu tanimlar ve imza tarihini belirtir",
    "Ikinci bolum odeme kosullarini aylik taksitler halinde ve banka havalesi ile duzenler",
    "Ucuncu bolum fesih hakkini otuz gun onceden yazili bildirim sartina baglar",
    "Dorduncu bolum uyusmazliklarda Istanbul mahkemelerinin yetkili oldugunu kabul eder",
]


def make_doc(pages: list[str], *, square: int | None = None) -> bytes:
    doc = pymupdf.open()
    for i, text in enumerate(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_textbox(pymupdf.Rect(72, 72, 523, 400), text, fontsize=12)
        if square is not None and i == square:
            page.draw_rect(pymupdf.Rect(100, 500, 300, 700), color=(0, 0, 0), fill=(0, 0, 0))
    data: bytes = doc.tobytes()
    doc.close()
    return data


def words(texts: list[str]) -> list[PageWords]:
    import hashlib

    return [PageWords(t.split(), [], hashlib.sha1(t.encode()).hexdigest()) for t in texts]


def test_align_detects_inserted_and_removed_pages() -> None:
    old = words(BASE)
    new = words([BASE[0], "Tamamen yeni bir sayfa eklendi burada hic benzerlik yok", BASE[1], BASE[3]])
    pairs = [(p.old, p.new) for p in align_pages(old, new)]
    assert (0, 0) in pairs and (1, 2) in pairs and (3, 3) in pairs
    assert (None, 1) in pairs and (2, None) in pairs


def test_align_pairs_modified_page() -> None:
    old = words(BASE)
    edited = BASE[2].replace("otuz", "altmis")
    new = words([BASE[0], BASE[1], edited, BASE[3]])
    pairs = [(p.old, p.new) for p in align_pages(old, new)]
    assert pairs == [(0, 0), (1, 1), (2, 2), (3, 3)]


def test_compare_end_to_end(api: Api) -> None:
    new_pages = [BASE[0], "Yepyeni ek protokol sayfasi hicbir ortak sozcuk icermiyor kesinlikle", BASE[1], BASE[3]]
    new_pages[2] = new_pages[2].replace("aylik", "haftalik")
    old = api.upload(make_doc(BASE), "eski.pdf")
    new = api.upload(make_doc(new_pages), "yeni.pdf")
    job = api.run("compare", [old["id"], new["id"]])
    assert job["status"] == "done", job
    s = job["data"]["summary"]
    assert s["pages_added"] == 1 and s["pages_removed"] == 1 and s["pages_changed"] == 1
    assert s["words_inserted"] == 1 and s["words_deleted"] == 1
    change = job["data"]["changes"][0]
    assert change == {"old_page": 2, "new_page": 3, "type": "replace", "old": "aylik", "new": "haftalik"}
    with pymupdf.open("pdf", api.download(job["result"]["id"])) as rep:
        # summary + added + changed pair + removed, in document order
        assert rep.page_count == 4
        assert "Karşılaştırma Raporu" in rep[0].get_text()
        assert [t[1] for t in rep.get_toc()][1:] == [
            "+ Yeni sayfa / New page 2",
            "2 ↔ 3",
            "− Silinen sayfa / Removed page 3",
        ]
        sheet = rep[2]
        assert sheet.rect.width > sheet.rect.height  # landscape, side by side
        # Highlights were baked into content: green and red pixels present.
        pix = sheet.get_pixmap(dpi=100)
        samples = pix.samples
        n = pix.n
        colors = {tuple(samples[i : i + 3]) for i in range(0, len(samples), n)}
        assert any(g > 150 and r < 150 and b < 150 for r, g, b in colors)
        assert any(r > 180 and g < 100 and b < 100 for r, g, b in colors)


def test_compare_identical_and_visual(api: Api) -> None:
    a = api.upload(make_doc(BASE[:2]))
    b = api.upload(make_doc(BASE[:2], square=1))
    job = api.run("compare", [a["id"], b["id"]])
    assert job["status"] == "done", job
    assert job["data"]["summary"]["pages_changed"] == 0
    job = api.run("compare", [a["id"], b["id"]], {"visual": True})
    s = job["data"]["summary"]
    assert s["pages_visual_only"] == 1 and s["pages_changed"] == 1
    assert [p["status"] for p in job["data"]["pages"]] == ["same", "visual"]


def test_compare_needs_two_inputs(api: Api) -> None:
    a = api.upload(make_doc(BASE[:1]))
    assert api.start("compare", [a["id"]]).status_code == 422
