"""Build the portable package (zip) from a checkout whose web UI is built.

    cd web && npm ci && npm run build && cd ..
    python scripts/build_package.py            # → dist/AdminPDFToolkit-<version>.zip

The zip holds the Python server with the built UI, the start scripts and the
docs. Python packages are installed on the first start (Baslat (Windows).bat
or scripts/start.sh). Windows scripts get CRLF line endings.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SKIP_DIRS = {"__pycache__", "_data", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
DOCS = (
    "README.md",
    "CHANGELOG.md",
    "THIRD_PARTY_LICENSES.md",
    "STANDARDS.md",
    "LICENSE",
    "LICENSE.tr.txt",
    "NOTICE.txt",
)
SCRIPTS = ("start.sh", "start-windows.bat", "install-ocr-windows.bat", "install-ocr-windows.ps1")
LAUNCHERS = {
    "Baslat (Windows).bat": '@echo off\ncall "%~dp0scripts\\start-windows.bat" %*\n',
    "OCR Kur (Windows).bat": '@echo off\ncall "%~dp0scripts\\install-ocr-windows.bat"\n',
}


def version() -> str:
    text = (ROOT / "server" / "adminpdf" / "config.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION = "([^"]+)"', text, re.M)
    if not match:
        sys.exit("VERSION not found in server/adminpdf/config.py")
    return match.group(1)


def crlf(text: str) -> bytes:
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


def main() -> None:
    ver = version()
    web_dist = ROOT / "server" / "adminpdf" / "web_dist"
    if not (web_dist / "index.html").is_file() or not (web_dist / "licenses.txt").is_file():
        sys.exit("Build the web UI first: cd web && npm ci && npm run build")
    top = "AdminPDFToolkit"
    DIST.mkdir(exist_ok=True)
    out = DIST / f"AdminPDFToolkit-{ver}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        package = ROOT / "server" / "adminpdf"
        for path in sorted(package.rglob("*")):
            rel = path.relative_to(package)
            if path.is_file() and not SKIP_DIRS.intersection(rel.parts) and path.suffix != ".pyc":
                z.write(path, f"{top}/server/adminpdf/{rel.as_posix()}")
        z.write(ROOT / "server" / "pyproject.toml", f"{top}/server/pyproject.toml")
        for name in SCRIPTS:
            path = ROOT / "scripts" / name
            data = crlf(path.read_text(encoding="utf-8")) if path.suffix in (".bat", ".ps1") else path.read_bytes()
            z.writestr(f"{top}/scripts/{name}", data)
        for name, body in LAUNCHERS.items():
            z.writestr(f"{top}/{name}", crlf(body))
        for name in DOCS:
            z.write(ROOT / name, f"{top}/{name}")
        readme = (ROOT / "scripts" / "package" / "OKUBENI.txt").read_text(encoding="utf-8")
        z.writestr(f"{top}/OKUBENI.txt", crlf(readme.replace("{version}", ver)))
    print(out)


if __name__ == "__main__":
    main()
