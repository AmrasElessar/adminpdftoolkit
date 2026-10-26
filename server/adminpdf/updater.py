"""``python -m adminpdf.updater`` — check for and fetch a new Windows package.

    check              → one JSON line: is a newer release out, and can it be
                         installed automatically (signed)?
    download --dest D  → fetch, verify and unpack it into D, printing progress
                         lines; the launcher swaps the files in afterwards.

Trust: every release publishes ``SHA256SUMS`` and ``SHA256SUMS.sig``, an
Ed25519 signature made in the release workflow with a key only that
workflow holds. The matching public key is built into this file. A package
is installed only if the signature verifies *and* the zip's SHA-256 matches
the signed list — a hijacked download, mirror or proxy cannot slip in
anything else. Without a configured key, updates are announced but never
installed automatically.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from .config import VERSION

REPO = "AmrasElessar/adminpdftoolkit"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
ASSET_RE = re.compile(r"^AdminPDFToolkit-(?P<version>[0-9][0-9A-Za-z.\-]*)-Windows\.zip$")
# The package this system downloads: only the Windows one is replaced in
# place by the launcher; on macOS / Linux the new release is announced.
PLATFORM_ASSETS = {
    "win32": ASSET_RE,
    "darwin": re.compile(r"^AdminPDFToolkit-(?P<version>[0-9][0-9A-Za-z.\-]*)-macOS-arm64\.zip$"),
    "linux": re.compile(r"^AdminPDFToolkit-(?P<version>[0-9][0-9A-Za-z.\-]*)-Linux-x86_64\.tar\.gz$"),
}


def platform_asset() -> re.Pattern[str]:
    key = "linux" if sys.platform.startswith("linux") else sys.platform
    return PLATFORM_ASSETS.get(key, ASSET_RE)


# Ed25519 public key of the release workflow (base64, 32 bytes), set when
# signing is configured (see scripts/release_signing.py). Empty = no
# automatic installs.
RELEASE_PUBLIC_KEY = "tB7ypO8z1pL9qb/CewmPox4suNoDHDxChX/aOoZ8fAc="
TIMEOUT = 8
MAX_PACKAGE_BYTES = 2 * 1024**3


class UpdateError(Exception):
    pass


def parse_version(text: str) -> tuple[int, ...]:
    """``"v2.10.1"`` → ``(2, 10, 1)``; pre-release suffixes sort lowest."""
    parts = re.findall(r"\d+", text.split("-", 1)[0])
    return tuple(int(p) for p in parts[:4]) or (0,)


def _get(url: str, timeout: float = TIMEOUT) -> bytes:
    if not url.startswith("https://"):
        raise UpdateError(f"refusing non-HTTPS URL: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": f"AdminPDFToolkit/{VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data: bytes = r.read(16 * 1024 * 1024)
    return data


def verify_sums(sums: bytes, signature: bytes, public_key: str = "") -> dict[str, str]:
    """Check the Ed25519 signature of a ``SHA256SUMS`` file and parse it into
    ``{file name: sha256}``. Raises :class:`UpdateError` on any doubt."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    key_b64 = public_key or RELEASE_PUBLIC_KEY
    if not key_b64:
        raise UpdateError("no release signing key is configured")
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(key_b64))
        key.verify(base64.b64decode(signature.strip()), sums)
    except (InvalidSignature, ValueError) as e:
        raise UpdateError("the release signature does not verify") from e
    out: dict[str, str] = {}
    for line in sums.decode("utf-8").splitlines():
        m = re.fullmatch(r"([0-9a-f]{64})\s+\*?(\S+)", line.strip())
        if m:
            out[m.group(2)] = m.group(1)
    return out


def latest_release() -> dict[str, Any]:
    """The newest release's Windows package and signature files."""
    release = json.loads(_get(API))
    assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
    pattern = platform_asset()
    package = next((n for n in assets if pattern.match(n)), None)
    manifest: dict[str, Any] = {}
    if "release-manifest.json" in assets:
        try:
            manifest = json.loads(_get(assets["release-manifest.json"]))
        except (OSError, ValueError):
            manifest = {}
    return {
        "tag": str(release.get("tag_name", "")),
        "page": str(release.get("html_url", RELEASES_PAGE)),
        "package": package,
        "package_url": assets.get(package or ""),
        "sums_url": assets.get("SHA256SUMS"),
        "sig_url": assets.get("SHA256SUMS.sig"),
        "components": manifest.get("components", {}),
    }


def check(current: str = VERSION) -> dict[str, Any]:
    try:
        rel = latest_release()
    except (OSError, ValueError) as e:
        return {"type": "update", "ok": False, "current": current, "error": str(e)[:200]}
    latest = rel["tag"].lstrip("v")
    available = bool(rel["package"]) and parse_version(latest) > parse_version(current)
    installable = (
        available and sys.platform == "win32" and bool(RELEASE_PUBLIC_KEY and rel["sums_url"] and rel["sig_url"])
    )
    return {
        "type": "update",
        "ok": True,
        "current": current,
        "latest": latest,
        "available": available,
        "installable": installable,
        "page": rel["page"],
        "components": rel["components"],
    }


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    """Unzip without letting a crafted entry escape ``dest`` (zip-slip)."""
    root = dest.resolve()
    for info in zf.infolist():
        name = PurePosixPath(info.filename)
        if name.is_absolute() or ".." in name.parts or ":" in info.filename:
            raise UpdateError(f"unsafe path in package: {info.filename}")
        target = (root / Path(*name.parts)).resolve()
        if not target.is_relative_to(root):
            raise UpdateError(f"unsafe path in package: {info.filename}")
    zf.extractall(root)


def download(dest: Path, progress: Callable[[float], None] = lambda _f: None) -> Path:
    """Fetch, verify and unpack the newest package into ``dest``; returns
    the folder holding the new files (``dest/AdminPDFToolkit``)."""
    rel = latest_release()
    if not (rel["package_url"] and rel["sums_url"] and rel["sig_url"]):
        raise UpdateError("the release has no signed package")
    m = ASSET_RE.match(rel["package"] or "")
    # Never downgrade: an old but genuinely signed release replayed as
    # "latest" (e.g. by a proxy) must not be installed.
    if not m or parse_version(m.group("version")) <= parse_version(VERSION):
        raise UpdateError("the offered package is not newer than this version")
    sums = verify_sums(_get(rel["sums_url"]), _get(rel["sig_url"]))
    expected = sums.get(rel["package"])
    if not expected:
        raise UpdateError("the package is not in the signed list")
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    with tempfile.TemporaryDirectory(dir=dest) as tmp:
        zip_path = Path(tmp) / "package.zip"
        h = hashlib.sha256()
        req = urllib.request.Request(rel["package_url"], headers={"User-Agent": f"AdminPDFToolkit/{VERSION}"})
        with urllib.request.urlopen(req, timeout=60) as r, zip_path.open("wb") as fh:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while block := r.read(1 << 20):
                done += len(block)
                if done > MAX_PACKAGE_BYTES:
                    raise UpdateError("the package is unexpectedly large")
                h.update(block)
                fh.write(block)
                if total:
                    progress(min(0.95, done / total))
        if h.hexdigest() != expected:
            raise UpdateError("the downloaded package does not match its signed SHA-256")
        with zipfile.ZipFile(zip_path) as zf:
            _safe_extract(zf, dest)
    staged = dest / "AdminPDFToolkit"
    if not (staged / "python").is_dir() or not (staged / "AdminPDFToolkit.exe").is_file():
        raise UpdateError("the package does not look like an Admin PDF Toolkit package")
    progress(1.0)
    return staged


def main() -> None:
    parser = argparse.ArgumentParser(prog="adminpdf.updater")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    dl = sub.add_parser("download")
    dl.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args()

    def emit(obj: dict[str, Any]) -> None:
        print(json.dumps(obj), flush=True)

    if args.cmd == "check":
        emit(check())
        return
    try:
        staged = download(args.dest, lambda f: emit({"type": "progress", "fraction": round(f, 3)}))
    except (UpdateError, OSError, zipfile.BadZipFile) as e:
        emit({"type": "error", "message": str(e)[:300]})
        sys.exit(1)
    emit({"type": "staged", "path": str(staged)})


if __name__ == "__main__":
    main()
