"""Record-distribution algorithms + phone normalisation helper."""

from __future__ import annotations

from typing import Any


def distribute_sequential(records: list[Any], teams: list[str]) -> dict[str, list[Any]]:
    """Split records into contiguous blocks, one per team."""
    out: dict[str, list[Any]] = {t: [] for t in teams}
    if not teams or not records:
        return out
    n = len(records)
    per = n // len(teams)
    extra = n % len(teams)
    i = 0
    for j, t in enumerate(teams):
        size = per + (1 if j < extra else 0)
        out[t] = records[i : i + size]
        i += size
    return out


def distribute_roundrobin(records: list[Any], teams: list[str]) -> dict[str, list[Any]]:
    """Distribute records 1→T1, 2→T2, 3→T3, 4→T1, …"""
    out: dict[str, list[Any]] = {t: [] for t in teams}
    if not teams:
        return out
    for idx, rec in enumerate(records):
        out[teams[idx % len(teams)]].append(rec)
    return out


def distribute_custom(
    records: list[Any], teams: list[str], ratios: list[float]
) -> dict[str, list[Any]]:
    """Distribute records by a custom ratio list (must align with teams)."""
    out: dict[str, list[Any]] = {t: [] for t in teams}
    if not teams or not records:
        return out
    total = sum(ratios)
    if total <= 0:
        return out
    counts = [round(len(records) * r / total) for r in ratios]
    diff = len(records) - sum(counts)
    if diff != 0:
        counts[0] += diff
    i = 0
    for j, t in enumerate(teams):
        size = max(0, counts[j])
        out[t] = records[i : i + size]
        i += size
    return out


def normalize_phone(p: Any) -> str:
    """Telefon karşılaştırması için: yalnızca rakamlar ve `+` işareti kalır."""
    s = str(p or "").strip()
    if not s:
        return ""
    return "".join(ch for ch in s if ch.isdigit() or ch == "+")
