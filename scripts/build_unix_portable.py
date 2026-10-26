r"""Build the self-contained Linux and macOS packages (no Python install needed).

Run on the target system after building the web UI (CI: ubuntu-22.04 for
Linux x86_64, macos-latest for Apple Silicon):

    cd web && npm ci && npm run build && cd ..
    python scripts/build_unix_portable.py
      → dist/AdminPDFToolkit-<version>-Linux-x86_64.tar.gz
      → dist/AdminPDFToolkit-<version>-macOS-arm64.zip  (AdminPDFToolkit.app)

Python comes from python-build-standalone (relocatable CPython builds, the
same ones uv and others ship), checked against the SHA-256 GitHub publishes
for the release asset. The app starts the Tk launcher (adminpdf.launcher):
component checklist, server without a terminal, network sharing, update
notice.

macOS: the app is ad-hoc signed (free; Apple Silicon requires a valid
signature) but not notarised, which needs a paid Apple account. On first
start macOS asks once: System Settings ▸ Privacy & Security ▸ Open Anyway.

OCR (Tesseract) and Ghostscript are not bundled here — their Unix builds
are not relocatable; the launcher shows the brew / apt command when missing.
"""

from __future__ import annotations

import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from build_package import DOCS, ROOT, version  # sibling scripts (scripts/ is on sys.path)
from build_windows_portable import _api, fetch

DIST = ROOT / "dist"
TOP = "AdminPDFToolkit"
PYTHON_MINOR = "3.13"
PBS_REPO = "astral-sh/python-build-standalone"
TRIPLES = {
    ("linux", "x86_64"): "x86_64-unknown-linux-gnu",
    ("darwin", "arm64"): "aarch64-apple-darwin",
    ("darwin", "x86_64"): "x86_64-apple-darwin",
}
ICON = ROOT / "server" / "adminpdf" / "assets" / "icon.png"

LINUX_START = """#!/bin/sh
# Admin PDF Toolkit — starts the launcher window (no terminal needed).
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/python/bin/python3" -m adminpdf.launcher "$@"
"""

LINUX_DESKTOP = """#!/bin/sh
# Adds Admin PDF Toolkit to the applications menu of this user.
HERE="$(cd "$(dirname "$0")" && pwd)"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS"
cat > "$APPS/adminpdftoolkit.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Admin PDF Toolkit
Comment=Offline PDF toolkit / Çevrimdışı PDF araçları
Exec="$HERE/AdminPDFToolkit"
Icon=$HERE/icon.png
Terminal=false
Categories=Office;Utility;
EOF
chmod +x "$APPS/adminpdftoolkit.desktop"
echo "Uygulamalar menüsüne eklendi / Added to the applications menu: $APPS/adminpdftoolkit.desktop"
"""

MAC_START = """#!/bin/sh
# Admin PDF Toolkit.app — starts the launcher window.
RES="$(cd "$(dirname "$0")/../Resources" && pwd)"
exec "$RES/python/bin/python3" -m adminpdf.launcher "$@"
"""

INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Admin PDF Toolkit</string>
  <key>CFBundleDisplayName</key><string>Admin PDF Toolkit</string>
  <key>CFBundleIdentifier</key><string>io.github.amraselessar.adminpdftoolkit</string>
  <key>CFBundleVersion</key><string>{version}</string>
  <key>CFBundleShortVersionString</key><string>{version}</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>AdminPDFToolkit</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.productivity</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSHumanReadableCopyright</key><string>AGPL-3.0 — https://github.com/AmrasElessar/adminpdftoolkit</string>
</dict>
</plist>
"""


def target() -> tuple[str, str]:
    system = "darwin" if sys.platform == "darwin" else "linux" if sys.platform.startswith("linux") else sys.platform
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "aarch64": "arm64"}.get(machine, machine)
    if (system, machine) not in TRIPLES:
        sys.exit(f"unsupported build platform: {system} {machine}")
    return system, machine


def resolve_python(triple: str) -> dict[str, str]:
    """Newest python-build-standalone ``install_only`` build of PYTHON_MINOR."""
    release = _api(f"repos/{PBS_REPO}/releases/latest")
    pattern = re.compile(rf"cpython-{re.escape(PYTHON_MINOR)}\.\d+\+\d+-{re.escape(triple)}-install_only\.tar\.gz")
    for asset in release["assets"]:
        if pattern.fullmatch(asset["name"]):
            digest = str(asset.get("digest") or "").removeprefix("sha256:")
            if not digest:
                sums = next((a for a in release["assets"] if a["name"] == "SHA256SUMS"), None)
                if sums:
                    import urllib.request

                    with urllib.request.urlopen(sums["browser_download_url"], timeout=60) as r:
                        for line in r.read().decode().splitlines():
                            parts = line.split()
                            if len(parts) == 2 and parts[1] == asset["name"]:
                                digest = parts[0]
            return {"url": asset["browser_download_url"], "sha256": digest, "name": asset["name"]}
    sys.exit(f"{PBS_REPO} {release['tag_name']}: no {PYTHON_MINOR} install_only build for {triple}")


def install_python(dest: Path, triple: str) -> str:
    """Unpack the standalone Python into ``dest`` (→ dest/bin/python3)."""
    spec = resolve_python(triple)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / spec["name"]
        fetch(spec["url"], archive, spec["sha256"])
        with tarfile.open(archive) as tar:
            tar.extractall(tmp, filter="data")  # refuses absolute paths, .., device files
        shutil.move(str(Path(tmp) / "python"), dest)
    return spec["name"]


def install_app(python_home: Path) -> None:
    py = python_home / "bin" / "python3"
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", tmp, str(ROOT / "server")], check=True
        )
        (wheel,) = Path(tmp).glob("adminpdf-*.whl")
        subprocess.run(
            [str(py), "-m", "pip", "install", "-q", "--no-compile", "--only-binary=:all:", str(wheel)], check=True
        )
    # Byte-code is written on first use into the user's cache instead.
    for cache in python_home.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    subprocess.run([str(py), "-c", "import tkinter, adminpdf.launcher, adminpdf.app"], check=True)


def write_exec(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def build_linux(ver: str, machine: str) -> Path:
    stage = DIST / "linux" / TOP
    shutil.rmtree(stage.parent, ignore_errors=True)
    stage.mkdir(parents=True)
    name = install_python(stage / "python", TRIPLES[("linux", machine)])
    install_app(stage / "python")
    write_exec(stage / "AdminPDFToolkit", LINUX_START)
    write_exec(stage / "Uygulamalar menusune ekle.sh", LINUX_DESKTOP)
    shutil.copy(ICON, stage / "icon.png")
    docs(stage, ver)
    print(f"python: {name}")
    out = DIST / f"AdminPDFToolkit-{ver}-Linux-{machine}.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        tar.add(stage, arcname=TOP)
    return out


def build_macos(ver: str, machine: str) -> Path:
    stage = DIST / "macos" / TOP
    shutil.rmtree(stage.parent, ignore_errors=True)
    app = stage / "AdminPDFToolkit.app" / "Contents"
    (app / "MacOS").mkdir(parents=True)
    (app / "Resources").mkdir()
    name = install_python(app / "Resources" / "python", TRIPLES[("darwin", machine)])
    install_app(app / "Resources" / "python")
    write_exec(app / "MacOS" / "AdminPDFToolkit", MAC_START)
    (app / "Info.plist").write_text(INFO_PLIST.replace("{version}", ver), encoding="utf-8")
    py = app / "Resources" / "python" / "bin" / "python3"
    subprocess.run(
        [
            str(py),
            "-c",
            f"from PIL import Image; Image.open({str(ICON)!r}).save({str(app / 'Resources' / 'AppIcon.icns')!r})",
        ],
        check=True,
    )
    for cache in (app / "Resources" / "python").rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    # Ad-hoc signature: free, required for Apple Silicon to run the binaries
    # after files were added; notarisation would need a paid Apple account.
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(stage / "AdminPDFToolkit.app")], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(stage / "AdminPDFToolkit.app")], check=True)
    docs(stage, ver)
    print(f"python: {name}")
    out = DIST / f"AdminPDFToolkit-{ver}-macOS-{machine}.zip"
    out.unlink(missing_ok=True)
    # ditto keeps symlinks, permissions and signatures (zipfile would not).
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(stage), str(out)], check=True)
    return out


def docs(stage: Path, ver: str) -> None:
    for name in DOCS:
        shutil.copy(ROOT / name, stage / name)
    readme = (ROOT / "scripts" / "package" / "OKUBENI-Unix.txt").read_text(encoding="utf-8")
    (stage / "OKUBENI.txt").write_text(readme.replace("{version}", ver), encoding="utf-8")


def main() -> None:
    if not (ROOT / "server" / "adminpdf" / "web_dist" / "index.html").is_file():
        sys.exit("Build the web UI first: cd web && npm ci && npm run build")
    system, machine = target()
    ver = version()
    out = build_macos(ver, machine) if system == "darwin" else build_linux(ver, machine)
    print(out)


if __name__ == "__main__":
    main()
