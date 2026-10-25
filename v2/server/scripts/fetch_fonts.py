#!/usr/bin/env python3
"""Download the bundled editor fonts (SIL OFL / Bitstream-Vera-style free
licences, full Turkish coverage) into ``adminpdf/assets/fonts/``.

Run once at install/packaging time — the server itself never touches the
network. Every file is checked against a SHA-256 pin in ``fonts.lock.json``
(next to this script):

* pinned and matching   → installed
* pinned and different  → rejected (upstream changed or tampering)
* not pinned yet        → rejected, unless ``--update-pins`` is given; then
  the hash is recorded (trust on first use — review and commit the lock file)

Usage::

    python scripts/fetch_fonts.py                # install / verify
    python scripts/fetch_fonts.py --update-pins  # record hashes for new entries
    python scripts/fetch_fonts.py --list         # show the manifest

Binaries are not committed; ``assets/fonts/.gitignore`` ignores them.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "adminpdf" / "assets" / "fonts"
LOCK = Path(__file__).resolve().parent / "fonts.lock.json"
MAX_DOWNLOAD = 64 * 1024 * 1024
TIMEOUT = 60


@dataclass(frozen=True)
class Source:
    """One downloadable file; ``member`` names a file inside an archive."""

    url: str
    files: tuple[tuple[str, str], ...]  # (local name, archive member or "")


# DejaVu and Liberation URLs are version-pinned. Noto has no versioned
# single-file host, so it comes from a git ref of the official notofonts site;
# set NOTO_REF to a commit SHA for full reproducibility — either way the
# SHA-256 pins reject any file that changed upstream.
NOTO_REF = "main"
NOTO = f"https://cdn.jsdelivr.net/gh/notofonts/notofonts.github.io@{NOTO_REF}/fonts"
DEJAVU = "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf"
LIBERATION = "https://github.com/liberationfonts/liberation-fonts/files/7261482/liberation-fonts-ttf-2.1.5.tar.gz"


def _noto(family: str, styles: tuple[str, ...]) -> list[Source]:
    return [Source(f"{NOTO}/{family}/hinted/ttf/{family}-{s}.ttf", ((f"{family}-{s}.ttf", ""),)) for s in styles]


def _dejavu(names: tuple[str, ...]) -> list[Source]:
    return [Source(f"{DEJAVU}/{n}.ttf", ((f"{n}.ttf", ""),)) for n in names]


FOUR = ("Regular", "Bold", "Italic", "BoldItalic")
MANIFEST: list[Source] = [
    *_noto("NotoSans", FOUR),
    *_noto("NotoSerif", FOUR),
    *_noto("NotoSansMono", ("Regular", "Bold")),
    *_dejavu(
        (
            "DejaVuSans",
            "DejaVuSans-Bold",
            "DejaVuSans-Oblique",
            "DejaVuSans-BoldOblique",
            "DejaVuSerif",
            "DejaVuSerif-Bold",
            "DejaVuSerif-Italic",
            "DejaVuSerif-BoldItalic",
            "DejaVuSansMono",
            "DejaVuSansMono-Bold",
            "DejaVuSansMono-Oblique",
            "DejaVuSansMono-BoldOblique",
        )
    ),
    # Metric-compatible with Arial / Times New Roman / Courier New — the best
    # stand-ins when replacing text set in those fonts.
    Source(
        LIBERATION,
        tuple(
            (f"{fam}-{style}.ttf", f"liberation-fonts-ttf-2.1.5/{fam}-{style}.ttf")
            for fam in ("LiberationSans", "LiberationSerif", "LiberationMono")
            for style in ("Regular", "Bold", "Italic", "BoldItalic")
        ),
    ),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "adminpdf-fetch-fonts/1"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # fixed https URLs only
        data: bytes = resp.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise RuntimeError("download too large")
    return data


def members(src: Source, blob: bytes) -> dict[str, bytes]:
    """``{local name: bytes}``; archive members are read by exact name only
    (never extracted to paths taken from the archive)."""
    if all(not m for _n, m in src.files):
        return {src.files[0][0]: blob}
    out: dict[str, bytes] = {}
    if src.url.endswith((".tar.gz", ".tgz")):
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
            for name, member in src.files:
                f = tar.extractfile(member)
                if f is None:
                    raise RuntimeError(f"{member} missing from archive")
                out[name] = f.read(MAX_DOWNLOAD)
    else:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            for name, member in src.files:
                out[name] = z.read(member)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update-pins", action="store_true", help="record SHA-256 of files that have no pin yet")
    ap.add_argument("--list", action="store_true", help="print the manifest and exit")
    args = ap.parse_args(argv)
    if args.list:
        for src in MANIFEST:
            for name, _m in src.files:
                print(f"{name:34} {src.url}")
        return 0
    pins: dict[str, str] = json.loads(LOCK.read_text("utf-8")) if LOCK.is_file() else {}
    DEST.mkdir(parents=True, exist_ok=True)
    failures = 0
    changed = False
    for src in MANIFEST:
        wanted = [n for n, _m in src.files]
        if all((DEST / n).is_file() and pins.get(n) == sha256((DEST / n).read_bytes()) for n in wanted):
            print(f"ok       {', '.join(wanted)}")
            continue
        try:
            files = members(src, download(src.url))
        except Exception as e:  # network, archive, HTTP errors
            print(f"FAILED   {src.url}: {e}", file=sys.stderr)
            failures += len(wanted)
            continue
        for name, data in files.items():
            digest = sha256(data)
            pin = pins.get(name)
            if pin is None and not args.update_pins:
                print(f"UNPINNED {name} sha256={digest} (re-run with --update-pins to accept)", file=sys.stderr)
                failures += 1
                continue
            if pin is not None and pin != digest:
                print(f"MISMATCH {name}: expected {pin}, got {digest}", file=sys.stderr)
                failures += 1
                continue
            if pin is None:
                pins[name] = digest
                changed = True
            (DEST / name).write_bytes(data)
            print(f"saved    {name} ({len(data) // 1024} KB)")
    if changed:
        LOCK.write_text(json.dumps(dict(sorted(pins.items())), indent=2) + "\n", "utf-8")
        print(f"pins written to {LOCK.name} — review and commit it")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
