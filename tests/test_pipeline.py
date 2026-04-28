"""Dedupe + filter pipeline testleri."""
from core import normalize_phone as _normalize_phone
from pipelines.batch_convert import apply_pipeline as _apply_pipeline


def _rec(sira, telefon, il="", durum="ended"):
    return {
        "Sıra": sira,
        "Müşteri": f"K{sira}",
        "Telefon": telefon,
        "Durum": durum,
        "İkamet ili": il,
    }


def test_normalize_phone_strips_spaces():
    assert _normalize_phone("+90 506 432 07 46") == "+905064320746"
    assert _normalize_phone("0506 432 07 46") == "05064320746"
    assert _normalize_phone("") == ""
    assert _normalize_phone(None) == ""


def test_pipeline_dedupe_only():
    records = [
        _rec(1, "+905061234567", "Ankara"),
        _rec(2, "+905061234567", "Ankara"),  # mükerrer
        _rec(3, "+905062223344", "İstanbul"),
        _rec(4, "+905061234567", "Ankara"),  # mükerrer
    ]
    sources = ["a", "a", "b", "b"]
    state = {"deduplicated": True, "filters": {}}
    out_recs, out_srcs = _apply_pipeline(records, sources, state)
    assert len(out_recs) == 2
    # İlk geçen kalır
    assert out_recs[0]["Müşteri"] == "K1"
    assert out_recs[1]["Müşteri"] == "K3"
    # Sıra yenilenmiş
    assert out_recs[0]["Sıra"] == 1
    assert out_recs[1]["Sıra"] == 2


def test_pipeline_filter_only():
    records = [
        _rec(1, "1", "Ankara"),
        _rec(2, "2", "İzmir"),
        _rec(3, "3", "Ankara"),
        _rec(4, "4", ""),  # boş
    ]
    sources = ["a"] * 4
    # Sadece Ankara
    state = {"deduplicated": False, "filters": {"İkamet ili": ["Ankara"]}}
    out_recs, _ = _apply_pipeline(records, sources, state)
    assert len(out_recs) == 2
    assert all(r["İkamet ili"] == "Ankara" for r in out_recs)


def test_pipeline_filter_empty_value():
    records = [
        _rec(1, "1", "Ankara"),
        _rec(2, "2", ""),
        _rec(3, "3", ""),
    ]
    sources = ["a"] * 3
    # Sadece (boş) olanlar
    state = {"deduplicated": False, "filters": {"İkamet ili": ["(boş)"]}}
    out_recs, _ = _apply_pipeline(records, sources, state)
    assert len(out_recs) == 2
    assert all(r["İkamet ili"] == "" for r in out_recs)


def test_pipeline_dedupe_then_filter():
    records = [
        _rec(1, "+901", "Ankara"),
        _rec(2, "+901", "Ankara"),  # dup
        _rec(3, "+902", "İzmir"),
        _rec(4, "+903", "Ankara"),
    ]
    sources = ["a"] * 4
    state = {"deduplicated": True, "filters": {"İkamet ili": ["Ankara"]}}
    out_recs, _ = _apply_pipeline(records, sources, state)
    # Dedupe sonrası 3 kayıt: 1, 3, 4
    # Filter: sadece Ankara (1 ve 4)
    assert len(out_recs) == 2
    assert out_recs[0]["Müşteri"] == "K1"
    assert out_recs[1]["Müşteri"] == "K4"


def test_pipeline_no_state_returns_original():
    records = [_rec(1, "+901"), _rec(2, "+902")]
    sources = ["a", "b"]
    state = {"deduplicated": False, "filters": {}}
    out_recs, out_srcs = _apply_pipeline(records, sources, state)
    assert len(out_recs) == 2
    assert out_srcs == sources
