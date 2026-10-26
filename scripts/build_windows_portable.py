r"""Build the self-contained Windows package: embedded Python + every library.

Run on Windows with the Python version to embed (CI: windows-latest), after
building the web UI:

    cd web && npm ci && npm run build && cd ..
    python scripts/build_windows_portable.py   # → dist/AdminPDFToolkit-<version>-Windows.zip

The target PC needs nothing installed and no internet: unzip, double-click
AdminPDFToolkit.exe (the launcher: component checklist, update prompt, tray
icon, no console window; the .bat fallbacks live in scripts\). OCR
(Tesseract + Turkish/English data) and Ghostscript (PDF/A) are bundled in
ocr\ and gs\, so everything works offline — also on office PCs whose
network blocks downloads.

Tools come from their newest GitHub release (or the file pinned in
scripts/ocr/sources.json) and are checked against the SHA-256 GitHub
publishes; the installers' Authenticode signatures are reported. Each
bundle's manifest.json records the SHA-256 of every file; the app re-checks
it before use and refuses a damaged or altered bundle. Ghostscript's exact
source tarball is written to dist/sources/ and published with the release
(AGPL-3.0). With the WINDOWS_SIGN_PFX secret the launcher is Authenticode-
signed.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from build_package import DOCS, ROOT, crlf, version  # sibling script (scripts/ is on sys.path)

DIST = ROOT / "dist"
TOP = "AdminPDFToolkit"
EMBED_URL = "https://www.python.org/ftp/python/{v}/python-{v}-embed-amd64.zip"
SCRIPTS = ("repair-ocr-windows.ps1",)
OCR_SOURCES = ROOT / "scripts" / "ocr" / "sources.json"
# Tesseract programs the app needs; the installer's training tools are dropped.
OCR_KEEP_EXE = {"tesseract.exe"}
# Fallbacks for the launcher, kept in scripts\ (they show a console window).
ENV = (
    'set "ROOT=%~dp0.."\n'
    'cd /d "%ROOT%"\n'
    'set "APT_DATA_DIR=%ROOT%\\data"\n'
    'set "APT_OCR_DIR=%ROOT%\\ocr"\n'
    'set "APT_GS_DIR=%ROOT%\\gs"\n'
)
BATCH = {
    "Baslat.bat": (
        "@echo off\n"
        "REM Fallback for AdminPDFToolkit.exe: same start, with a console window.\n"
        + ENV
        + '"%ROOT%\\python\\python.exe" -m adminpdf --open %*\n'
        "if errorlevel 1 pause\n"
    ),
    "Baslat - Ag Paylasimi.bat": '@echo off\ncall "%~dp0Baslat.bat" --lan %*\n',
    "OCR Onar.bat": (
        "@echo off\n"
        "REM Checks the bundled OCR files and re-downloads damaged language data (hash-verified).\n"
        "powershell -NoProfile -ExecutionPolicy Bypass"
        ' -File "%~dp0repair-ocr-windows.ps1" -OcrDir "%~dp0..\\ocr"\n'
        "pause\n"
    ),
    "Sertifikaya Guven.bat": (
        "@echo off\n"
        "REM Trust this app's local HTTPS certificate on this PC (Windows asks for confirmation).\n"
        + ENV
        + '"%ROOT%\\python\\python.exe" -m adminpdf --trust-ca\n'
        "pause\n"
    ),
    "Sistem Denetimi.bat": (
        "@echo off\n"
        "REM Lists every component and its state (the launcher shows the same).\n"
        + ENV
        + '"%ROOT%\\python\\python.exe" -m adminpdf.selfcheck\n'
        "pause\n"
    ),
}
LAUNCHER_SRC = ROOT / "scripts" / "launcher"


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


def _api(path: str) -> Any:
    req = urllib.request.Request(f"https://api.github.com/{path}", headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:  # CI: avoids the anonymous rate limit
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def resolve(spec: dict[str, str]) -> dict[str, str]:
    """``{version, url, sha256[, source_url, source_sha256]}`` of a tool: the
    pinned file when ``url`` is set, else the newest GitHub release asset
    together with the SHA-256 digest GitHub publishes for it."""
    if spec.get("url"):
        return {"version": spec.get("version", "pinned"), "url": spec["url"], "sha256": spec.get("sha256", "")}
    release = _api(f"repos/{spec['github']}/releases/latest")

    def asset(pattern: str) -> dict[str, str]:
        for a in release["assets"]:
            if re.fullmatch(pattern, a["name"]):
                digest = str(a.get("digest") or "")
                return {"url": a["browser_download_url"], "sha256": digest.removeprefix("sha256:")}
        sys.exit(f"{spec['github']} {release['tag_name']}: no asset matching {pattern}")

    found = {"version": release["tag_name"], **asset(spec["asset"])}
    if spec.get("source_asset"):
        src = asset(spec["source_asset"])
        found |= {"source_url": src["url"], "source_sha256": src["sha256"]}
    return found


def fetch(url: str, dest: Path, expected: str) -> str:
    """Download over HTTPS and check the expected SHA-256 (pinned, or the
    digest GitHub publishes for the release asset)."""
    if not url.startswith("https://"):
        sys.exit(f"refusing non-HTTPS source: {url}")
    print(f"downloading {url}")
    with urllib.request.urlopen(url, timeout=600) as r, dest.open("wb") as fh:
        shutil.copyfileobj(r, fh)
    digest = sha256(dest)
    if expected and digest != expected.lower():
        sys.exit(f"SHA-256 mismatch for {url}:\n  expected {expected}\n  got      {digest}")
    if not expected:
        print(f"  no published hash — pin it in scripts/ocr/sources.json: sha256 = {digest}")
    return digest


def authenticode(path: Path) -> str:
    """The Windows signature status of ``path`` (reported, not required:
    the hash is the real check)."""
    ps = (
        f"(Get-AuthenticodeSignature -LiteralPath '{path}')"
        " | ForEach-Object { $_.Status.ToString() + ' ' + $_.SignerCertificate.Subject }"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, check=False)
    return r.stdout.strip() or "unknown"


def nsis_extract(installer: Path, target: Path, expect: str) -> None:
    """Unpack an NSIS installer with 7-Zip (preinstalled on CI runners):
    nothing is installed on the build machine and no UAC re-launch can race
    us. Falls back to a silent install (``/S /D=``) and waits for ``expect``."""
    print(f"  signature: {authenticode(installer)}")
    seven = shutil.which("7z") or next((str(p) for p in (Path("C:/Program Files/7-Zip/7z.exe"),) if p.is_file()), None)
    if seven:
        subprocess.run([seven, "x", "-y", f"-o{target}", str(installer)], check=True, stdout=subprocess.DEVNULL)
        for junk in ("$PLUGINSDIR", "$TEMP", "uninstall.exe", "Uninstall.exe", "uninst.exe"):
            path = target / junk
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.is_file():
                path.unlink()
    else:
        # /D must be last and unquoted.
        subprocess.run([str(installer), "/S", f"/D={target}"], check=True)
    for _ in range(120):
        if (target / expect).is_file():
            return
        time.sleep(1)
    listing = "\n".join(str(p.relative_to(target)) for p in sorted(target.rglob("*"))[:80]) if target.exists() else "-"
    sys.exit(f"{installer.name} did not produce {expect}; got:\n{listing}")


def write_manifest(dest: Path, version: str, sources: dict[str, dict[str, str]]) -> None:
    """SHA-256 of every bundled file; the app checks it before each use."""
    files = {p.relative_to(dest).as_posix(): sha256(p) for p in sorted(dest.rglob("*")) if p.is_file()}
    manifest = {"version": version, "sources": sources, "files": files}
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"{dest.name}: {version}, {len(files)} files")


def bundle_ocr(dest: Path, spec: dict[str, Any]) -> str:
    """Tesseract (UB Mannheim build) + tur/eng/osd fast models into ``dest``."""
    used: dict[str, dict[str, str]] = {}
    tess = resolve(spec["tesseract"])
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        installer = work / "tesseract-setup.exe"
        used["tesseract"] = {"url": tess["url"], "sha256": fetch(tess["url"], installer, tess["sha256"])}
        target = work / "tesseract"
        nsis_extract(installer, target, "tesseract.exe")
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
        for lang, src in spec["tessdata"].items():
            out = tessdata / f"{lang}.traineddata"
            used[f"tessdata/{lang}"] = {"url": src["url"], "sha256": fetch(src["url"], out, src["sha256"])}
    (dest / "NOTICE.txt").write_text(
        f"Tesseract OCR {tess['version']} (Apache-2.0) - https://github.com/tesseract-ocr/tesseract\n"
        "Windows build by UB Mannheim (Apache-2.0) - https://github.com/UB-Mannheim/tesseract\n"
        "Language data: tessdata_fast (Apache-2.0) - https://github.com/tesseract-ocr/tessdata_fast\n"
        "The bundled DLLs (Leptonica, libpng, libjpeg-turbo, libtiff, zlib, libwebp, OpenJPEG, giflib, ...)\n"
        "are under permissive licences; see THIRD_PARTY_LICENSES.md.\n",
        encoding="utf-8",
    )
    write_manifest(dest, tess["version"], used)
    return tess["version"]


def bundle_ghostscript(dest: Path, spec: dict[str, Any], sources_dir: Path) -> str:
    """Ghostscript (AGPL-3.0, like this app) into ``dest``; its exact source
    tarball goes to ``sources_dir`` to be published next to the package."""
    gs = resolve(spec)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        installer = work / "gs-setup.exe"
        used = {"ghostscript": {"url": gs["url"], "sha256": fetch(gs["url"], installer, gs["sha256"])}}
        target = work / "gs"
        nsis_extract(installer, target, "bin/gswin64c.exe")
        (dest / "bin").mkdir(parents=True)
        for item in (target / "bin").iterdir():
            if item.suffix.lower() == ".dll" or item.name.lower() == "gswin64c.exe":
                shutil.copy2(item, dest / "bin" / item.name)
        for item in [*target.glob("*"), *target.glob("doc/*")]:
            if item.is_file() and item.name.upper().startswith(("LICENSE", "COPYING")):
                shutil.copy2(item, dest / item.name)
    source_note = ""
    if gs.get("source_url"):
        sources_dir.mkdir(parents=True, exist_ok=True)
        tarball = sources_dir / gs["source_url"].rsplit("/", 1)[-1]
        used["source"] = {"url": gs["source_url"], "sha256": fetch(gs["source_url"], tarball, gs["source_sha256"])}
        source_note = (
            f"Corresponding source: {tarball.name}, published with this release and at\n  {gs['source_url']}\n"
        )
    (dest / "NOTICE.txt").write_text(
        f"Ghostscript {gs['version']} - Copyright Artifex Software, Inc. - AGPL-3.0\n"
        "https://ghostscript.com/ - unmodified Windows build from Artifex.\n" + source_note,
        encoding="utf-8",
    )
    write_manifest(dest, gs["version"], used)
    return gs["version"]


def compile_launcher(stage: Path, ver: str) -> Path:
    """AdminPDFToolkit.exe from scripts/launcher with the csc.exe of .NET
    Framework 4.x (part of Windows): plain managed code, no packer, with
    version info and a manifest — the things antivirus heuristics look for."""
    found = sorted(Path(os.environ.get("WINDIR", "C:/Windows")).glob("Microsoft.NET/Framework64/v4*/csc.exe"))
    if not found:
        sys.exit("csc.exe (.NET Framework 4.x) not found")
    numeric = ".".join([*re.findall(r"\d+", ver), "0", "0", "0"][:3])
    out = stage / "AdminPDFToolkit.exe"
    with tempfile.TemporaryDirectory() as tmp:
        info = Path(tmp) / "AssemblyInfo.cs"
        template = (LAUNCHER_SRC / "AssemblyInfo.cs.in").read_text(encoding="utf-8")
        info.write_text(template.replace("{version}", numeric), encoding="utf-8")
        subprocess.run(
            [
                str(found[-1]),
                "/nologo",
                "/target:winexe",
                "/optimize+",
                f"/out:{out}",
                f"/win32icon:{LAUNCHER_SRC / 'app.ico'}",
                f"/win32manifest:{LAUNCHER_SRC / 'app.manifest'}",
                "/r:System.Windows.Forms.dll",
                "/r:System.Drawing.dll",
                "/r:System.Web.Extensions.dll",
                str(LAUNCHER_SRC / "Launcher.cs"),
                str(info),
            ],
            check=True,
        )
    sign(out)
    return out


def sign(path: Path) -> None:
    """Authenticode-sign ``path`` when a code-signing certificate is provided
    (CI secrets WINDOWS_SIGN_PFX = base64 .pfx, WINDOWS_SIGN_PASSWORD)."""
    pfx_b64 = os.environ.get("WINDOWS_SIGN_PFX", "").strip()
    if not pfx_b64:
        print(f"  {path.name}: not signed (no WINDOWS_SIGN_PFX)")
        return
    kits = Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Windows Kits/10/bin"
    tools = sorted(kits.glob("*/x64/signtool.exe"))
    if not tools:
        sys.exit("signtool.exe not found")
    with tempfile.TemporaryDirectory() as tmp:
        pfx = Path(tmp) / "sign.pfx"
        pfx.write_bytes(base64.b64decode(pfx_b64))
        subprocess.run(
            [
                str(tools[-1]),
                "sign",
                "/fd",
                "SHA256",
                "/td",
                "SHA256",
                "/tr",
                os.environ.get("WINDOWS_SIGN_TIMESTAMP_URL", "http://timestamp.digicert.com"),
                "/d",
                "Admin PDF Toolkit",
                "/f",
                str(pfx),
                "/p",
                os.environ.get("WINDOWS_SIGN_PASSWORD", ""),
                str(path),
            ],
            check=True,
        )
    print(f"  {path.name}: signed")


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
    tools = json.loads(OCR_SOURCES.read_text(encoding="utf-8"))
    components = {
        "python": platform.python_version(),
        "tesseract": bundle_ocr(stage / "ocr", tools),
        "ghostscript": bundle_ghostscript(stage / "gs", tools["ghostscript"], DIST / "sources"),
    }
    (stage / "scripts").mkdir()
    for name in SCRIPTS:
        (stage / "scripts" / name).write_bytes(crlf((ROOT / "scripts" / name).read_text(encoding="utf-8")))
    for name, body in BATCH.items():
        (stage / "scripts" / name).write_bytes(crlf(body))
    compile_launcher(stage, ver)
    # What this package carries; the release manifest and the updater show it.
    (stage / "package.json").write_text(json.dumps({"version": ver, "components": components}, indent=2))
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
