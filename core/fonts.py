"""System font discovery + the merged bundled+system editor font catalog.

Extends the bundled (Noto/DejaVu) catalog from ``editor.py`` with whatever
TTF/OTF families the host operating system already has installed. Reading
TTF metadata uses a pure-stdlib parser — no fontTools dependency.
"""

from __future__ import annotations

import os
import re
import struct as _struct  # used by the TTF / OS/2 parsers below
import sys
from pathlib import Path
from typing import Any

from .editor import (
    EDITOR_FONT_FAMILIES,
    _FONTS_DIR,
    resolve_editor_font as _resolve_editor_font_bundled,
)

_SYSTEM_FONT_CACHE: list[dict[str, Any]] | None = None


def _system_font_dirs() -> list[Path]:
    """Return the list of platform-standard directories to scan for fonts."""
    plat = sys.platform
    candidates: list[Path] = []
    if plat == "win32":
        candidates = [
            Path("C:/Windows/Fonts"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts",
        ]
    elif plat == "darwin":
        candidates = [
            Path("/System/Library/Fonts"),
            Path("/System/Library/Fonts/Supplemental"),
            Path("/Library/Fonts"),
            Path.home() / "Library" / "Fonts",
        ]
    else:
        candidates = [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path.home() / ".fonts",
            Path.home() / ".local" / "share" / "fonts",
        ]
    return [p for p in candidates if p.is_dir()]


def _read_ttf_metadata(path: Path) -> dict[str, Any] | None:
    """Read family + subfamily + fsType from a .ttf / .otf file.

    Pure-stdlib parser — no fontTools dependency. Reads only the ``name`` and
    ``OS/2`` tables. Returns ``None`` if the file isn't a recognisable
    OpenType / TrueType single-font container (skips ``.ttc`` collections).
    """
    try:
        with open(path, "rb") as f:
            data = f.read(min(path.stat().st_size, 1024 * 256))  # 256 KB is plenty
    except OSError:
        return None
    if len(data) < 12:
        return None

    sig = data[:4]
    if sig not in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1"):
        return None

    try:
        num_tables = _struct.unpack(">H", data[4:6])[0]
    except _struct.error:
        return None

    tables: dict[bytes, tuple[int, int]] = {}
    for i in range(num_tables):
        rec = 12 + i * 16
        if rec + 16 > len(data):
            return None
        tag = data[rec : rec + 4]
        offset = _struct.unpack(">I", data[rec + 8 : rec + 12])[0]
        length = _struct.unpack(">I", data[rec + 12 : rec + 16])[0]
        tables[tag] = (offset, length)

    if b"name" not in tables:
        return None
    name_off, name_len = tables[b"name"]
    if name_off + 6 > len(data):
        return None
    try:
        _format = _struct.unpack(">H", data[name_off : name_off + 2])[0]
        count = _struct.unpack(">H", data[name_off + 2 : name_off + 4])[0]
        string_offset = _struct.unpack(">H", data[name_off + 4 : name_off + 6])[0]
    except _struct.error:
        return None
    string_base = name_off + string_offset

    family = subfamily = pref_family = pref_subfamily = None
    for i in range(count):
        rec = name_off + 6 + i * 12
        if rec + 12 > len(data):
            break
        try:
            platform = _struct.unpack(">H", data[rec : rec + 2])[0]
            encoding = _struct.unpack(">H", data[rec + 2 : rec + 4])[0]
            _lang = _struct.unpack(">H", data[rec + 4 : rec + 6])[0]
            name_id = _struct.unpack(">H", data[rec + 6 : rec + 8])[0]
            length = _struct.unpack(">H", data[rec + 8 : rec + 10])[0]
            str_off = _struct.unpack(">H", data[rec + 10 : rec + 12])[0]
        except _struct.error:
            continue
        if string_base + str_off + length > len(data):
            continue
        raw = data[string_base + str_off : string_base + str_off + length]
        try:
            if platform == 3 and encoding in (1, 10):
                value = raw.decode("utf-16-be", errors="ignore").strip("\x00").strip()
            elif platform == 1 and encoding == 0:
                value = raw.decode("mac-roman", errors="ignore").strip()
            elif platform == 0:
                value = raw.decode("utf-16-be", errors="ignore").strip("\x00").strip()
            else:
                continue
        except UnicodeDecodeError:
            continue
        if not value:
            continue
        if name_id == 1 and not family:
            family = value
        elif name_id == 2 and not subfamily:
            subfamily = value
        elif name_id == 16 and not pref_family:
            pref_family = value
        elif name_id == 17 and not pref_subfamily:
            pref_subfamily = value

    family = pref_family or family
    subfamily = pref_subfamily or subfamily or "Regular"
    if not family:
        return None

    fs_type = 0
    if b"OS/2" in tables:
        os2_off, os2_len = tables[b"OS/2"]
        if os2_off + 10 <= len(data):
            try:
                fs_type = _struct.unpack(">H", data[os2_off + 8 : os2_off + 10])[0]
            except _struct.error:
                fs_type = 0

    sub_lower = subfamily.lower()
    bold = ("bold" in sub_lower) or ("black" in sub_lower) or ("heavy" in sub_lower)
    italic = ("italic" in sub_lower) or ("oblique" in sub_lower)
    return {
        "family": family,
        "subfamily": subfamily,
        "bold": bold,
        "italic": italic,
        "fs_type": fs_type,
        "embeddable": (fs_type & 0x0002) == 0,  # bit 1 = Restricted License Embedding
    }


def discover_system_fonts(*, refresh: bool = False) -> list[dict[str, Any]]:
    """Scan platform-standard font dirs and return embeddable families.

    Each entry::

        {"id": "system:arial",
         "label": "Arial",
         "category": "system",
         "variants": ["regular", "bold", "italic", "bolditalic"],
         "files": {"regular": "C:/Windows/Fonts/arial.ttf", ...}}

    Restricted-embed (fsType bit 1) fonts are filtered out so output PDFs
    never embed a font we don't have legal rights to redistribute.
    Cached for the process lifetime; pass ``refresh=True`` to re-scan.
    """
    global _SYSTEM_FONT_CACHE
    if _SYSTEM_FONT_CACHE is not None and not refresh:
        return _SYSTEM_FONT_CACHE

    families: dict[str, dict[str, Any]] = {}
    for d in _system_font_dirs():
        try:
            for path in d.iterdir():
                if not path.is_file():
                    continue
                ext = path.suffix.lower()
                if ext not in (".ttf", ".otf"):
                    continue
                meta = _read_ttf_metadata(path)
                if not meta or not meta.get("embeddable"):
                    continue
                fam = meta["family"]
                key = re.sub(r"[^a-z0-9]+", "-", fam.lower()).strip("-")
                if not key:
                    continue
                style = (
                    "bolditalic" if meta["bold"] and meta["italic"]
                    else "bold" if meta["bold"]
                    else "italic" if meta["italic"]
                    else "regular"
                )
                entry = families.setdefault(key, {
                    "id": f"system:{key}",
                    "label": fam,
                    "category": "system",
                    "variants": [],
                    "files": {},
                })
                # First file wins for any given variant
                if style not in entry["files"]:
                    entry["files"][style] = str(path)
                    entry["variants"].append(style)
        except OSError:
            continue

    # Filter to families that have at least a regular or any variant
    result = sorted(
        (f for f in families.values() if f["variants"]),
        key=lambda f: f["label"].lower(),
    )
    _SYSTEM_FONT_CACHE = result
    return result


def resolve_system_font(family_id: str, *, bold: bool = False, italic: bool = False) -> Path | None:
    """Resolve ``"system:arial"`` + style → on-disk path."""
    if not family_id.startswith("system:"):
        return None
    key = family_id.split(":", 1)[1]
    for entry in discover_system_fonts():
        if entry["id"] == family_id or re.sub(r"[^a-z0-9]+", "-", entry["label"].lower()).strip("-") == key:
            files = entry.get("files", {})
            for variant in (
                "bolditalic" if bold and italic else None,
                "bold" if bold else None,
                "italic" if italic else None,
                "regular",
            ):
                if variant and variant in files:
                    p = Path(files[variant])
                    if p.is_file():
                        return p
            # Last resort: any variant we have
            for v in entry["variants"]:
                p = Path(files[v])
                if p.is_file():
                    return p
    return None


def resolve_editor_font_with_system(
    family_id: str, *, bold: bool = False, italic: bool = False,
) -> Path | None:
    """Like ``resolve_editor_font`` but also handles ``system:*`` ids."""
    if family_id.startswith("system:"):
        sys_path = resolve_system_font(family_id, bold=bold, italic=italic)
        if sys_path:
            return sys_path
    return _resolve_editor_font_bundled(family_id, bold=bold, italic=italic)


def editor_font_catalog_with_system() -> list[dict[str, Any]]:
    """Public catalog: bundled (Noto/DejaVu) first, then host system fonts."""
    bundled = []
    for fam in EDITOR_FONT_FAMILIES:
        present: list[str] = []
        for variant_key, filename in fam["variants"].items():
            if (_FONTS_DIR / filename).is_file():
                present.append(variant_key)
        if not present:
            continue
        bundled.append({
            "id": fam["id"],
            "label": fam["label"],
            "category": "bundled",
            "variants": present,
        })
    sys_fonts = [
        {"id": f["id"], "label": f["label"], "category": f["category"], "variants": f["variants"]}
        for f in discover_system_fonts()
    ]
    return bundled + sys_fonts
