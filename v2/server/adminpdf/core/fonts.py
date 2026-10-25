"""Font catalogue: PDF base-14, bundled and locally installed fonts.

The editor needs three things from fonts:

* a catalogue the UI can offer (``GET /api/fonts``) with every face's weight,
  style and licence flag,
* the bytes of a face so the browser can preview text WYSIWYG and the worker
  can embed it,
* a best-effort mapping from the chaotic font names found inside PDFs
  (``ABCDEF+TimesNewRomanPSMT``, ``Arial,Bold``, ``CalibriSemibold``…) to a
  catalogue family.

Font metadata is read with a small seek-based ``sfnt`` reader (TrueType,
OpenType/CFF and TrueType collections): only the table directory and the
``name``/``OS/2``/``post``/``head`` tables are touched, every offset is
bounds-checked against the file size and every read is capped, so a
malformed or hostile file can't make it allocate or loop.
"""

from __future__ import annotations

import hashlib
import os
import re
import struct
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Literal

from .pdf import FONT_DIR

Source = Literal["standard", "bundled", "system"]

MAX_FONT_FILES = 5000
MAX_FONT_BYTES = 50 * 1024 * 1024
MAX_FACES_PER_COLLECTION = 64
MAX_TABLES = 512
_NAME_TABLE_CAP = 1024 * 1024
FONT_EXTENSIONS = frozenset({".ttf", ".otf", ".ttc", ".otc"})

# fsType bits (OS/2): only the low nibble is the embedding permission level.
FS_RESTRICTED = 0x0002


# -- sfnt reader ------------------------------------------------------------------
@dataclass(frozen=True)
class FaceInfo:
    """Metadata of one face inside a font file."""

    family: str
    subfamily: str
    full_name: str
    ps_name: str
    weight: int
    italic: bool
    fs_type: int
    monospace: bool
    serif: bool
    index: int

    @property
    def restricted(self) -> bool:
        return (self.fs_type & 0x000F) == FS_RESTRICTED


class _Reader:
    """Bounds-checked random access to a font file."""

    def __init__(self, f: BinaryIO, size: int) -> None:
        self.f = f
        self.size = size

    def read(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > self.size:
            raise ValueError("read out of bounds")
        self.f.seek(offset)
        data = self.f.read(length)
        if len(data) != length:
            raise ValueError("short read")
        return data


_SFNT_VERSIONS = (b"\x00\x01\x00\x00", b"OTTO", b"true")

# (platform, encoding) pairs whose strings are UTF-16BE.
_UTF16_PLATFORMS = {0, 3}


def _table_directory(r: _Reader, offset: int) -> dict[bytes, tuple[int, int]]:
    head = r.read(offset, 12)
    if head[:4] not in _SFNT_VERSIONS:
        raise ValueError("not an sfnt")
    (num_tables,) = struct.unpack_from(">H", head, 4)
    if not 0 < num_tables <= MAX_TABLES:
        raise ValueError("bad table count")
    directory = r.read(offset + 12, num_tables * 16)
    tables: dict[bytes, tuple[int, int]] = {}
    for i in range(num_tables):
        tag, _checksum, t_off, t_len = struct.unpack_from(">4sIII", directory, i * 16)
        if t_off + t_len <= r.size and tag not in tables:
            tables[tag] = (t_off, t_len)
    return tables


def _parse_names(data: bytes) -> dict[int, str]:
    """Best string per name id, preferring Windows/Unicode US-English."""
    if len(data) < 6:
        return {}
    _fmt, count, string_offset = struct.unpack_from(">HHH", data, 0)
    best: dict[int, tuple[int, str]] = {}
    for i in range(min(count, 4096)):
        rec = 6 + i * 12
        if rec + 12 > len(data):
            break
        platform, encoding, lang, name_id, length, str_off = struct.unpack_from(">HHHHHH", data, rec)
        if name_id not in (1, 2, 4, 6, 16, 17):
            continue
        start = string_offset + str_off
        raw = data[start : start + length]
        if len(raw) != length or not raw:
            continue
        if platform in _UTF16_PLATFORMS:
            if platform == 3 and encoding not in (0, 1, 10):
                continue
            value = raw.decode("utf-16-be", errors="replace")
            score = 3 if platform == 3 and lang == 0x0409 else 2
        elif platform == 1 and encoding == 0:
            value = raw.decode("mac-roman", errors="replace")
            score = 1 if lang == 0 else 0
        else:
            continue
        value = value.replace("\x00", "").strip()
        if value and (name_id not in best or score > best[name_id][0]):
            best[name_id] = (score, value[:200])
    return {k: v for k, (_s, v) in best.items()}


_WEIGHT_WORDS: tuple[tuple[tuple[str, ...], int], ...] = (
    (("extrablack", "ultrablack"), 950),
    (("extrabold", "ultrabold"), 800),
    (("semibold", "demibold"), 600),
    (("extralight", "ultralight"), 200),
    (("hairline", "thin"), 100),
    (("black", "heavy"), 900),
    (("bold",), 700),
    (("demi",), 600),
    (("medium",), 500),
    (("light",), 300),
    (("book", "regular", "normal", "roman"), 400),
)


def weight_from_text(text: str) -> int | None:
    """``"Semi Bold Italic"`` → 600; ``None`` when no weight word is present."""
    norm = re.sub(r"[\s\-_]+", "", text.lower())
    for words, weight in _WEIGHT_WORDS:
        if any(w in norm for w in words):
            return min(weight, 900)
    return None


def _italic_from_text(text: str) -> bool:
    low = text.lower()
    return "italic" in low or "oblique" in low or "kursiv" in low


_SERIF_HINTS = (
    "serif",
    "times",
    "georgia",
    "garamond",
    "cambria",
    "caladea",
    "palatino",
    "minion",
    "baskerville",
    "bookman",
    "century",
    "didot",
    "caslon",
    "antiqua",
    "tinos",
    "roman",
    "constantia",
    "charter",
)
_MONO_HINTS = ("mono", "courier", "consol", "code", "menlo", "cousine", "fixed", "typewriter")


def _guess_serif(name: str) -> bool:
    low = name.lower()
    if "sans" in low:
        return False
    return any(h in low for h in _SERIF_HINTS)


def _guess_mono(name: str) -> bool:
    low = name.lower()
    return any(h in low for h in _MONO_HINTS)


def _read_face(r: _Reader, offset: int, index: int) -> FaceInfo | None:
    tables = _table_directory(r, offset)
    if b"name" not in tables:
        return None
    n_off, n_len = tables[b"name"]
    names = _parse_names(r.read(n_off, min(n_len, _NAME_TABLE_CAP)))
    family = names.get(16) or names.get(1)
    if not family:
        return None
    subfamily = names.get(17) or names.get(2) or "Regular"

    weight: int | None = None
    italic = _italic_from_text(subfamily)
    fs_type = 0
    panose = b""
    if b"OS/2" in tables:
        o_off, o_len = tables[b"OS/2"]
        os2 = r.read(o_off, min(o_len, 100))
        if len(os2) >= 10:
            (wclass,) = struct.unpack_from(">H", os2, 4)
            (fs_type,) = struct.unpack_from(">H", os2, 8)
            if 1 <= wclass <= 9:  # some old fonts use a 1–9 scale
                wclass *= 100
            if 1 <= wclass <= 1000:
                weight = wclass
        if len(os2) >= 42:
            panose = os2[32:42]
        if len(os2) >= 64:
            (fs_selection,) = struct.unpack_from(">H", os2, 62)
            italic = italic or bool(fs_selection & 0x0001) or bool(fs_selection & 0x0200)
    elif b"head" in tables:
        h_off, h_len = tables[b"head"]
        if h_len >= 46:
            (mac_style,) = struct.unpack_from(">H", r.read(h_off + 44, 2), 0)
            italic = italic or bool(mac_style & 0x2)
            if mac_style & 0x1:
                weight = 700

    text_weight = weight_from_text(subfamily)
    if weight is None or (weight == 400 and text_weight is not None):
        weight = text_weight or 400
    weight = max(100, min(900, round(weight / 100) * 100))

    mono = _guess_mono(family)
    if b"post" in tables:
        p_off, p_len = tables[b"post"]
        if p_len >= 16:
            (fixed,) = struct.unpack_from(">I", r.read(p_off + 12, 4), 0)
            mono = mono or fixed != 0
    serif = _guess_serif(family)
    if len(panose) == 10 and panose[0] == 2:  # Latin text
        if 2 <= panose[1] <= 10:
            serif = True
        elif 11 <= panose[1] <= 13:
            serif = False
        mono = mono or panose[3] == 9
    return FaceInfo(
        family=family,
        subfamily=subfamily,
        full_name=names.get(4) or f"{family} {subfamily}",
        ps_name=names.get(6) or "",
        weight=weight,
        italic=italic,
        fs_type=fs_type,
        monospace=mono,
        serif=serif and not mono,
        index=index,
    )


def read_font_faces(path: Path) -> list[FaceInfo]:
    """Parse every face of a TTF/OTF/TTC file. Never raises: a broken or
    unsupported file yields an empty list."""
    try:
        size = path.stat().st_size
        if not 12 <= size <= MAX_FONT_BYTES:
            return []
        with path.open("rb") as f:
            r = _Reader(f, size)
            head = r.read(0, 12)
            if head[:4] == b"ttcf":
                (num,) = struct.unpack_from(">I", head, 8)
                num = min(num, MAX_FACES_PER_COLLECTION)
                offsets = struct.unpack_from(f">{num}I", r.read(12, num * 4), 0) if num else ()
            else:
                offsets = (0,)
            faces: list[FaceInfo] = []
            for i, off in enumerate(offsets):
                try:
                    face = _read_face(r, off, i)
                except (ValueError, struct.error):
                    continue
                if face:
                    faces.append(face)
            return faces
    except (OSError, ValueError, struct.error):
        return []


def extract_face(path: Path, index: int) -> bytes:
    """Bytes of a single face. For a collection (TTC), rebuild a standalone
    sfnt from that face's tables — browsers' ``FontFace`` and PyMuPDF both
    want one face per buffer."""
    size = path.stat().st_size
    if size > MAX_FONT_BYTES:
        raise ValueError("font file too large")
    with path.open("rb") as f:
        r = _Reader(f, size)
        head = r.read(0, 12)
        if head[:4] != b"ttcf":
            if index != 0:
                raise ValueError("not a collection")
            return r.read(0, size)
        (num,) = struct.unpack_from(">I", head, 8)
        if not 0 <= index < min(num, MAX_FACES_PER_COLLECTION):
            raise ValueError("face index out of range")
        (offset,) = struct.unpack_from(">I", r.read(12 + 4 * index, 4), 0)
        version = r.read(offset, 4)
        tables = _table_directory(r, offset)
        tags = sorted(tables)
        n = len(tags)
        entry_selector = max(0, n.bit_length() - 1)
        search_range = (1 << entry_selector) * 16
        header = version + struct.pack(">HHHH", n, search_range, entry_selector, n * 16 - search_range)
        directory = b""
        body = b""
        data_start = 12 + 16 * n
        for tag in tags:
            t_off, t_len = tables[tag]
            data = r.read(t_off, t_len)
            padded = data + b"\x00" * (-len(data) % 4)
            checksum = sum(struct.unpack(f">{len(padded) // 4}I", padded)) & 0xFFFFFFFF
            directory += struct.pack(">4sIII", tag, checksum, data_start + len(body), t_len)
            body += padded
        return header + directory + body


# -- catalogue -----------------------------------------------------------------------
@dataclass(frozen=True)
class FontStyle:
    id: str
    family_id: str
    weight: int
    italic: bool
    restricted: bool
    # On-disk face (bundled/system) …
    path: str = ""
    index: int = 0
    # … or a PDF base-14 font code (``helv``, ``tibo``…).
    base14: str = ""

    @property
    def has_file(self) -> bool:
        return bool(self.path)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "weight": self.weight,
            "italic": self.italic,
            "restricted": self.restricted,
            "file": self.has_file and not self.restricted,
        }


@dataclass
class FontFamily:
    id: str
    family: str
    source: Source
    monospace: bool
    serif: bool
    styles: list[FontStyle] = field(default_factory=list)

    @property
    def restricted(self) -> bool:
        return any(s.restricted for s in self.styles)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "family": self.family,
            "source": self.source,
            "styles": [s.public() for s in self.styles],
            "restricted": self.restricted,
            "monospace": self.monospace,
            "serif": self.serif,
        }

    def resolve(self, weight: int = 400, italic: bool = False) -> FontStyle:
        """CSS-like nearest face: same style first, then closest weight
        (ties go to the heavier face for bold requests, lighter otherwise)."""

        def score(s: FontStyle) -> tuple[int, int, int]:
            dist = abs(s.weight - weight)
            tie = (s.weight < weight) if weight > 400 else (s.weight > weight)
            return (int(s.italic != italic), dist, int(tie))

        return min(self.styles, key=score)


_STANDARD: tuple[tuple[str, str, bool, bool, tuple[str, str, str, str]], ...] = (
    # id suffix, family, serif, mono, (regular, bold, italic, bold-italic)
    ("helvetica", "Helvetica", False, False, ("helv", "hebo", "heit", "hebi")),
    ("times", "Times", True, False, ("tiro", "tibo", "tiit", "tibi")),
    ("courier", "Courier", False, True, ("cour", "cobo", "coit", "cobi")),
)


def _standard_families() -> list[FontFamily]:
    out = []
    for key, name, serif, mono, codes in _STANDARD:
        fam = FontFamily(id=f"standard:{key}", family=name, source="standard", monospace=mono, serif=serif)
        for code, (weight, italic) in zip(codes, ((400, False), (700, False), (400, True), (700, True)), strict=True):
            fam.styles.append(
                FontStyle(
                    id=f"std-{code}", family_id=fam.id, weight=weight, italic=italic, restricted=False, base14=code
                )
            )
        out.append(fam)
    return out


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def _style_id(source: str, path: Path, index: int) -> str:
    digest = hashlib.sha256(f"{source}\0{path}\0{index}".encode()).hexdigest()
    return f"f{digest[:23]}"


def system_font_dirs() -> list[Path]:
    """OS font directories. ``APT_SYSTEM_FONT_DIRS`` (``os.pathsep``-separated)
    replaces them — used by tests and locked-down deployments; an empty value
    disables system fonts."""
    override = os.environ.get("APT_SYSTEM_FONT_DIRS")
    if override is not None:
        return [Path(p) for p in override.split(os.pathsep) if p]
    home = Path.home()
    if sys.platform == "win32":
        windir = Path(os.environ.get("WINDIR", "C:/Windows"))
        dirs = [windir / "Fonts"]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
        return dirs
    if sys.platform == "darwin":
        return [
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            home / "Library" / "Fonts",
        ]
    return [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        home / ".local" / "share" / "fonts",
        home / ".fonts",
    ]


def _font_files(dirs: list[Path], budget: list[int]) -> list[Path]:
    """Font files under ``dirs`` (recursive, no symlinked dirs), capped by the
    shared ``budget`` counter so a huge font folder can't stall startup."""
    out: list[Path] = []
    seen: set[str] = set()
    for root in dirs:
        if budget[0] <= 0:
            break
        try:
            if not root.is_dir():
                continue
        except OSError:
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames.sort()
            for name in sorted(filenames):
                if Path(name).suffix.lower() not in FONT_EXTENSIONS:
                    continue
                if budget[0] <= 0:
                    return out
                p = Path(dirpath) / name
                try:
                    real = str(p.resolve())
                except OSError:
                    continue
                if real in seen:
                    continue
                seen.add(real)
                budget[0] -= 1
                out.append(p)
    return out


@dataclass
class Catalogue:
    families: list[FontFamily]
    by_family: dict[str, FontFamily]
    by_style: dict[str, FontStyle]
    # normalised family name → families (bundled, system, standard order)
    by_key: dict[str, list[FontFamily]]

    def public(self) -> list[dict[str, Any]]:
        return [f.public() for f in self.families]

    def family(self, family_id: str) -> FontFamily | None:
        return self.by_family.get(family_id)

    def style(self, style_id: str) -> FontStyle | None:
        return self.by_style.get(style_id)


def name_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def build_catalogue(bundled_dir: Path = FONT_DIR, system_dirs: list[Path] | None = None) -> Catalogue:
    families: list[FontFamily] = []
    budget = [MAX_FONT_FILES]
    sources: list[tuple[Source, list[Path]]] = [
        ("bundled", [bundled_dir]),
        ("system", system_font_dirs() if system_dirs is None else system_dirs),
    ]
    for source, dirs in sources:
        grouped: dict[str, FontFamily] = {}
        for path in _font_files(dirs, budget):
            for face in read_font_faces(path):
                fid = f"{source}:{slug(face.family)}"
                if fid == f"{source}:":
                    continue
                fam = grouped.get(fid)
                if fam is None:
                    fam = grouped[fid] = FontFamily(
                        id=fid, family=face.family, source=source, monospace=face.monospace, serif=face.serif
                    )
                if any(s.weight == face.weight and s.italic == face.italic for s in fam.styles):
                    continue
                fam.styles.append(
                    FontStyle(
                        id=_style_id(source, path, face.index),
                        family_id=fid,
                        weight=face.weight,
                        italic=face.italic,
                        restricted=face.restricted,
                        path=str(path),
                        index=face.index,
                    )
                )
        for fam in sorted(grouped.values(), key=lambda f: f.family.lower()):
            fam.styles.sort(key=lambda s: (s.weight, s.italic))
            families.append(fam)
    families.extend(_standard_families())
    by_key: dict[str, list[FontFamily]] = {}
    for fam in families:
        by_key.setdefault(name_key(fam.family), []).append(fam)
    return Catalogue(
        families=families,
        by_family={f.id: f for f in families},
        by_style={s.id: s for f in families for s in f.styles},
        by_key=by_key,
    )


_lock = threading.Lock()
_cached: Catalogue | None = None


def get_catalogue(*, refresh: bool = False) -> Catalogue:
    """The process-wide catalogue, scanned once and kept in memory."""
    global _cached
    with _lock:
        if _cached is None or refresh:
            _cached = build_catalogue()
        return _cached


def style_bytes(style: FontStyle) -> bytes:
    """Font program of an on-disk face (TTC faces are extracted)."""
    if not style.path:
        raise ValueError("standard fonts have no file")
    return extract_face(Path(style.path), style.index)


# -- PDF font name → catalogue match ---------------------------------------------------
_NAME_WEIGHTS: dict[str, int] = {
    "thin": 100,
    "hairline": 100,
    "extralight": 200,
    "ultralight": 200,
    "light": 300,
    "book": 400,
    "regular": 400,
    "normal": 400,
    "medium": 500,
    "med": 500,
    "semibold": 600,
    "demibold": 600,
    "demi": 600,
    "bold": 700,
    "bd": 700,
    "extrabold": 800,
    "ultrabold": 800,
    "black": 900,
    "heavy": 900,
    "extrablack": 900,
    "ultrablack": 900,
}
_NAME_ITALIC = frozenset({"italic", "oblique", "it", "slanted", "kursiv"})
_NAME_TECH = frozenset({"mt", "ps", "psmt", "tt", "std", "pro", "ot", "lt", "com"})
_NAME_WIDTH = frozenset({"condensed", "cond", "narrow", "expanded", "extended", "compressed", "wide"})
# Multi-word weight tokens written as separate words ("Semi Bold").
_NAME_JOIN = {("semi", "bold"): "semibold", ("extra", "bold"): "extrabold", ("ultra", "bold"): "ultrabold"}
_NAME_JOIN |= {("extra", "light"): "extralight", ("ultra", "light"): "ultralight", ("demi", "bold"): "demibold"}

# Metric-compatible / visually close substitutes, tried in order after an
# exact family match fails.
_ALIASES: dict[str, tuple[str, ...]] = {
    "helvetica": ("helvetica", "arial", "liberationsans", "nimbussans", "arimo"),
    "arial": ("arial", "liberationsans", "arimo", "helvetica"),
    "timesnewroman": ("timesnewroman", "liberationserif", "tinos", "times"),
    "times": ("times", "timesnewroman", "liberationserif", "tinos"),
    "timesroman": ("times", "timesnewroman", "liberationserif", "tinos"),
    "couriernew": ("couriernew", "liberationmono", "cousine", "courier"),
    "courier": ("courier", "couriernew", "liberationmono", "cousine"),
    "calibri": ("calibri", "carlito"),
    "cambria": ("cambria", "caladea"),
    "verdana": ("verdana", "dejavusans"),
    "tahoma": ("tahoma", "dejavusans"),
    "segoeui": ("segoeui", "notosans", "opensans"),
    "georgia": ("georgia", "gelasio", "notoserif"),
}


@dataclass(frozen=True)
class MatchedFont:
    family_id: str
    weight: int
    italic: bool

    def public(self) -> dict[str, Any]:
        return {"family_id": self.family_id, "weight": self.weight, "italic": self.italic}


def strip_subset_prefix(name: str) -> str:
    return re.sub(r"^[A-Z]{6}\+", "", name or "")


def decompose_font_name(name: str) -> tuple[str, str, int | None, bool]:
    """``"ABCDEF+Arial-BoldItalicMT"`` → ``("Arial", "Arial", 700, True)``:
    (family with width words, family stem, weight or None, italic)."""
    raw = strip_subset_prefix(name).strip()
    raw = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw)
    raw = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", raw)
    raw = re.sub(r"[_\-,+.]+", " ", raw)
    tokens = [t for t in raw.split() if t]
    merged: list[str] = []
    i = 0
    while i < len(tokens):
        pair = (tokens[i].lower(), tokens[i + 1].lower()) if i + 1 < len(tokens) else None
        if pair in _NAME_JOIN:
            merged.append(_NAME_JOIN[pair])
            i += 2
            continue
        merged.append(tokens[i])
        i += 1
    weight: int | None = None
    italic = False
    full: list[str] = []
    stem: list[str] = []
    for tok in merged:
        low = tok.lower()
        if low in _NAME_WEIGHTS:
            w = _NAME_WEIGHTS[low]
            if weight is None or abs(w - 400) > abs(weight - 400):
                weight = w
            continue
        if low in _NAME_ITALIC:
            italic = True
            continue
        if low in _NAME_TECH:
            continue
        # Glued suffixes: "BoldItalic", "BoldOblique", "SemiboldItalic"
        m = re.fullmatch(r"([a-z]+?)(italic|oblique)", low)
        if m and m.group(1) in _NAME_WEIGHTS:
            w = _NAME_WEIGHTS[m.group(1)]
            weight = w if weight is None else weight
            italic = True
            continue
        full.append(tok)
        if low not in _NAME_WIDTH:
            stem.append(tok)
    return " ".join(full), " ".join(stem), weight, italic


def _usable(fam: FontFamily) -> bool:
    return any(not s.restricted for s in fam.styles)


def match_pdf_font(
    name: str,
    *,
    catalogue: Catalogue | None = None,
    bold: bool = False,
    italic: bool = False,
    serif: bool | None = None,
    mono: bool | None = None,
) -> MatchedFont:
    """Best catalogue family for a PDF font name (+ span flags as hints).

    Order: exact family name → known substitutes → the base-14 family with
    the right look (mono → Courier, serif → Times, else Helvetica).
    Restricted-licence families are skipped — they can't be embedded.
    """
    cat = catalogue or get_catalogue()
    full, stem, weight, name_italic = decompose_font_name(name)
    w = weight if weight is not None else (700 if bold else 400)
    it = name_italic or italic

    def found(fid: str) -> MatchedFont:
        return MatchedFont(fid, w, it)

    keys: list[str] = []
    for candidate in (full, stem):
        k = name_key(candidate)
        if k and k not in keys:
            keys.append(k)
    for k in list(keys):
        for alias in _ALIASES.get(k, ()):
            if alias not in keys:
                keys.append(alias)
    for k in keys:
        for fam in cat.by_key.get(k, []):
            if _usable(fam):
                return found(fam.id)
    low = stem.lower()
    is_mono = mono if mono is not None else _guess_mono(low)
    is_serif = serif if serif is not None else _guess_serif(low)
    if is_mono or _guess_mono(low):
        return found("standard:courier")
    if is_serif:
        return found("standard:times")
    return found("standard:helvetica")
