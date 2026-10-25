"""Locate external programs (Tesseract, Ghostscript, …).

Windows installers usually don't add these to PATH, so besides PATH we look
in their default install folders. A program found that way is also put on
this process's PATH so libraries that call it by name (OCRmyPDF) find it too.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import sys
from pathlib import Path


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


def use_user_tessdata() -> None:
    """Point Tesseract at the per-user language folder when it has data,
    unless TESSDATA_PREFIX is already set by the user."""
    folder = user_tessdata()
    if "TESSDATA_PREFIX" not in os.environ and any(folder.glob("*.traineddata")):
        os.environ["TESSDATA_PREFIX"] = str(folder)
