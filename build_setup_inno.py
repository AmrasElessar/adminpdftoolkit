"""Compile setup.iss into AdminPDFToolkit_Setup.exe via Inno Setup.

Pipeline
--------
1. Make sure the launcher .exe exists (build via build_exe.py if missing).
2. Make sure dist/Admin_PDF_Toolkit_Portable/ exists with app code copied
   in (run build_portable.py if missing — its app-code copy step is what
   we ship in the installer; the python/, clamav/, _EasyOCR_models/
   subdirs are NOT shipped because they are downloaded at install time).
3. Locate ISCC.exe (Inno Setup compiler) on this machine.
4. Run ISCC.exe setup.iss → dist/AdminPDFToolkit_Setup.exe (a classic Windows
   wizard installer with download progress + native progress pages).
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        with contextlib.suppress(Exception):
            _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
ISS_FILE = ROOT / "setup.iss"
PORTABLE = ROOT / "dist" / "Admin_PDF_Toolkit_Portable"
LAUNCHER_EXE = ROOT / "build" / "_pyinstaller_dist" / "Admin PDF Toolkit.exe"
OUT_EXE = ROOT / "dist" / "AdminPDFToolkit_Setup.exe"


def info(msg: str) -> None:
    print(f"    {msg}")


def step(msg: str) -> None:
    print(f"\n>>> {msg}")


def fail(msg: str) -> int:
    print(f"\n[HATA] {msg}")
    return 1


def find_iscc() -> Path | None:
    """ISCC.exe is the Inno Setup compiler. Hunt the common install dirs."""
    # Windows env-var lookups are case-insensitive at the OS level; the
    # mixed-case forms below are the names shown by ``set`` in cmd. ruff's
    # SIM112 wants ALL_CAPS but that's a Linux convention.
    candidates = [
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Inno Setup 6" / "ISCC.exe",  # noqa: SIM112
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        / "Inno Setup 6"
        / "ISCC.exe",  # noqa: SIM112
        Path.home() / "AppData" / "Local" / "Programs" / "Inno Setup 6" / "ISCC.exe",
    ]
    on_path = shutil.which("iscc") or shutil.which("ISCC")
    if on_path:
        candidates.insert(0, Path(on_path))
    for p in candidates:
        if p.exists():
            return p
    return None


def ensure_launcher_exe() -> bool:
    if LAUNCHER_EXE.exists():
        info(f"launcher .exe mevcut: {LAUNCHER_EXE.name}")
        return True
    info("launcher .exe yok — PyInstaller ile derleniyor...")
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        rc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"],
        ).returncode
        if rc != 0:
            return False
    rc = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",
            "--console",
            "--name",
            "Admin PDF Toolkit",
            "--workpath",
            str(ROOT / "build" / "_pyinstaller"),
            "--distpath",
            str(ROOT / "build" / "_pyinstaller_dist"),
            "--specpath",
            str(ROOT / "build" / "_pyinstaller"),
            "--noconfirm",
            str(ROOT / "launcher.py"),
        ],
    ).returncode
    return rc == 0 and LAUNCHER_EXE.exists()


def ensure_portable_app_code() -> bool:
    """We only need the app-code parts of the portable folder. If the folder
    doesn't exist at all, bail and tell the user to run build_portable.py."""
    if not PORTABLE.exists():
        return False
    # Cheap sanity check: app.py + core/ + static/ must be present.
    return (
        (PORTABLE / "app.py").exists()
        and (PORTABLE / "core").is_dir()
        and (PORTABLE / "static").is_dir()
    )


def main() -> int:
    print("=" * 60)
    print(" Admin PDF Toolkit — Inno Setup Installer Build")
    print("=" * 60)

    step("Inno Setup compiler aranıyor")
    iscc = find_iscc()
    if iscc is None:
        return fail(
            "ISCC.exe bulunamadı. Inno Setup yükle:\n"
            "  winget install --id JRSoftware.InnoSetup\n"
            "ya da: https://jrsoftware.org/isdl.php"
        )
    info(f"ISCC: {iscc}")

    step("Launcher .exe hazır mı?")
    if not ensure_launcher_exe():
        return fail("launcher .exe oluşturulamadı.")

    step("App code (portable folder) hazır mı?")
    if not ensure_portable_app_code():
        return fail(
            "dist/Admin_PDF_Toolkit_Portable/ eksik veya bozuk.\n  Önce: python build_portable.py"
        )
    info("app code dist/Admin_PDF_Toolkit_Portable/ altında mevcut")

    step("ISCC.exe çalıştırılıyor")
    rc = subprocess.run([str(iscc), str(ISS_FILE)], cwd=str(ROOT)).returncode
    if rc != 0:
        return fail(f"ISCC.exe exit {rc}")

    if not OUT_EXE.exists():
        return fail(f"Beklenen .exe oluşmadı: {OUT_EXE}")

    size_mb = OUT_EXE.stat().st_size / (1024 * 1024)
    print()
    print("=" * 60)
    print(f" Hazır: {OUT_EXE}")
    print(f" Boyut: {size_mb:.1f} MB")
    print("=" * 60)
    print()
    print("Test: bu .exe'yi temiz bir Windows makinesine kopyala, çift tıkla.")
    print("Klasik Windows installer açılır → Konum seç → İlerleme barı →")
    print("Python+paketler+ClamAV+EasyOCR otomatik kurulur (5-15 dk) →")
    print("Masaüstü kısayolu hazır.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
