"""Build a native Windows .exe launcher for the portable distribution.

Pipeline:
    1. ``python build_portable.py``  -> dist/Admin_PDF_Toolkit_Portable/
       (embeddable Python, all packages, app code, .bat launcher)
    2. ``python build_exe.py``       -> drops "Admin PDF Toolkit.exe" into that
       folder. The .exe is a small (~10 MB) PyInstaller-compiled wrapper around
       launcher.py. It finds the bundled python/ next to itself and runs app.py.

The portable folder layout, the .bat launcher, package versions, and the
ClamAV / EasyOCR bundles all stay untouched. The .exe is an additional clickable
entry point, not a replacement.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORTABLE = ROOT / "dist" / "Admin_PDF_Toolkit_Portable"
LAUNCHER = ROOT / "launcher.py"
EXE_NAME = "Admin PDF Toolkit"
BUILD_DIR = ROOT / "build" / "_pyinstaller"
DIST_DIR = ROOT / "build" / "_pyinstaller_dist"


def _ensure_pyinstaller() -> bool:
    try:
        import PyInstaller  # noqa: F401

        return True
    except ImportError:
        print(">>> PyInstaller bulunamadi, kuruluyor...")
        rc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"],
        ).returncode
        return rc == 0


def _ensure_tray_deps() -> bool:
    """pystray + Pillow — tray icon + image rendering."""
    missing: list[str] = []
    try:
        import pystray  # noqa: F401
    except ImportError:
        missing.append("pystray>=0.19")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("Pillow>=10.0")
    if not missing:
        return True
    print(f">>> Tray bagimliliklari kuruluyor: {missing}")
    rc = subprocess.run(
        [sys.executable, "-m", "pip", "install", *missing],
    ).returncode
    return rc == 0


def main() -> int:
    if not LAUNCHER.exists():
        print(f"HATA: {LAUNCHER} bulunamadi.")
        return 1
    if not PORTABLE.exists():
        print(f"HATA: {PORTABLE} bulunamadi.")
        print("      Once 'python build_portable.py' calistirin.")
        return 1
    if not (PORTABLE / "python" / "python.exe").exists():
        print(f"HATA: {PORTABLE / 'python' / 'python.exe'} yok - portable build eksik.")
        return 1

    if not _ensure_pyinstaller():
        print("HATA: PyInstaller kurulamadi.")
        return 1
    if not _ensure_tray_deps():
        print("HATA: pystray/Pillow kurulamadi.")
        return 1

    for d in (BUILD_DIR, DIST_DIR):
        if d.exists():
            shutil.rmtree(d)

    # Windows Explorer "Properties → Details" pane reads VS_VERSIONINFO
    # from the .exe's PE header. ``--version-file`` is how PyInstaller
    # embeds those strings (CompanyName=D Brand, ProductName etc).
    version_info = ROOT / "launcher_version_info.txt"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--noconsole",  # tray app — no console window
        "--name",
        EXE_NAME,
        "--workpath",
        str(BUILD_DIR),
        "--distpath",
        str(DIST_DIR),
        "--specpath",
        str(BUILD_DIR),
        "--noconfirm",
        "--hidden-import",
        "pystray._win32",
        "--collect-submodules",
        "pystray",
    ]
    if version_info.is_file():
        cmd += ["--version-file", str(version_info)]
    cmd.append(str(LAUNCHER))

    print(">>> PyInstaller calisiyor...")
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        print(f"HATA: PyInstaller basarisiz (exit {rc}).")
        return rc

    src_exe = DIST_DIR / f"{EXE_NAME}.exe"
    if not src_exe.exists():
        print(f"HATA: Beklenen .exe olusmadi: {src_exe}")
        return 1

    target = PORTABLE / f"{EXE_NAME}.exe"
    shutil.copy2(src_exe, target)
    size_mb = target.stat().st_size / (1024 * 1024)

    print()
    print("=" * 60)
    print(f" Hazir: {target}")
    print(f" Boyut: {size_mb:.1f} MB")
    print("=" * 60)
    print()
    print("Kullanim: portable klasordeki .exe'ye cift tikla. Sunucu baslar,")
    print("tarayici http://127.0.0.1:8000 acilir. .bat launcher de duruyor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
