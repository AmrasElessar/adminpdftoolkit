"""About & Licences: complete, and Turkish and English kept apart."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement

from adminpdf.about import curated, python_packages

from .conftest import Api

ROOT = Path(__file__).resolve().parent.parent


def _pairs(node: Any) -> list[dict[str, str]]:
    """Every {"tr": …, "en": …} text in the curated data."""
    if isinstance(node, dict):
        if set(node) == {"tr", "en"}:
            return [node]
        return [p for v in node.values() for p in _pairs(v)]
    if isinstance(node, list):
        return [p for v in node for p in _pairs(v)]
    return []


def test_every_text_exists_in_both_languages() -> None:
    pairs = _pairs(curated())
    assert len(pairs) > 100
    for p in pairs:
        assert isinstance(p["tr"], str) and isinstance(p["en"], str)
        if p["tr"] or p["en"]:
            assert p["tr"].strip() and p["en"].strip(), p


def test_every_direct_dependency_is_listed_and_has_a_role() -> None:
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    wanted = {Requirement(r).name.lower().replace("_", "-") for r in declared}
    listed = {p["name"].lower().replace("_", "-") for p in python_packages() if not p["via"]}
    assert wanted <= listed, wanted - listed
    roles = curated()["python_roles"]
    assert wanted <= set(roles), wanted - set(roles)


def test_licences_are_known() -> None:
    for p in python_packages():
        assert p["license"] and p["license"] != "?", p


def test_systems_and_first_run_warnings() -> None:
    data = curated()
    names = " ".join(s["name"]["en"] for s in data["systems"]["server"])
    for system in ("Windows", "macOS", "Linux", "Docker"):
        assert system in names
    warnings = " ".join(w["title"]["en"] for w in data["first_run"])
    assert "SmartScreen" in warnings and "Gatekeeper" in warnings


def test_about_endpoint(api: Api) -> None:
    r = api.c.get("/api/about")
    assert r.status_code == 200
    data = r.json()
    assert data["license"] == "AGPL-3.0-or-later"
    assert len(data["python_packages"]) >= 40
    assert data["first_run"] and data["systems"]["clients"]


def test_third_party_file_has_separate_languages() -> None:
    text = (ROOT.parent / "THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")
    tr, _, en = text.partition("## Third-Party Licences and Attributions")
    assert "## Üçüncü Taraf Lisansları ve Atıflar" in tr and en
    assert "Çalıştığı sistemler" in tr and "Supported systems" in en
    assert "Supported systems" not in tr and "Çalıştığı sistemler" not in en
