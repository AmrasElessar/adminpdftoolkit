"""parse_call_log helper'ı için temel test (PDF olmadan, sadece _parse_qa)."""
from parsers.call_log_360 import _parse_qa, _normalize_text, _is_record_start


def test_parse_qa_simple():
    lines = [
        "S: Ağrı / romatizma",
        "C: Var",
        "S: Yaş",
        "C: Otuz üç",
    ]
    out = _parse_qa(lines)
    assert out["Ağrı / romatizma"] == "Var"
    assert out["Yaş"] == "Otuz üç"


def test_parse_qa_multiline_answer():
    lines = [
        "S: Meslek",
        "C: Mühendislik",
        "ek satır",
        "S: İl",
        "C: Ankara",
    ]
    out = _parse_qa(lines)
    assert out["Meslek"] == "Mühendislik ek satır"
    assert out["İl"] == "Ankara"


def test_parse_qa_empty_answer():
    lines = [
        "S: Sigara",
        "C:",
        "S: Yaş",
        "C: 40",
    ]
    out = _parse_qa(lines)
    assert out["Sigara"] == ""
    assert out["Yaş"] == "40"


def test_normalize_text_drops_empty_lines():
    raw = "satir1\n\n  satir2  \n\nsatir3\n"
    out = _normalize_text(raw)
    assert out == ["satir1", "satir2", "satir3"]


def test_normalize_text_handles_literal_backslash_n():
    raw = "S: Ağrı / romatizma\\nC:\\n\\nS: Yaş"
    out = _normalize_text(raw)
    # Literal \\n'ler gerçek \n'ye çevriliyor
    assert "S: Ağrı / romatizma" in out
    assert "C:" in out
    assert "S: Yaş" in out


def test_is_record_start():
    assert _is_record_start("1")
    assert _is_record_start("999")
    assert not _is_record_start("1.0")
    assert not _is_record_start("a1")
    assert not _is_record_start("")
