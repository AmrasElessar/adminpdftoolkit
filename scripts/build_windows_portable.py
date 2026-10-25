"""Build the self-contained Windows package: embedded Python + every library.

Run on Windows with the Python version to embed (CI: windows-latest), after
building the web UI:

    cd web && npm ci && npm run build && cd ..
    python scripts/build_windows_portable.py   # → dist/AdminPDFToolkit-<version>-Windows.zip

The target PC needs nothing installed and no internet: unzip, double-click
"Baslat (Windows).bat". OCR (Tesseract) stays an optional extra.
"""

from __future__ import annotations

import io
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from build_package import DOCS, ROOT, crlf, version  # sibling script (scripts/ is on sys.path)

DIST = ROOT / "dist"
TOP = "AdminPDFToolkit"
EMBED_URL = "https://www.python.org/ftp/python/{v}/python-{v}-embed-amd64.zip"
SCRIPTS = ("install-ocr-windows.bat", "install-ocr-windows.ps1", "offer-ocr.bat")
LAUNCHERS = {
    "Baslat (Windows).bat": (
        "@echo off\n"
        "REM Admin PDF Toolkit - self-contained: no Python or other install needed.\n"
        'cd /d "%~dp0"\n'
        'set "APT_DATA_DIR=%~dp0data"\n'
        'if not exist "%~dp0data" call "%~dp0scripts\\offer-ocr.bat"\n'
        '"%~dp0python\\python.exe" -m adminpdf --open %*\n'
        "if errorlevel 1 pause\n"
    ),
    "Baslat - Ag Paylasimi (Windows).bat": (
        "@echo off\n"
        "REM Also reachable from phones / other PCs on the network (pairing link in this window).\n"
        'call "%~dp0Baslat (Windows).bat" --lan %*\n'
    ),
    "OCR Kur (Windows).bat": '@echo off\ncall "%~dp0scripts\\install-ocr-windows.bat"\n',
}


def embed_python(dest: Path) -> None:
    ver = platform.python_version()
    url = EMBED_URL.format(v=ver)
    print(f"downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as r:
        zipfile.ZipFile(io.BytesIO(r.read())).extractall(dest)
    # The embeddable build ignores site-packages unless its ._pth file says so.
    (pth,) = dest.glob("python*._pth")
    stdlib = next(dest.glob("python*.zip")).name
    pth.write_text(f"{stdlib}\n.\nLib\\site-packages\nimport site\n", encoding="ascii")


def install_libraries(site: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", tmp, str(ROOT / "server")], check=True
        )
        (wheel,) = Path(tmp).glob("adminpdf-*.whl")
        pip = [sys.executable, "-m", "pip", "install", "-q", "--no-compile", "--only-binary=:all:"]
        subprocess.run([*pip, "--target", str(site), str(wheel)], check=True)
    # pip's console-script launchers point at the build machine's Python.
    for scripts in ("bin", "Scripts"):
        shutil.rmtree(site / scripts, ignore_errors=True)
    # OpenCV's FFmpeg plug-in (~30 MB) is only for video I/O, which we never use;
    # cv2 loads it lazily, so images keep working without it.
    for dll in (site / "cv2").glob("opencv_videoio_ffmpeg*.dll"):
        dll.unlink()


def main() -> None:
    if sys.platform != "win32":
        sys.exit("Run on Windows: the embedded Python and its libraries must be Windows builds.")
    ver = version()
    web_dist = ROOT / "server" / "adminpdf" / "web_dist"
    if not (web_dist / "index.html").is_file():
        sys.exit("Build the web UI first: cd web && npm ci && npm run build")
    stage = DIST / "windows" / TOP
    shutil.rmtree(stage.parent, ignore_errors=True)
    python = stage / "python"
    embed_python(python)
    install_libraries(python / "Lib" / "site-packages")
    (stage / "scripts").mkdir()
    for name in SCRIPTS:
        (stage / "scripts" / name).write_bytes(crlf((ROOT / "scripts" / name).read_text(encoding="utf-8")))
    for name, body in LAUNCHERS.items():
        (stage / name).write_bytes(crlf(body))
    for name in DOCS:
        shutil.copy(ROOT / name, stage / name)
    readme = (ROOT / "scripts" / "package" / "OKUBENI-Windows.txt").read_text(encoding="utf-8")
    (stage / "OKUBENI.txt").write_bytes(crlf(readme.replace("{version}", ver)))

    out = DIST / f"AdminPDFToolkit-{ver}-Windows.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(stage.parent).as_posix())
    print(out)


if __name__ == "__main__":
    main()
