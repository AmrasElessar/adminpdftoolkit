"""Splitting rows between teams (v1 ``core/distribution.py``) and safe,
unique per-team file names."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from typing import Literal, TypeVar

from ...core.errors import UserError
from ...core.files import safe_filename

T = TypeVar("T")
Mode = Literal["sequential", "round_robin", "ratio"]
WeightMode = Literal["percent", "factor"]


def sequential_counts(total: int, teams: int) -> list[int]:
    """Equal shares; the first ``total % teams`` teams get one more."""
    per, extra = divmod(total, teams)
    return [per + (1 if j < extra else 0) for j in range(teams)]


def ratio_counts(total: int, weights: Sequence[float]) -> list[int]:
    """Largest-remainder rounding: shares always sum to ``total`` and never
    go negative. (v1's server added the whole rounding error to the first
    team, which could make its share negative; its UI preview used this
    method, so the preview and the result could disagree.) Ties go to the
    earlier team."""
    weight_sum = math.fsum(weights)
    if weight_sum <= 0:
        raise UserError("Oranların toplamı sıfırdan büyük olmalı.", "The weights must add up to more than zero.")
    exact = [total * w / weight_sum for w in weights]
    counts = [math.floor(x) for x in exact]
    rest = total - sum(counts)
    order = sorted(range(len(weights)), key=lambda i: (-(exact[i] - counts[i]), i))
    for i in order[:rest]:
        counts[i] += 1
    return counts


def check_weights(weights: Sequence[float], teams: int, mode: WeightMode) -> None:
    if len(weights) != teams:
        raise UserError(
            f"Her ekip için bir oran girin ({teams} ekip, {len(weights)} oran).",
            f"Enter one weight per team ({teams} teams, {len(weights)} weights).",
        )
    if any(not math.isfinite(w) or w < 0 for w in weights):
        raise UserError("Oranlar negatif olamaz.", "Weights cannot be negative.")
    if mode == "percent" and abs(math.fsum(weights) - 100) > 0.01:
        raise UserError(
            f"Doğrudan oran modunda yüzdelerin toplamı %100 olmalı (şu an %{round(math.fsum(weights), 2)}).",
            f"In percent mode the percentages must total 100% (now {round(math.fsum(weights), 2)}%).",
        )


def distribute(rows: Sequence[T], teams: int, mode: Mode, weights: Sequence[float] | None = None) -> list[list[T]]:
    """Rows per team, in team order. ``sequential`` and ``ratio`` hand out
    contiguous blocks; ``round_robin`` deals 1→T1, 2→T2, …, n+1→T1."""
    if teams < 1:
        raise UserError("En az bir ekip gerekli.", "At least one team is needed.")
    if mode == "round_robin":
        return [list(rows[j::teams]) for j in range(teams)]
    counts = sequential_counts(len(rows), teams) if mode == "sequential" else ratio_counts(len(rows), weights or [])
    out: list[list[T]] = []
    start = 0
    for c in counts:
        out.append(list(rows[start : start + c]))
        start += c
    return out


def team_file_names(teams: Sequence[str], *, ext: str = ".xlsx", reserved: Sequence[str] = ()) -> list[str]:
    """One distinct, filesystem-safe name per team.

    v1 ran team names through a basename-style sanitiser, so ``a/b`` and
    ``x/b`` both became ``b.xlsx`` and ``a:b`` / ``a?b`` both ``a_b.xlsx`` —
    later teams silently overwrote earlier ones in the ZIP. Here separators
    are replaced (not cut), and clashes — compared case-insensitively, as on
    Windows — get a `` (2)`` suffix.
    """
    taken = {r.casefold() for r in reserved}
    out: list[str] = []
    for i, team in enumerate(teams, start=1):
        stem = re.sub(r"[\\/]", "_", team).strip()
        name = safe_filename(f"{stem}{ext}", default=f"ekip_{i}")
        stem = (name[: -len(ext)] if name.lower().endswith(ext) else name).strip() or f"ekip_{i}"
        candidate, n = stem, 2
        while f"{candidate}{ext}".casefold() in taken:
            candidate = f"{stem} ({n})"
            n += 1
        taken.add(f"{candidate}{ext}".casefold())
        out.append(f"{candidate}{ext}")
    return out
