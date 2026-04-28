"""Sanity tests for the dashboard card filter.

The dashboard's card visibility logic (``refreshDashCards`` in
``templates/index.html``) drives off ``CAT_ACCEPTS`` — a JS object that
maps each category id to the file types that should reveal it. We
removed the ``Toplu İşlem`` card and want to keep its mapping out of the
table; we also want to lock down the PDF-only vs ``→ PDF`` split so a
future careless edit doesn't silently revive the wrong card on the
wrong file type.

We don't run JavaScript in CI, so these tests parse the HTML returned
by ``/`` and assert against the static markup + the literal
``CAT_ACCEPTS`` map text. That's enough to catch every regression we've
seen so far without paying the Playwright / jsdom tax.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

import app
import core


@pytest.fixture
def html(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(core, "is_local_request", lambda req: True)
    client = TestClient(app.app)
    r = client.get("/")
    assert r.status_code == 200
    return r.text


def _extract_cat_accepts(html: str) -> dict[str, list[str]]:
    """Find the ``const CAT_ACCEPTS = { ... };`` block and parse it as
    a tiny dict literal — every entry is ``key: ["a", "b"]``."""
    m = re.search(r"const CAT_ACCEPTS = \{([^}]+)\};", html, re.S)
    assert m, "CAT_ACCEPTS block missing from index.html"
    body = m.group(1)
    out: dict[str, list[str]] = {}
    for entry in re.finditer(
        r"(\w+)\s*:\s*\[([^\]]*)\]", body
    ):
        key = entry.group(1)
        values = [v.strip().strip('"').strip("'")
                   for v in entry.group(2).split(",")
                   if v.strip()]
        out[key] = values
    return out


def _card_categories(html: str) -> set[str]:
    """Every ``<button class="dash-card" data-cat="..."`` in the markup."""
    return set(re.findall(r'<button[^>]*class="dash-card"[^>]*data-cat="([^"]+)"', html))


# ---------------------------------------------------------------------------
# Card inventory
# ---------------------------------------------------------------------------
EXPECTED_CARDS: set[str] = {
    "convert",   # PDF → Excel/Word/JPG (sync + async)
    "tools",     # Düzenle (sayfa) — merge/split/compress/etc.
    "editor",    # Editör (içerik) — annotation/overlay/replace
    "analyze",   # Boş sayfa, imza, kategori, deep-analyze
    "extract",   # PDF → MD/CSV/img/outline/metadata
    "find",      # Bul / vurgula
    "generate",  # → PDF (image/docx/xlsx/html/url)
}


def test_dashboard_renders_expected_cards(html: str) -> None:
    """The card inventory is intentional — adding/removing one is a UX
    decision that should be reflected in this test."""
    assert _card_categories(html) == EXPECTED_CARDS


def test_batch_card_no_longer_present(html: str) -> None:
    """The ``Toplu İşlem`` card was removed (the merged-Excel + dedupe +
    distribution flow is now reached via the convert flow itself).
    The data-cat="batch" button must NOT come back."""
    assert 'data-cat="batch"' not in html


# ---------------------------------------------------------------------------
# CAT_ACCEPTS contract
# ---------------------------------------------------------------------------
def test_cat_accepts_keys_match_card_inventory(html: str) -> None:
    """Every card needs a CAT_ACCEPTS entry; every CAT_ACCEPTS entry
    needs a card. Drift either way is a UX bug."""
    accepts = _extract_cat_accepts(html)
    assert set(accepts) == EXPECTED_CARDS


def test_pdf_only_cards_route_off_pdf(html: str) -> None:
    """PDF-input cards (convert / tools / editor / analyze / extract /
    find) must accept exactly ``["pdf"]`` — surfacing them when the user
    dropped a Word doc would crash the underlying endpoints."""
    accepts = _extract_cat_accepts(html)
    pdf_only = {"convert", "tools", "editor", "analyze", "extract", "find"}
    for cat in pdf_only:
        assert accepts[cat] == ["pdf"], (
            f"Card '{cat}' should accept only PDF; got {accepts[cat]}"
        )


def test_generate_card_rejects_pdf(html: str) -> None:
    """The ``→ PDF`` card is for users who DON'T have a PDF yet —
    surfacing it on a PDF input would be a dead-end. Must list every
    non-PDF input we support, and explicitly NOT list ``pdf``."""
    accepts = _extract_cat_accepts(html)
    gen = set(accepts["generate"])
    assert "pdf" not in gen
    assert {"image", "docx", "xlsx"}.issubset(gen)


def test_no_card_matches_both_pdf_and_non_pdf(html: str) -> None:
    """Mixing pdf with image/docx/xlsx in the same card would defeat
    the type-aware filtering — every card belongs to exactly one
    'input world'."""
    accepts = _extract_cat_accepts(html)
    for cat, types in accepts.items():
        ts = set(types)
        if "pdf" in ts:
            assert ts == {"pdf"}, (
                f"Card '{cat}' mixes pdf with {ts - {'pdf'}}"
            )


# ---------------------------------------------------------------------------
# Drop input contract
# ---------------------------------------------------------------------------
def test_dash_file_input_accepts_pdf_word_excel_image(html: str) -> None:
    """The hero accepts the four input families we route to the cards.
    Other formats are surfaced through later forms but must not be
    selectable from the hero — keeps the dashboard's promise honest."""
    m = re.search(r'<input[^>]*id="dashFileInput"[^>]*accept="([^"]+)"', html)
    assert m, "dashFileInput is missing the accept attribute"
    accept = m.group(1).lower()
    for must_have in ("pdf", "docx", "xlsx", "image/"):
        assert must_have in accept, f"hero input drops {must_have!r}"
