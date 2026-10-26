"""Locate external programs (Tesseract, Ghostscript, …).

Windows installers usually don't add these to PATH, so besides PATH we look
in their default install folders. A program found that way is also put on
this process's PATH so libraries that call it by name (OCRmyPDF) find it too.
"""

from __future__ import annotations

import glob
import hashlib
import json
import logging
import os
import re
import shutil
import sys
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("adminpdf.tools")

# Set by the Windows package launcher to its bundled tool folders.
OCR_BUNDLE_ENV = "APT_OCR_DIR"
GS_BUNDLE_ENV = "APT_GS_DIR"


def _windows_roots() -> list[str]:
    roots = [os.environ.get(k, "") for k in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)")]
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        roots.append(str(Path(local) / "Programs"))
    roots += ["C:/Program Files", "C:/Program Files (x86)"]
    return list(dict.fromkeys(r for r in roots if r))


def find_tool(
    names: tuple[str, ...], windows_globs: tuple[str, ...] = (), unix_paths: tuple[str, ...] = ()
) -> str | None:
    """First match of ``names`` on PATH, else in the known install locations.

    ``windows_globs`` are relative to Program Files (e.g. ``"Tesseract-OCR/tesseract.exe"``);
    the newest match wins when a pattern has a version wildcard."""
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    candidates: list[str] = []
    if sys.platform == "win32":
        for root in _windows_roots():
            for pattern in windows_globs:
                candidates += sorted(glob.glob(str(Path(root) / pattern)), key=_version_key, reverse=True)
    candidates += list(unix_paths)
    for c in candidates:
        if Path(c).is_file():
            _add_to_path(str(Path(c).parent))
            return c
    return None


def _version_key(path: str) -> list[tuple[int, int | str]]:
    """Natural sort: gs10.05 > gs9.50."""
    return [(1, int(p)) if p.isdigit() else (0, p) for p in re.split(r"(\d+)", path)]


def _add_to_path(folder: str) -> None:
    parts = os.environ.get("PATH", "").split(os.pathsep)
    if folder not in parts:
        os.environ["PATH"] = os.pathsep.join([folder, *parts])


def user_tessdata() -> Path:
    """Per-user Tesseract language folder filled by ``install-ocr-windows.ps1``."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "AdminPDFToolkit" / "tessdata"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify_bundle(folder: Path) -> list[str]:
    """Files of a bundled tool folder that are missing or differ from its
    ``manifest.json`` (SHA-256 per file, written when the package was built).
    Empty means intact; a missing or unreadable manifest is a problem too."""
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        files: dict[str, str] = manifest["files"]
    except (OSError, ValueError, KeyError, TypeError):
        return ["manifest.json"]
    bad = []
    for rel, digest in files.items():
        path = (folder / rel).resolve()
        if not path.is_relative_to(folder.resolve()) or not path.is_file() or _sha256(path) != str(digest).lower():
            bad.append(rel)
    return bad


@lru_cache(maxsize=4)
def _bundled(env: str, exe_rel: str) -> tuple[str | None, str | None]:
    """``(exe, problem)`` for a tool shipped inside the Windows package.
    Its files are checked against the package manifest, offline; a damaged
    or altered bundle is never run (problem ``"damaged"``)."""
    root = os.environ.get(env)
    if not root:
        return None, None
    folder = Path(root)
    exe = folder / exe_rel
    if not exe.is_file():
        return None, None
    bad = verify_bundle(folder)
    if bad:
        log.error("bundled %s failed its integrity check: %s", folder.name, ", ".join(bad[:10]))
        return None, "damaged"
    _add_to_path(str(exe.parent))
    return str(exe), None


def bundled_ocr() -> tuple[str | None, str | None]:
    """The package's Tesseract (with its own tessdata), verified."""
    exe, problem = _bundled(OCR_BUNDLE_ENV, "tesseract.exe" if sys.platform == "win32" else "tesseract")
    if exe:
        os.environ["TESSDATA_PREFIX"] = str(Path(exe).parent / "tessdata")
    return exe, problem


def bundled_ghostscript() -> tuple[str | None, str | None]:
    """The package's Ghostscript (PDF/A), verified."""
    return _bundled(GS_BUNDLE_ENV, "bin/gswin64c.exe" if sys.platform == "win32" else "bin/gs")


def use_user_tessdata() -> None:
    """Point Tesseract at the per-user language folder when it has data,
    unless TESSDATA_PREFIX is already set by the user."""
    folder = user_tessdata()
    if "TESSDATA_PREFIX" not in os.environ and any(folder.glob("*.traineddata")):
        os.environ["TESSDATA_PREFIX"] = str(folder)
