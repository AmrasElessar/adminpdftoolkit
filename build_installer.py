"""Build the end-user setup .exe.

Pipeline
--------
1. Make sure the launcher .exe exists (build it via ``build_exe.py`` if missing).
2. Zip the app code (everything needed at runtime, no tests / build artifacts)
   into ``build/_installer/app_bundle.zip``.
3. Run PyInstaller --onefile on ``installer.py``, attaching the bundle + the
   launcher .exe via --add-data. The bootloader unpacks them on launch.

Output
------
``dist/AdminPDFToolkit_Setup.exe`` — single-file installer (~15-25 MB).
The end user double-clicks this on a fresh machine: it asks for an install
path, then downloads Python embeddable, all pip packages, ClamAV, and EasyOCR
models into that folder. Internet required during install, not after.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# UTF-8 stdout for Turkish chars + arrows on cp1254 consoles.
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        with contextlib.suppress(Exception):
            _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
INSTALLER_SRC = ROOT / "installer.py"
LAUNCHER_EXE = ROOT / "build" / "_pyinstaller_dist" / "Admin PDF Toolkit.exe"
BUILD_DIR = ROOT / "build" / "_installer"
BUNDLE_ZIP = BUILD_DIR / "app_bundle.zip"
PYI_BUILD = BUILD_DIR / "pyi_build"
PYI_DIST = BUILD_DIR / "pyi_dist"
OUT_DIR = ROOT / "dist"
OUT_NAME = "AdminPDFToolkit_Setup"

# Files at the repo root to ship.
ROOT_FILES = [
    "app.py", "app_http.py", "state.py", "settings.py",
    "pdf_converter.py", "pdf_safety.py",
    "requirements.txt",
    "LICENSE", "NOTICE.txt", "THIRD_PARTY_LICENSES.md", "README.md",
]

# Folders at the repo root to ship recursively. tests/ excluded — installed
# distribution does not run pytest. _bench_samples/ excluded (huge PDFs).
ROOT_DIRS = ["core", "routers", "pipelines", "parsers", "templates", "static", "scripts"]

# Patterns to exclude when zipping directories.
SKIP_DIR_NAMES = {"__pycache__", ".pytest_cache", ".git", ".venv", "node_modules"}
SKIP_FILE_SUFFIXES = (".pyc", ".pyo")


def info(msg: str) -> None:
    print(f"    {msg}")


def step(msg: str) -> None:
    print(f"\n>>> {msg}")


def fail(msg: str) -> int:
    print(f"\n[HATA] {msg}")
    return 1


def ensure_launcher_exe() -> bool:
    if LAUNCHER_EXE.exists():
        info(f"launcher .exe mevcut: {LAUNCHER_EXE.name}")
        return True
    info("launcher .exe yok — build_exe.py mantığı çalıştırılıyor...")
    rc = subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--onefile", "--console",
            "--name", "Admin PDF Toolkit",
            "--workpath", str(ROOT / "build" / "_pyinstaller"),
            "--distpath", str(ROOT / "build" / "_pyinstaller_dist"),
            "--specpath", str(ROOT / "build" / "_pyinstaller"),
            "--noconfirm",
            str(ROOT / "launcher.py"),
        ],
    ).returncode
    return rc == 0 and LAUNCHER_EXE.exists()


def _ensure_pyinstaller() -> bool:
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        rc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"],
        ).returncode
        return rc == 0


def _ensure_editor_assets() -> None:
    """Run scripts/setup_editor_assets.py if static/pdfjs or static/fonts is empty."""
    pdfjs = ROOT / "static" / "pdfjs"
    fonts = ROOT / "static" / "fonts"
    if (pdfjs.exists() and any(pdfjs.iterdir())) and (fonts.exists() and any(fonts.iterdir())):
        return
    setup = ROOT / "scripts" / "setup_editor_assets.py"
    if not setup.exists():
        info("scripts/setup_editor_assets.py yok — atlandı")
        return
    info("static/pdfjs + static/fonts boş — setup_editor_assets çalışıyor...")
    subprocess.run([sys.executable, str(setup)], cwd=str(ROOT), check=False)


def _iter_files_for_zip() -> list[tuple[Path, Path]]:
    """Yield (absolute, relative) pairs for everything to include in app_bundle.zip."""
    pairs: list[tuple[Path, Path]] = []
    for name in ROOT_FILES:
        p = ROOT / name
        if p.exists():
            pairs.append((p, Path(name)))
    for d in ROOT_DIRS:
        src = ROOT / d
        if not src.exists():
            continue
        for path in src.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix in SKIP_FILE_SUFFIXES:
                continue
            pairs.append((path, path.relative_to(ROOT)))
    return pairs


def build_bundle() -> bool:
    _ensure_editor_assets()
    if BUNDLE_ZIP.exists():
        BUNDLE_ZIP.unlink()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    pairs = _iter_files_for_zip()
    if not pairs:
        info("kopyalanacak dosya yok!")
        return False
    info(f"{len(pairs)} dosya bundle ediliyor → {BUNDLE_ZIP.name}")
    with zipfile.ZipFile(BUNDLE_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for src, rel in pairs:
            zf.write(src, arcname=str(rel).replace("\\", "/"))
    size_mb = BUNDLE_ZIP.stat().st_size / (1024 * 1024)
    info(f"bundle hazır: {size_mb:.1f} MB")
    return True


def run_pyinstaller() -> bool:
    for d in (PYI_BUILD, PYI_DIST):
        if d.exists():
            shutil.rmtree(d)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",
        "--name", OUT_NAME,
        "--workpath", str(PYI_BUILD),
        "--distpath", str(PYI_DIST),
        "--specpath", str(PYI_BUILD),
        "--noconfirm",
        # Bundle the app code zip alongside the launcher .exe.
        f"--add-data={BUNDLE_ZIP};.",
        f"--add-data={LAUNCHER_EXE};.",
        str(INSTALLER_SRC),
    ]
    info("PyInstaller calisiyor...")
    return subprocess.run(cmd).returncode == 0


def main() -> int:
    print("=" * 60)
    print(" Admin PDF Toolkit — Installer Build")
    print("=" * 60)

    if not INSTALLER_SRC.exists():
        return fail(f"{INSTALLER_SRC} bulunamadi.")

    step("Launcher .exe hazır mı?")
    if not _ensure_pyinstaller():
        return fail("PyInstaller kurulamadi.")
    if not ensure_launcher_exe():
        return fail("launcher .exe olusturulamadi.")

    step("Uygulama kodu zip'leniyor")
    if not build_bundle():
        return fail("app_bundle.zip olusturulamadi.")

    step("PyInstaller ile installer .exe build ediliyor")
    if not run_pyinstaller():
        return fail("PyInstaller basarisiz.")

    src_exe = PYI_DIST / f"{OUT_NAME}.exe"
    if not src_exe.exists():
        return fail(f"Beklenen .exe olusmadi: {src_exe}")

    OUT_DIR.mkdir(exist_ok=True)
    target = OUT_DIR / f"{OUT_NAME}.exe"
    shutil.copy2(src_exe, target)
    size_mb = target.stat().st_size / (1024 * 1024)

    print()
    print("=" * 60)
    print(f" Hazir: {target}")
    print(f" Boyut: {size_mb:.1f} MB")
    print("=" * 60)
    print()
    print("Test: bu .exe'yi temiz bir Windows makinesine kopyala, cift tikla.")
    print("Installer kurulum klasoru sorar, sonra Python+paketler+ClamAV+EasyOCR")
    print("modellerini internetten indirir. Sonunda masaustu kisayolu olusur.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
