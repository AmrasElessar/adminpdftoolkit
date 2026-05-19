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
    _FONTS_DIR,
    EDITOR_FONT_FAMILIES,
)
from .editor import (
    resolve_editor_font as _resolve_editor_font_bundled,
)

_SYSTEM_FONT_CACHE: list[dict[str, Any]] | None = None


# ----- Weight axis (CSS-uyumlu 100-900 ekseni) ----------------------------
# Frontend ve PDF embed her ikisi de bu isimleri kullanır. CSS karşılığı:
# thin=100, extralight=200, light=300, regular=400, medium=500,
# semibold=600, bold=700, extrabold=800, black=900.
WEIGHT_AXIS = (
    "thin", "extralight", "light", "regular", "medium",
    "semibold", "bold", "extrabold", "black",
)
_WEIGHT_CSS = {
    "thin": 100, "extralight": 200, "light": 300, "regular": 400,
    "medium": 500, "semibold": 600, "bold": 700, "extrabold": 800,
    "black": 900,
}

# Subfamily / font-name token'larından weight tahmini.
# Sıralama önemli: daha spesifik (extrabold) önce gelmeli, "bold" sonra.
_WEIGHT_TOKEN_ORDER: tuple[tuple[tuple[str, ...], str], ...] = (
    (("extrablack", "ultrablack"), "black"),
    (("extrabold", "ultrabold"), "extrabold"),
    (("semibold", "demibold"), "semibold"),
    (("extralight", "ultralight"), "extralight"),
    (("hairline",), "thin"),
    (("black", "heavy"), "black"),
    (("bold", "bd", "blk"), "bold"),
    (("demi",), "semibold"),
    (("medium", "med"), "medium"),
    (("light",), "light"),
    (("thin",), "thin"),
    (("regular", "normal", "roman", "book"), "regular"),
)


def classify_weight_from_text(text: str) -> tuple[str, bool]:
    """Parse a subfamily/font-name string → ``(weight, italic)``.

    ``weight`` ∈ :data:`WEIGHT_AXIS`. Italic detected from ``italic``,
    ``oblique`` ya da ``slant`` token'larından. Token bulunamazsa
    ``("regular", False)`` döner.
    """
    src = (text or "").lower()
    if not src:
        return ("regular", False)
    # Tüm boşluk/tire/underscore'ları kaldır — "Semi Bold", "Semi-Bold",
    # "SemiBold" hepsi "semibold"a normalize olsun
    norm = re.sub(r"[\s\-_]+", "", src)
    italic = ("italic" in norm) or ("oblique" in norm) or ("slant" in norm)
    weight = "regular"
    for tokens, w in _WEIGHT_TOKEN_ORDER:
        if any(t in norm for t in tokens):
            weight = w
            break
    return (weight, italic)


def weight_css(weight: str) -> int:
    """CSS font-weight değeri (100..900). Bilinmeyen weight → 400."""
    return _WEIGHT_CSS.get((weight or "regular").lower(), 400)


# Komşu weight'ler — istenen variant yüklü değilse en yakına düşer
_WEIGHT_NEIGHBORS: dict[str, tuple[str, ...]] = {
    "thin": ("extralight", "light", "regular"),
    "extralight": ("thin", "light", "regular"),
    "light": ("extralight", "regular", "medium"),
    "regular": ("medium", "light", "book"),
    "medium": ("semibold", "regular", "bold"),
    "semibold": ("bold", "medium", "extrabold"),
    "bold": ("extrabold", "semibold", "black", "medium"),
    "extrabold": ("black", "bold", "semibold"),
    "black": ("extrabold", "bold", "semibold"),
}


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
    ``OS/2`` tables via ``seek``/``read``, so font size is irrelevant
    (Times/Tahoma/Arial all keep their name table near the file end). Returns
    ``None`` if the file isn't a recognisable OpenType / TrueType single-font
    container (skips ``.ttc`` collections).
    """
    try:
        with open(path, "rb") as f:
            header = f.read(12)
            if len(header) < 12:
                return None
            sig = header[:4]
            if sig not in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1"):
                return None
            try:
                num_tables = _struct.unpack(">H", header[4:6])[0]
            except _struct.error:
                return None
            if num_tables == 0 or num_tables > 256:
                return None
            directory = f.read(num_tables * 16)
            if len(directory) < num_tables * 16:
                return None
            tables: dict[bytes, tuple[int, int]] = {}
            for i in range(num_tables):
                rec = directory[i * 16 : (i + 1) * 16]
                tag = rec[:4]
                offset = _struct.unpack(">I", rec[8:12])[0]
                length = _struct.unpack(">I", rec[12:16])[0]
                tables[tag] = (offset, length)

            if b"name" not in tables:
                return None
            name_off, name_len = tables[b"name"]
            # name table'lar pratikte 50 KB altında; defansif olarak 1 MB cap'le
            name_len_capped = min(name_len, 1024 * 1024)
            f.seek(name_off)
            name_data = f.read(name_len_capped)
            if len(name_data) < 6:
                return None

            fs_type = 0
            if b"OS/2" in tables:
                os2_off, _os2_len = tables[b"OS/2"]
                # fsType OS/2 başlığından 8 byte sonra (2 byte)
                f.seek(os2_off + 8)
                fs_bytes = f.read(2)
                if len(fs_bytes) == 2:
                    try:
                        fs_type = _struct.unpack(">H", fs_bytes)[0]
                    except _struct.error:
                        fs_type = 0
    except OSError:
        return None

    try:
        _format = _struct.unpack(">H", name_data[0:2])[0]
        count = _struct.unpack(">H", name_data[2:4])[0]
        string_offset = _struct.unpack(">H", name_data[4:6])[0]
    except _struct.error:
        return None

    family = subfamily = pref_family = pref_subfamily = None
    for i in range(count):
        rec = 6 + i * 12
        if rec + 12 > len(name_data):
            break
        try:
            platform = _struct.unpack(">H", name_data[rec : rec + 2])[0]
            encoding = _struct.unpack(">H", name_data[rec + 2 : rec + 4])[0]
            _lang = _struct.unpack(">H", name_data[rec + 4 : rec + 6])[0]
            name_id = _struct.unpack(">H", name_data[rec + 6 : rec + 8])[0]
            length = _struct.unpack(">H", name_data[rec + 8 : rec + 10])[0]
            str_off = _struct.unpack(">H", name_data[rec + 10 : rec + 12])[0]
        except _struct.error:
            continue
        start = string_offset + str_off
        end = start + length
        if end > len(name_data):
            continue
        raw = name_data[start:end]
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
                if not meta:
                    continue
                fam = meta["family"]
                key = re.sub(r"[^a-z0-9]+", "-", fam.lower()).strip("-")
                if not key:
                    continue
                # Subfamily'den granular weight tespiti (Light/Semibold/Black…)
                # Eğer subfamily explicit weight içermiyorsa, meta'daki bool
                # bold flag'ini base alır.
                weight, italic_explicit = classify_weight_from_text(meta.get("subfamily", ""))
                italic = italic_explicit or bool(meta.get("italic"))
                if weight == "regular" and meta.get("bold"):
                    weight = "bold"
                entry = families.setdefault(
                    key,
                    {
                        "id": f"system:{key}",
                        "label": fam,
                        "category": "system",
                        # Yeni: zengin variant listesi
                        "weight_variants": [],   # [{weight, italic, file}]
                        # Legacy: 4-noktalı boolean variantlar (backward compat)
                        "variants": [],          # ["regular","bold",...]
                        "files": {},             # {"regular": path, ...}
                        # fsType bit 1 (Restricted Embed) — kullanıcının PC'sindeki
                        # lisanslı fontu listede tutuyoruz; UI 🔒 rozetiyle uyarıyor.
                        "embeddable": True,
                    },
                )
                # Yeni rich variant — aynı (weight, italic) için ilk dosya kazansın
                if not any(
                    v["weight"] == weight and v["italic"] == italic
                    for v in entry["weight_variants"]
                ):
                    entry["weight_variants"].append({
                        "weight": weight,
                        "italic": italic,
                        "file": str(path),
                    })
                # Legacy 4-noktalı slot (regular/bold/italic/bolditalic)
                is_bold_legacy = weight in {"bold", "extrabold", "black"}
                if is_bold_legacy and italic:
                    legacy = "bolditalic"
                elif is_bold_legacy:
                    legacy = "bold"
                elif italic:
                    legacy = "italic"
                else:
                    legacy = "regular"
                if legacy not in entry["files"]:
                    entry["files"][legacy] = str(path)
                    entry["variants"].append(legacy)
                # Aile için "embeddable" en kısıtlı varyantın değerine düşer
                if not meta.get("embeddable"):
                    entry["embeddable"] = False
        except OSError:
            continue

    # En az bir varyantı olan aileleri tut + her birinin weight_variants'ını
    # CSS weight değerine göre sırala (ince → kalın), aynı weight içinde
    # roman → italik sırası
    result = []
    for f in families.values():
        if not f["weight_variants"]:
            continue
        f["weight_variants"].sort(key=lambda v: (weight_css(v["weight"]), v["italic"]))
        result.append(f)
    result.sort(key=lambda f: f["label"].lower())
    _SYSTEM_FONT_CACHE = result
    return result


def resolve_system_font(
    family_id: str,
    *,
    weight: str | None = None,
    bold: bool = False,
    italic: bool = False,
) -> Path | None:
    """Resolve ``"system:arial"`` + weight/italic → on-disk path.

    ``weight`` (``"light"``/``"medium"``/``"semibold"``/``"bold"``/…) verilirse
    önce tam ``(weight, italic)`` kombinasyonu aranır; bulunmazsa komşu weight'
    lere düşülür. Geriye-uyumluluk için ``bold=True`` verilirse ``weight``
    yokken ``"bold"`` varsayılır.
    """
    if not family_id.startswith("system:"):
        return None
    key = family_id.split(":", 1)[1]
    if weight is None:
        weight = "bold" if bold else "regular"
    weight = (weight or "regular").lower()
    for entry in discover_system_fonts():
        if (
            entry["id"] != family_id
            and re.sub(r"[^a-z0-9]+", "-", entry["label"].lower()).strip("-") != key
        ):
            continue
        variants = entry.get("weight_variants") or []
        # 1) Tam eşleşme (weight + italic)
        for v in variants:
            if v["weight"] == weight and v["italic"] == italic:
                p = Path(v["file"])
                if p.is_file():
                    return p
        # 2) Aynı weight, italic karşıtı
        for v in variants:
            if v["weight"] == weight:
                p = Path(v["file"])
                if p.is_file():
                    return p
        # 3) Komşu weight'lere düş (önce aynı italic'i deneyerek)
        for neighbor in _WEIGHT_NEIGHBORS.get(weight, ()):
            for v in variants:
                if v["weight"] == neighbor and v["italic"] == italic:
                    p = Path(v["file"])
                    if p.is_file():
                        return p
            for v in variants:
                if v["weight"] == neighbor:
                    p = Path(v["file"])
                    if p.is_file():
                        return p
        # 4) Son çare: regular ya da herhangi bir variant
        for prefer in ("regular", "medium", "bold"):
            for v in variants:
                if v["weight"] == prefer:
                    p = Path(v["file"])
                    if p.is_file():
                        return p
        for v in variants:
            p = Path(v["file"])
            if p.is_file():
                return p
    return None


def resolve_editor_font_with_system(
    family_id: str,
    *,
    weight: str | None = None,
    bold: bool = False,
    italic: bool = False,
) -> Path | None:
    """Like ``resolve_editor_font`` but also handles ``system:*`` ids and
    granular CSS-style ``weight`` values (``"semibold"``, ``"light"``…).

    Bundled fontlar yalnızca 4-noktalı (regular/bold/italic/bolditalic)
    varyant taşıdığı için ``weight`` bundled tarafta ``bold`` boolean'a
    indirgenir (``weight ∈ {bold, extrabold, black}`` → bold).
    """
    if weight is None:
        effective_bold = bold
    else:
        effective_bold = (weight or "regular").lower() in {"bold", "extrabold", "black"}
    if family_id.startswith("system:"):
        sys_path = resolve_system_font(
            family_id, weight=weight, bold=effective_bold, italic=italic
        )
        if sys_path:
            return sys_path
    return _resolve_editor_font_bundled(
        family_id, bold=effective_bold, italic=italic
    )


# ----- PDF font name → (family_id, bold, italic) matcher -------------------
#
# PDF dosyalarındaki font adları kaotiktir: "TimesNewRomanPSMT", "Arial-BoldMT",
# "ABCDEF+Helvetica" (subset prefix), "Courier New Bold Italic", "CalibriLight".
# Bu helper adı parçalara ayırıp:
#   1. Tam normalize edilmiş key ile sistem fontu cache'inde ara
#      ("times-new-roman" → "system:times-new-roman" varsa)
#   2. Width/weight modifier'larını koruyarak da dene
#      ("calibri-light" matches → değilse "calibri"e düşer)
#   3. Bunlardan biri bulunmazsa bundled Noto/DejaVu ailesine keyword fallback.

_STYLE_ITALIC = frozenset({
    "italic", "oblique", "it", "slant", "slanted",
})
# Weight token → ekseni — tek tek mapping (decompose içinde de kullanılır)
_WEIGHT_TOKEN_MAP: dict[str, str] = {
    "thin": "thin", "hairline": "thin",
    "extralight": "extralight", "ultralight": "extralight",
    "light": "light",
    # "roman" KASITLI olarak yok — "Times New Roman" family adının parçası
    # olarak korunuyor. Adobe-style "GaramondPremiere-Roman" durumunda da
    # default weight=regular zaten geçerli; family core korunmuş olur.
    "regular": "regular", "normal": "regular", "book": "regular",
    "medium": "medium", "med": "medium",
    "semibold": "semibold", "demibold": "semibold", "demi": "semibold",
    "bold": "bold", "bd": "bold", "blk": "bold",
    "extrabold": "extrabold", "ultrabold": "extrabold",
    "black": "black", "heavy": "black",
    "extrablack": "black", "ultrablack": "black",
}
# Width modifier'ları — keep_with_mods'a girer ama keep_minimal'dan düşer
# (örn. "Arial Narrow" — full match için "Arial Narrow", fallback için "Arial")
_WIDTH_MODIFIERS = frozenset({
    "condensed", "expanded", "narrow", "wide", "compressed", "extended",
})
# PostScript / OpenType tech suffixes — tamamen at
_TECH_SUFFIX = frozenset({
    "mt", "ps", "psmt", "tt", "bt", "std", "pro", "ot", "cm",
})


def _decompose_pdf_font_name(name: str) -> dict[str, Any]:
    """Parse a raw PDF font name into structured pieces.

    Returns ``{"core_full": str, "core_min": str, "weight": str, "italic": bool}``:
      * ``core_full`` — family + width modifier (Calibri Light → "Calibri Light")
      * ``core_min`` — family stem only (Calibri Light → "Calibri")
      * ``weight`` — :data:`WEIGHT_AXIS` üyesi
      * ``italic`` — bool
    """
    raw = (name or "").strip()
    if not raw:
        return {"core_full": "", "core_min": "", "weight": "regular", "italic": False}
    # PDF subset prefix — 6 büyük harf + "+"
    raw = re.sub(r"^[A-Z]{6}\+", "", raw)
    # camelCase boundaries: insert space
    raw = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw)
    raw = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", raw)
    raw = re.sub(r"[_\-]+", " ", raw)
    tokens = [t for t in raw.split() if t]

    weight = "regular"
    italic = False
    keep_with_mods: list[str] = []
    keep_minimal: list[str] = []
    weight_priority = {w: i for i, w in enumerate(WEIGHT_AXIS)}
    # `weight` aldığımızda en spesifik (en yüksek priority) token kazansın;
    # böylece "BoldItalic" gelirse weight=bold; "ExtraBold" gelirse extrabold.
    weight_score = -1
    for tok in tokens:
        low = tok.lower()
        if low in _WEIGHT_TOKEN_MAP:
            mapped = _WEIGHT_TOKEN_MAP[low]
            # Priority: daha "extreme" (uçtaki) weight kazansın
            score = abs(weight_priority[mapped] - weight_priority["regular"])
            if mapped != "regular" and score > weight_score:
                weight = mapped
                weight_score = score
            continue
        if low in _STYLE_ITALIC:
            italic = True
            continue
        if low in _TECH_SUFFIX:
            continue
        if low in _WIDTH_MODIFIERS:
            keep_with_mods.append(tok)
            continue
        keep_with_mods.append(tok)
        keep_minimal.append(tok)
    return {
        "core_full": " ".join(keep_with_mods),
        "core_min": " ".join(keep_minimal),
        "weight": weight,
        "italic": italic,
    }


def _font_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def match_pdf_font_name(pdf_font_name: str) -> dict[str, Any]:
    """Map a PDF's internal font name → rich match info.

    Returns ``{"family_id": str, "weight": str, "italic": bool, "bold": bool}``
    where ``weight`` is a member of :data:`WEIGHT_AXIS` and ``bold`` is the
    legacy boolean (``weight in {bold, extrabold, black}``) — kept for callers
    that haven't migrated yet.
    """
    decomp = _decompose_pdf_font_name(pdf_font_name)
    weight = decomp["weight"]
    italic = decomp["italic"]
    core_full = decomp["core_full"]
    core_min = decomp["core_min"]
    bold_legacy = weight in {"bold", "extrabold", "black"}

    def _result(family_id: str) -> dict[str, Any]:
        return {
            "family_id": family_id,
            "weight": weight,
            "italic": italic,
            "bold": bold_legacy,
        }

    if not core_min:
        return _result("noto-sans")

    system_map = {f["id"].split(":", 1)[1]: f["id"] for f in discover_system_fonts()}
    for candidate in (core_full, core_min):
        k = _font_key(candidate)
        if k and k in system_map:
            return _result(system_map[k])

    # Bundled keyword fallback
    low = core_min.lower()
    if any(t in low for t in ("mono", "courier", "consolas", "menlo", "fixed", "code")):
        family = "noto-mono"
    elif any(
        t in low
        for t in (
            "times", "serif", "garamond", "georgia", "palatino", "minion",
            "caslon", "baskerville", "didot", "cambria", "antiqua", "century",
            "bookman",
        )
    ):
        family = "noto-serif"
    else:
        family = "noto-sans"
    return _result(family)


def editor_font_catalog_with_system() -> list[dict[str, Any]]:
    """Public catalog: bundled (Noto/DejaVu) first, then host system fonts.

    Her entry hem legacy ``variants`` (``["regular","bold","italic","bolditalic"]``
    boolean slot'ları) hem de zengin ``weight_variants``
    (``[{"weight": "...", "italic": bool}, ...]``) taşır. Frontend, weight
    dropdown'unu doldururken ``weight_variants``'tan benzersiz weight'leri
    çıkartır.
    """
    bundled: list[dict[str, Any]] = []
    for fam in EDITOR_FONT_FAMILIES:
        legacy_present: list[str] = []
        rich: list[dict[str, Any]] = []
        for variant_key, filename in fam["variants"].items():
            if not (_FONTS_DIR / filename).is_file():
                continue
            legacy_present.append(variant_key)
            # Bundled 4-noktalı şema → weight axis
            is_bold = "bold" in variant_key
            is_italic = "italic" in variant_key
            rich.append({
                "weight": "bold" if is_bold else "regular",
                "italic": is_italic,
            })
        if not legacy_present:
            continue
        bundled.append({
            "id": fam["id"],
            "label": fam["label"],
            "category": fam.get("category") or "bundled",
            "variants": legacy_present,
            "weight_variants": rich,
            "source": "bundled",
        })
    sys_fonts: list[dict[str, Any]] = []
    for f in discover_system_fonts():
        sys_fonts.append({
            "id": f["id"],
            "label": f["label"],
            "category": f["category"],
            "variants": f["variants"],
            "weight_variants": [
                {"weight": v["weight"], "italic": v["italic"]}
                for v in f.get("weight_variants", [])
            ],
            "source": "system",
            "embeddable": f.get("embeddable", True),
        })
    return bundled + sys_fonts
