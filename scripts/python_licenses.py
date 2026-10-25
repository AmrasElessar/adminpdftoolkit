"""Print the runtime Python dependency tree of the server as a Markdown table.

Run inside the server's environment and paste the output into
THIRD_PARTY_LICENSES.md:  python scripts/python_licenses.py
"""

from __future__ import annotations

import re
import tomllib
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

from packaging.requirements import Requirement

PYPROJECT = Path(__file__).resolve().parent.parent / "server" / "pyproject.toml"


# Metadata that doesn't carry a clean SPDX id.
OVERRIDES = {"pymupdf": "AGPL-3.0 (or Artifex commercial)"}


def licence(meta) -> str:  # type: ignore[no-untyped-def]
    if meta["Name"].lower() in OVERRIDES:
        return OVERRIDES[meta["Name"].lower()]
    if meta.get("License-Expression"):
        return str(meta["License-Expression"])
    for c in meta.get_all("Classifier") or []:
        if c.startswith("License ::"):
            return c.split("::")[-1].strip()
    return (meta.get("License") or "?").splitlines()[0][:60]


def url(meta) -> str:  # type: ignore[no-untyped-def]
    for u in meta.get_all("Project-URL") or []:
        label, _, link = u.partition(",")
        if label.strip().lower() in ("source", "source code", "repository", "homepage", "home", "github"):
            return link.strip()
    return meta.get("Home-page") or f"https://pypi.org/project/{meta['Name']}/"


def main() -> None:
    roots = [Requirement(r).name for r in tomllib.loads(PYPROJECT.read_text())["project"]["dependencies"]]
    seen: dict[str, tuple[str, str, str, str, str]] = {}

    def walk(name: str, via: str) -> None:
        key = re.sub(r"[-_.]+", "-", name).lower()
        if key in seen:
            return
        try:
            dist = distribution(name)
        except PackageNotFoundError:
            return
        meta = dist.metadata
        seen[key] = (meta["Name"], dist.version, licence(meta), url(meta), via)
        for raw in dist.requires or []:
            req = Requirement(raw)
            if req.marker and not req.marker.evaluate({"extra": ""}):
                continue
            walk(req.name, via or meta["Name"])

    for root in roots:
        walk(root, "")
    print("| Paket / Package | Sürüm | Lisans | Gelen / Pulled in by |")
    print("|---|---|---|---|")
    for name, version, lic, link, via in sorted(seen.values(), key=lambda r: r[0].lower()):
        print(f"| [{name}]({link}) | {version} | {lic} | {via or 'doğrudan / direct'} |")


if __name__ == "__main__":
    main()
