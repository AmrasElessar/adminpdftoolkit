"""Parser registry & dispatch tests (S2 plugin layer).

Lightweight unit tests — exercise registry order, lookup, and the
``GenericTableParser`` fallback semantics without needing real PDF fixtures.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import parsers
from parsers import classify, get_parser
from parsers.call_log_360 import CallLog360Parser
from parsers.generic_table import GenericTableParser
from parsers.scanned import ScannedParser


class _FakePage:
    def __init__(self, text: str, has_image: bool) -> None:
        self._text = text
        self._has_image = has_image

    def get_text(self) -> str:
        return self._text

    def get_images(self) -> list:
        return [object()] if self._has_image else []


class _FakeDoc:
    def __init__(self, page_texts: tuple[str, ...], image_pages: int) -> None:
        self._pages = [
            _FakePage(text, has_image=(i < image_pages)) for i, text in enumerate(page_texts)
        ]

    def __len__(self) -> int:
        return len(self._pages)

    def __iter__(self):
        return iter(self._pages)

    def __getitem__(self, index: int) -> _FakePage:
        return self._pages[index]


def _fake_doc(*page_texts: str, image_pages: int = 0) -> _FakeDoc:
    return _FakeDoc(page_texts, image_pages)


def test_registry_order_is_specific_first() -> None:
    """CallLog360 + Scanned must come before the GenericTable fallback."""
    names = [p.name for p in parsers.PARSERS]
    assert names.index("call_log_360") < names.index("generic_table")
    assert names.index("scanned") < names.index("generic_table")


def test_get_parser_returns_singleton_by_name() -> None:
    p = get_parser("call_log_360")
    assert isinstance(p, CallLog360Parser)
    assert get_parser("scanned").name == "scanned"
    assert get_parser("generic_table").name == "generic_table"


def test_get_parser_unknown_returns_none() -> None:
    assert get_parser("does_not_exist") is None


def test_classify_picks_call_log_when_markers_present() -> None:
    head = "S: Ağrı / romatizma\nS: Termal\nMÜŞTERİ Ahmet\nSeçilen kayıt sayısı"
    doc = _fake_doc(head)
    p = classify(doc)
    assert p is not None and p.name == "call_log_360"


def test_classify_falls_back_to_generic_table_for_plain_text() -> None:
    """A neutral text-only PDF doesn't match call-log or scanned, so the
    fallback (always-true GenericTableParser) wins."""
    doc = _fake_doc("Sıradan bir PDF metni içeriği.")
    p = classify(doc)
    assert p is not None and p.name == "generic_table"


def test_scanned_parser_classifies_image_heavy_low_text() -> None:
    """Avg < 40 chars/page + at least one page with an image → scanned."""
    # 3 sayfa, ortalama < 40 char, image olan sayfa var
    doc = _fake_doc("hi", "OK", "x", image_pages=2)
    sp = ScannedParser()
    assert sp.is_match(doc) is True


def test_scanned_parser_does_not_classify_text_heavy() -> None:
    rich_text = "x" * 200
    doc = _fake_doc(rich_text, rich_text, image_pages=0)
    assert ScannedParser().is_match(doc) is False


def test_generic_table_parser_always_matches() -> None:
    """is_match always True so it acts as the registry's last-resort fallback."""
    assert GenericTableParser().is_match(_fake_doc("any")) is True


def test_call_log_parser_rejects_non_call_log() -> None:
    """Two markers required; a generic invoice should not match."""
    doc = _fake_doc("Fatura No: 123\nTutar: 5000 TL")
    assert CallLog360Parser().is_match(doc) is False


def test_call_log_parser_records_have_expected_keys() -> None:
    """parse_records returns dicts with all expected schema fields."""
    text = (
        "Seçilen kayıt sayısı: 1\n"
        "1\n"
        "Ahmet Yılmaz\n"
        "+90 555 111 22 33\n"
        "ended\n"
        "01.01.2026 10:30\n"
        "5:23\n"
        "S: Ağrı / romatizma\n"
        "C: Var\n"
        "S: Yaş\n"
        "C: 33\n"
    )
    doc = _fake_doc(text)
    records = CallLog360Parser().parse_records(doc)
    assert len(records) == 1
    rec = records[0]
    for key in ["#", "Müşteri", "Telefon", "Durum", "Tarih", "Süre", "AI Özeti (Ham)"]:
        assert key in rec
    assert rec["Müşteri"] == "Ahmet Yılmaz"
    assert rec["Ağrı / romatizma"] == "Var"


def test_pdf_to_csv_message_uses_parser_friendly_text(tmp_path) -> None:
    """The 'no parser fits' message replaces the old 'tablo bulunamadı' string."""
    # Empty PDF: pdfplumber will return zero tables → ValueError with new wording
    import fitz

    pdf = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf))
    doc.close()

    out = tmp_path / "out.csv"
    with pytest.raises(ValueError) as exc:
        GenericTableParser().to_csv(pdf, out)
    assert "Bu PDF formatına uygun parser yok" in str(exc.value)
