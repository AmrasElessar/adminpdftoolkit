"""Dağıtım fonksiyonları için temel testler."""
from core import (
    distribute_sequential as _distribute_sequential,
    distribute_roundrobin as _distribute_roundrobin,
    distribute_custom as _distribute_custom,
)


def test_sequential_even():
    records = list(range(300))
    teams = ["A", "B", "C"]
    out = _distribute_sequential(records, teams)
    assert len(out["A"]) == 100
    assert len(out["B"]) == 100
    assert len(out["C"]) == 100
    assert out["A"][0] == 0
    assert out["A"][-1] == 99
    assert out["B"][0] == 100


def test_sequential_uneven():
    records = list(range(301))
    teams = ["A", "B", "C"]
    out = _distribute_sequential(records, teams)
    assert len(out["A"]) == 101
    assert len(out["B"]) == 100
    assert len(out["C"]) == 100


def test_roundrobin_preserves_order():
    records = list(range(12))
    teams = ["A", "B", "C"]
    out = _distribute_roundrobin(records, teams)
    assert out["A"] == [0, 3, 6, 9]
    assert out["B"] == [1, 4, 7, 10]
    assert out["C"] == [2, 5, 8, 11]


def test_custom_basic():
    records = list(range(100))
    teams = ["A", "B"]
    out = _distribute_custom(records, teams, [3, 1])  # %75 / %25
    assert len(out["A"]) == 75
    assert len(out["B"]) == 25


def test_custom_remainder_distributed():
    """Toplam pozitif olduğunda kalanlar fractional sırasına göre dağıtılır."""
    records = list(range(10))
    teams = ["A", "B", "C"]
    out = _distribute_custom(records, teams, [1, 1, 1])
    total = sum(len(v) for v in out.values())
    assert total == 10
    # Her ekibin payı 3 veya 4 olmalı
    for v in out.values():
        assert len(v) in (3, 4)
