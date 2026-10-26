"""The About & Licences data: what the app is, where it runs, and everything it uses.

Three sources, so nothing is forgotten:

* ``about.json`` — the hand-written half (systems, programs, fonts, data,
  build tools, methods, first-run warnings), in Turkish and English separately;
* the Python packages actually installed, walked from this package's own
  requirements via their metadata (name, version, licence, homepage);
* the files of tools bundled in the Windows package (``ocr/``, ``gs/``),
  read from their manifests, and the npm packages in the web bundle
  (``web_dist/licenses.json``, written at build time).

``scripts/third_party.py`` renders the same data as THIRD_PARTY_LICENSES.md.
"""

from __future__ import annotations

import json
import os
import platform
import re
import sys
from functools import lru_cache
from importlib.metadata import Distribution, PackageNotFoundError, distribution
from pathlib import Path
from typing import Any

from .config import VERSION
from .core.tools import GS_BUNDLE_ENV, OCR_BUNDLE_ENV

HERE = Path(__file__).parent
# Metadata that does not carry a clean SPDX id.
LICENCE_OVERRIDES = {"pymupdf": "AGPL-3.0 (or Artifex commercial)"}


def _key(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _field(dist: Distribution, key: str) -> str:
    values = dist.metadata.get_all(key) or []
    return str(values[0]) if values else ""


def _licence(dist: Distribution) -> str:
    meta = dist.metadata
    name = _key(meta["Name"])
    if name in LICENCE_OVERRIDES:
        return LICENCE_OVERRIDES[name]
    if _field(dist, "License-Expression"):
        return _field(dist, "License-Expression")
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    if classifiers:
        return " / ".join(dict.fromkeys(classifiers))
    text = _field(dist, "License").strip().splitlines()
    return text[0][:60] if text else "?"


def _url(dist: Distribution) -> str:
    meta = dist.metadata
    for entry in meta.get_all("Project-URL") or []:
        label, _, link = entry.partition(",")
        if label.strip().lower() in ("source", "source code", "repository", "homepage", "home", "github", "code"):
            return str(link).strip()
    return _field(dist, "Home-page") or f"https://pypi.org/project/{meta['Name']}/"


def _requirement(raw: str) -> str | None:
    """Name of a requirement that applies here (markers evaluated, extras skipped)."""
    try:
        from packaging.requirements import Requirement
    except ImportError:  # pragma: no cover - packaging comes with pikepdf
        if ";" in raw:
            return None
        return re.split(r"[\s<>=!~\[(]", raw.strip(), maxsplit=1)[0]
    req = Requirement(raw)
    if req.marker and not req.marker.evaluate({"extra": ""}):
        return None
    return req.name


@lru_cache(maxsize=1)
def python_packages() -> list[dict[str, str]]:
    """Every Python package this app uses, direct ones first, with who pulls it in."""
    try:
        me = distribution("adminpdf")
    except PackageNotFoundError:  # pragma: no cover - running from a bare checkout
        return []
    seen: dict[str, dict[str, str]] = {}

    def record(dist: Distribution, via: str) -> None:
        seen[_key(str(dist.metadata["Name"]))] = {
            "name": str(dist.metadata["Name"]),
            "version": dist.version,
            "license": _licence(dist),
            "url": _url(dist),
            "via": via,
        }

    def walk(dist: Distribution) -> None:
        for raw in dist.requires or []:
            child = _requirement(raw)
            if not child or _key(child) in seen:
                continue
            try:
                sub = distribution(child)
            except PackageNotFoundError:
                continue
            record(sub, seen[_key(str(dist.metadata["Name"]))]["via"] or str(dist.metadata["Name"]))
            walk(sub)

    # Direct requirements first, so a library we import ourselves is never
    # shown as merely pulled in by another one.
    roots = []
    for raw in me.requires or []:
        name = _requirement(raw)
        if not name:
            continue
        try:
            roots.append(distribution(name))
        except PackageNotFoundError:
            continue
    for dist in roots:
        record(dist, "")
    for dist in roots:
        walk(dist)
    return sorted(seen.values(), key=lambda p: (bool(p["via"]), p["name"].lower()))


def bundled_files() -> list[dict[str, Any]]:
    """Tools shipped inside this package (Windows): versions, sources and files."""
    out = []
    for env, label in ((OCR_BUNDLE_ENV, "Tesseract OCR"), (GS_BUNDLE_ENV, "Ghostscript")):
        folder = os.environ.get(env)
        if not folder:
            continue
        try:
            manifest = json.loads((Path(folder) / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append(
            {
                "name": label,
                "version": str(manifest.get("version", "")),
                "sources": manifest.get("sources", {}),
                "files": sorted(manifest.get("files", {})),
            }
        )
    return out


def web_packages(web_dist: Path) -> list[dict[str, str]]:
    try:
        data = json.loads((web_dist / "licenses.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [p for p in data if isinstance(p, dict)]


@lru_cache(maxsize=1)
def curated() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((HERE / "about.json").read_text(encoding="utf-8"))
    return data


def runtime() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "embedded": "yes" if any(Path(sys.executable).parent.glob("python*._pth")) else "",
    }


def about(web_dist: Path) -> dict[str, Any]:
    return {
        "version": VERSION,
        "license": "AGPL-3.0-or-later",
        **curated(),
        "runtime": runtime(),
        "python_packages": python_packages(),
        "web_packages": web_packages(web_dist),
        "bundled": bundled_files(),
    }
