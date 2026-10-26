"""Build the self-contained Windows package: embedded Python + every library.

Run on Windows with the Python version to embed (CI: windows-latest), after
building the web UI:

    cd web && npm ci && npm run build && cd ..
    python scripts/build_windows_portable.py   # → dist/AdminPDFToolkit-<version>-Windows.zip

The target PC needs nothing installed and no internet: unzip, double-click
"Baslat (Windows).bat". OCR (Tesseract + Turkish/English data) is bundled in
ocr/, so scanned documents work offline too — also on office PCs whose
network blocks downloads.

Every downloaded file is checked against the SHA-256 pinned in
scripts/ocr/sources.json (when set), and the installer's Authenticode
signature is reported. ocr/manifest.json records the SHA-256 of every
bundled file; the app re-checks it before each use and refuses a damaged or
altered bundle, and "OCR Onar (Windows).bat" repairs language data only
with files matching those hashes.
"""

from __future__ import annotations

import hashlib
import io
import json
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
SCRIPTS = ("repair-ocr-windows.ps1",)
OCR_SOURCES = ROOT / "scripts" / "ocr" / "sources.json"
# Tesseract programs the app needs; the installer's training tools are dropped.
OCR_KEEP_EXE = {"tesseract.exe"}
LAUNCHERS = {
    "Baslat (Windows).bat": (
        "@echo off\n"
        "REM Admin PDF Toolkit - self-contained: no Python or other install needed.\n"
        'cd /d "%~dp0"\n'
        'set "APT_DATA_DIR=%~dp0data"\n'
        'set "APT_OCR_DIR=%~dp0ocr"\n'
        '"%~dp0python\\python.exe" -m adminpdf --open %*\n'
        "if errorlevel 1 pause\n"
    ),
    "Baslat - Ag Paylasimi (Windows).bat": (
        "@echo off\n"
        "REM Also reachable from phones / other PCs on the network (pairing link in this window).\n"
        'call "%~dp0Baslat (Windows).bat" --lan %*\n'
    ),
    "OCR Onar (Windows).bat": (
        "@echo off\n"
        "REM Checks the bundled OCR files and re-downloads damaged language data (hash-verified).\n"
        "powershell -NoProfile -ExecutionPolicy Bypass"
        ' -File "%~dp0scripts\\repair-ocr-windows.ps1" -OcrDir "%~dp0ocr"\n'
        "pause\n"
    ),
    "Sertifikaya Guven (Windows).bat": (
        "@echo off\n"
        "REM Trust this app's local HTTPS certificate on this PC (Windows asks for confirmation).\n"
        'cd /d "%~dp0"\n'
        'set "APT_DATA_DIR=%~dp0data"\n'
        '"%~dp0python\\python.exe" -m adminpdf --trust-ca\n'
        "pause\n"
    ),
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


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(url: str, dest: Path, pinned: str) -> str:
    """Download over HTTPS and check the pinned SHA-256 (if any)."""
    if not url.startswith("https://"):
        sys.exit(f"refusing non-HTTPS source: {url}")
    print(f"downloading {url}")
    with urllib.request.urlopen(url, timeout=300) as r, dest.open("wb") as fh:
        shutil.copyfileobj(r, fh)
    digest = sha256(dest)
    if pinned and digest != pinned.lower():
        sys.exit(f"SHA-256 mismatch for {url}:\n  expected {pinned}\n  got      {digest}")
    if not pinned:
        print(f"  NOT PINNED — add to scripts/ocr/sources.json: sha256 = {digest}")
    return digest


def authenticode(path: Path) -> str:
    """The Windows signature status of ``path`` (reported, not required:
    the pinned hash is the real check)."""
    ps = (
        f"(Get-AuthenticodeSignature -LiteralPath '{path}')"
        " | ForEach-Object { $_.Status.ToString() + ' ' + $_.SignerCertificate.Subject }"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, check=False)
    return r.stdout.strip() or "unknown"


def bundle_ocr(dest: Path) -> None:
    """Tesseract (UB Mannheim build) + tur/eng/osd fast models into ``dest``."""
    sources = json.loads(OCR_SOURCES.read_text(encoding="utf-8"))
    used: dict[str, dict[str, str]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        tess = sources["tesseract"]
        installer = work / "tesseract-setup.exe"
        used["tesseract"] = {"url": tess["url"], "sha256": fetch(tess["url"], installer, tess["sha256"])}
        print(f"  signature: {authenticode(installer)}")
        target = work / "tesseract"
        # NSIS silent install into a scratch folder; /D must be last and unquoted.
        subprocess.run([str(installer), "/S", f"/D={target}"], check=True)
        if not (target / "tesseract.exe").is_file():
            sys.exit("Tesseract installer did not produce tesseract.exe")
        dest.mkdir(parents=True)
        for item in target.iterdir():
            program = item.suffix.lower() == ".dll" or item.name.lower() in OCR_KEEP_EXE
            licence = item.suffix.lower() in (".txt", ".md", "") and "licen" in item.name.lower()
            if item.is_file() and (program or licence):
                shutil.copy2(item, dest / item.name)
        # Renderer configs (hocr, pdf, txt) and the PDF glyph font; models come next.
        tessdata = dest / "tessdata"
        shutil.copytree(
            target / "tessdata", tessdata, ignore=shutil.ignore_patterns("*.traineddata", "script", "tessconfigs")
        )
        for lang, src in sources["tessdata"].items():
            out = tessdata / f"{lang}.traineddata"
            used[f"tessdata/{lang}"] = {"url": src["url"], "sha256": fetch(src["url"], out, src["sha256"])}
    (dest / "NOTICE.txt").write_text(
        "Tesseract OCR (Apache-2.0) - https://github.com/tesseract-ocr/tesseract\n"
        "Windows build by UB Mannheim (Apache-2.0) - https://github.com/UB-Mannheim/tesseract\n"
        "Language data: tessdata_fast (Apache-2.0) - https://github.com/tesseract-ocr/tessdata_fast\n"
        "The bundled DLLs (Leptonica, libpng, libjpeg-turbo, libtiff, zlib, libwebp, OpenJPEG, giflib, ...)\n"
        "are under permissive licences; see THIRD_PARTY_LICENSES.md.\n",
        encoding="utf-8",
    )
    files = {p.relative_to(dest).as_posix(): sha256(p) for p in sorted(dest.rglob("*")) if p.is_file()}
    manifest = {"version": sources["tesseract"]["version"], "sources": used, "files": files}
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"OCR bundled: {len(files)} files")


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
    bundle_ocr(stage / "ocr")
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
