"""Compile setup_offline.iss into AdminPDFToolkit_Setup_Offline.exe.

Differs from build_setup_inno.py: bundles the ENTIRE portable folder
(python/, clamav/, _EasyOCR_models/) inside the installer .exe, so no
network access is needed during install.

Target use: corporate / firewalled work PCs where pypi.org / GitHub
download paths are blocked. End user copies the .exe (via USB / OneDrive)
to the work PC and double-clicks. Output is ~700 MB - 1.4 GB depending on
how compressible the bundled wheels are.

Pipeline
--------
1. Verify portable folder exists (run build_portable.py first if missing).
2. Verify launcher tray .exe exists (run build_exe.py first if missing).
3. Locate ISCC.exe (Inno Setup compiler).
4. Run ISCC on setup_offline.iss. Compression takes ~5-10 min.

The online installer (setup.iss / AdminPDFToolkit_Setup.exe) is left
untouched — both can coexist for different distribution scenarios.
"""

# ruff: noqa: SIM112
# Windows env-var names are case-insensitive at the OS level; ProgramFiles /
# ProgramFiles(x86) are the names ``set`` prints in cmd.exe.

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
ISS_FILE = ROOT / "setup_offline.iss"
PORTABLE = ROOT / "dist" / "Admin_PDF_Toolkit_Portable"
LAUNCHER_EXE = ROOT / "build" / "_pyinstaller_dist" / "Admin PDF Toolkit.exe"
OUT_EXE = ROOT / "dist" / "AdminPDFToolkit_Setup_Offline.exe"


def info(msg: str) -> None:
    print(f"    {msg}")


def step(msg: str) -> None:
    print(f"\n>>> {msg}")


def fail(msg: str) -> int:
    print(f"\n[HATA] {msg}")
    return 1


def find_iscc() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        / "Inno Setup 6"
        / "ISCC.exe",
        Path.home() / "AppData" / "Local" / "Programs" / "Inno Setup 6" / "ISCC.exe",
    ]
    on_path = shutil.which("iscc") or shutil.which("ISCC")
    if on_path:
        candidates.insert(0, Path(on_path))
    for p in candidates:
        if p.exists():
            return p
    return None


def main() -> int:
    print("=" * 60)
    print(" Admin PDF Toolkit — OFFLINE Installer Build")
    print("=" * 60)

    step("Inno Setup compiler aranıyor")
    iscc = find_iscc()
    if iscc is None:
        return fail(
            "ISCC.exe bulunamadı. Inno Setup yükle:\n  winget install --id JRSoftware.InnoSetup"
        )
    info(f"ISCC: {iscc}")

    step("Tray launcher .exe hazır mı?")
    if not LAUNCHER_EXE.exists():
        return fail("Launcher .exe yok. Önce: python build_exe.py")
    info(f"launcher: {LAUNCHER_EXE.name}")

    step("Portable klasör + python + clamav + EasyOCR hazır mı?")
    required = [
        PORTABLE / "app.py",
        PORTABLE / "core",
        PORTABLE / "python" / "python.exe",
        PORTABLE / "clamav" / "clamscan.exe",
        PORTABLE / "_EasyOCR_models",
    ]
    missing = [p for p in required if not p.exists()]
    if missing:
        return fail(
            "Portable build eksik. Önce: python build_portable.py\n"
            "Eksikler:\n  " + "\n  ".join(str(p) for p in missing)
        )
    info("tüm bileşenler dist/Admin_PDF_Toolkit_Portable/ altında")

    step("ISCC.exe çalıştırılıyor (LZMA2/ultra64 — ~5-10 dakika)")
    info(f"script: {ISS_FILE.name}")
    rc = subprocess.run([str(iscc), str(ISS_FILE)], cwd=str(ROOT)).returncode
    if rc != 0:
        return fail(f"ISCC.exe exit {rc}")

    if not OUT_EXE.exists():
        return fail(f"Beklenen .exe oluşmadı: {OUT_EXE}")

    size_mb = OUT_EXE.stat().st_size / (1024 * 1024)
    print()
    print("=" * 60)
    print(f" Hazır: {OUT_EXE}")
    print(f" Boyut: {size_mb:.0f} MB")
    print("=" * 60)
    print()
    print("Dağıtım:")
    print("  1. Bu .exe'yi OneDrive / Sharepoint / USB ile iş PC'sine kopyala")
    print("  2. İş PC'sinde çift tıkla → klasik Windows wizard açılır")
    print("  3. Kurulum boyunca İNTERNET GEREKMEZ — her şey içeride")
    return 0


if __name__ == "__main__":
    sys.exit(main())
