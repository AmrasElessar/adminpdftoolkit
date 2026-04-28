"""Download the PDF Editor assets — pdf.js viewer + Noto / DejaVu font pack.

Run once at project setup or before building the portable bundle::

    python scripts/setup_editor_assets.py

Assets are written under ``static/pdfjs/`` (pdf.js library) and
``static/fonts/`` (Noto + DejaVu TTFs). Both directories are git-ignored;
the portable build script copies them as part of the dist bundle.

Sources (all OFL / Apache-2.0 / public CDN, no auth required):

- pdf.js: GitHub releases — https://github.com/mozilla/pdf.js/releases
- Noto Sans/Serif/Mono: Google's official notofonts.github.io repo
- DejaVu (already-shipped fallback): jsDelivr CDN

The script is idempotent: existing files are not re-downloaded unless
``--force`` is passed.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Force UTF-8 stdout/stderr so progress arrows render on Windows cp1254 consoles.
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
PDFJS_DIR = STATIC / "pdfjs"
FONTS_DIR = STATIC / "fonts"

# pdf.js — pin a specific release for reproducibility
PDFJS_VERSION = "4.10.38"
PDFJS_BASE = (
    f"https://cdn.jsdelivr.net/npm/pdfjs-dist@{PDFJS_VERSION}/legacy/build"
)
PDFJS_FILES = [
    ("pdf.min.mjs", f"{PDFJS_BASE}/pdf.min.mjs"),
    ("pdf.worker.min.mjs", f"{PDFJS_BASE}/pdf.worker.min.mjs"),
]

# Notofonts CDN — direct TTF files
NOTO_BASE = "https://cdn.jsdelivr.net/gh/notofonts/notofonts.github.io@main/fonts"
NOTO_FILES = [
    # Noto Sans (Latin + Turkish glyphs, primary UI font)
    ("NotoSans-Regular.ttf",     f"{NOTO_BASE}/NotoSans/hinted/ttf/NotoSans-Regular.ttf"),
    ("NotoSans-Bold.ttf",        f"{NOTO_BASE}/NotoSans/hinted/ttf/NotoSans-Bold.ttf"),
    ("NotoSans-Italic.ttf",      f"{NOTO_BASE}/NotoSans/hinted/ttf/NotoSans-Italic.ttf"),
    ("NotoSans-BoldItalic.ttf",  f"{NOTO_BASE}/NotoSans/hinted/ttf/NotoSans-BoldItalic.ttf"),
    # Noto Serif (Times / Garamond replacement)
    ("NotoSerif-Regular.ttf",    f"{NOTO_BASE}/NotoSerif/hinted/ttf/NotoSerif-Regular.ttf"),
    ("NotoSerif-Bold.ttf",       f"{NOTO_BASE}/NotoSerif/hinted/ttf/NotoSerif-Bold.ttf"),
    ("NotoSerif-Italic.ttf",     f"{NOTO_BASE}/NotoSerif/hinted/ttf/NotoSerif-Italic.ttf"),
    ("NotoSerif-BoldItalic.ttf", f"{NOTO_BASE}/NotoSerif/hinted/ttf/NotoSerif-BoldItalic.ttf"),
    # Noto Sans Mono (Courier replacement)
    ("NotoSansMono-Regular.ttf", f"{NOTO_BASE}/NotoSansMono/hinted/ttf/NotoSansMono-Regular.ttf"),
    ("NotoSansMono-Bold.ttf",    f"{NOTO_BASE}/NotoSansMono/hinted/ttf/NotoSansMono-Bold.ttf"),
]

DEJAVU_BASE = "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf"
DEJAVU_FILES = [
    ("DejaVuSans.ttf",        f"{DEJAVU_BASE}/DejaVuSans.ttf"),
    ("DejaVuSans-Bold.ttf",   f"{DEJAVU_BASE}/DejaVuSans-Bold.ttf"),
    ("DejaVuSerif.ttf",       f"{DEJAVU_BASE}/DejaVuSerif.ttf"),
    ("DejaVuSansMono.ttf",    f"{DEJAVU_BASE}/DejaVuSansMono.ttf"),
]


def fetch(url: str, dest: Path, force: bool) -> bool:
    """Download ``url`` to ``dest``. Returns True on download, False on skip."""
    if dest.exists() and not force:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  ↓ {url}")
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "ht-pdf-editor-setup/1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 — https only
            data = resp.read()
        dest.write_bytes(data)
        size_kb = len(data) / 1024
        sha = hashlib.sha256(data).hexdigest()[:8]
        print(f"     → {dest.relative_to(ROOT)}  ({size_kb:.0f} KB, sha256:{sha})")
        return True
    except urllib.error.URLError as e:
        print(f"     ✗ {e}", file=sys.stderr)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Download PDF editor assets.")
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if files exist.")
    parser.add_argument("--pdfjs-only", action="store_true")
    parser.add_argument("--fonts-only", action="store_true")
    args = parser.parse_args()

    do_pdfjs = not args.fonts_only
    do_fonts = not args.pdfjs_only

    if do_pdfjs:
        print(f"[pdf.js] downloading v{PDFJS_VERSION} → {PDFJS_DIR.relative_to(ROOT)}/")
        PDFJS_DIR.mkdir(parents=True, exist_ok=True)
        for name, url in PDFJS_FILES:
            try:
                fetch(url, PDFJS_DIR / name, args.force)
            except urllib.error.URLError:
                print("[pdf.js] download failed — see error above.", file=sys.stderr)
                return 2
        # Write a small VERSION file so downstream scripts know what's installed
        (PDFJS_DIR / "VERSION").write_text(PDFJS_VERSION + "\n", encoding="utf-8")

    if do_fonts:
        print(f"\n[fonts] downloading Noto + DejaVu → {FONTS_DIR.relative_to(ROOT)}/")
        FONTS_DIR.mkdir(parents=True, exist_ok=True)
        for name, url in NOTO_FILES + DEJAVU_FILES:
            try:
                fetch(url, FONTS_DIR / name, args.force)
            except urllib.error.URLError:
                print(f"[fonts] {name} failed — continuing.", file=sys.stderr)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
