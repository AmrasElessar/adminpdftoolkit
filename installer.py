"""Admin PDF Toolkit — End-User Setup (compiled into a Windows .exe).

What it does on the end-user's machine
======================================
1. Asks where to install (default: %LOCALAPPDATA%\\AdminPDFToolkit).
2. Extracts the bundled app code (zipped inside this .exe by build_installer.py).
3. Downloads Python 3.13 embeddable (~25 MB).
4. Installs pip + requirements.txt into the embedded Python (~500 MB-1 GB).
5. Downloads ClamAV binaries + signature DB (~350 MB).
6. Pre-fetches EasyOCR detection + recognition models (~500 MB).
7. Writes a desktop shortcut + Start Menu entry pointing at the bundled .exe.
8. Offers to launch the app.

After install, the target folder is the same layout as
``dist/Admin_PDF_Toolkit_Portable/`` — fully self-contained, no PATH munging,
no admin rights required.

This script is stdlib-only so the compiled installer .exe stays small.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# UTF-8 stdout for Turkish chars on cp1254 consoles.
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        with contextlib.suppress(Exception):
            _stream.reconfigure(encoding="utf-8", errors="replace")

PY_VERSION = "3.13.0"
EMBED_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

DEFAULT_INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AdminPDFToolkit"

APP_NAME = "Admin PDF Toolkit"
APP_BUNDLE_NAME = "app_bundle.zip"  # bundled by build_installer.py
LAUNCHER_BUNDLE_NAME = "Admin PDF Toolkit.exe"  # bundled launcher

# Critical modules — install fails loudly if any of these can't import.
CRITICAL_IMPORTS = [
    "fitz",
    "pdfplumber",
    "pdf2docx",
    "openpyxl",
    "fastapi",
    "uvicorn",
    "jinja2",
    "easyocr",
    "torch",
    "torchvision",
    "PIL",
    "numpy",
]


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def banner() -> None:
    print("=" * 64)
    print(f"  {APP_NAME} — Kurulum Sihirbazı")
    print("  by Engin · Portable kurulum, yönetici izni gerekmez")
    print("=" * 64)
    print()


def step(msg: str) -> None:
    print(f"\n>>> {msg}")


def info(msg: str) -> None:
    print(f"    {msg}")


def warn(msg: str) -> None:
    print(f"    UYARI: {msg}")


def fail(msg: str) -> int:
    print(f"\n[HATA] {msg}")
    print("\nKurulum tamamlanamadı. Tekrar denemek için kurulumu yeniden başlatın.")
    input("\nKapatmak için Enter'a basın...")
    return 1


def ask_install_dir() -> Path:
    print(f"Varsayılan kurulum klasörü: {DEFAULT_INSTALL_DIR}")
    print("(boş bırakıp Enter'a basarsanız varsayılan kullanılır)")
    raw = input("Farklı bir klasör isterseniz tam yolu girin: ").strip().strip('"')
    if not raw:
        return DEFAULT_INSTALL_DIR
    return Path(raw).expanduser().resolve()


def confirm(prompt: str, default: bool = True) -> bool:
    sfx = " [E/h]: " if default else " [e/H]: "
    ans = input(prompt + sfx).strip().lower()
    if not ans:
        return default
    return ans.startswith(("e", "y"))


# ---------------------------------------------------------------------------
# Download with progress
# ---------------------------------------------------------------------------


def download(url: str, dest: Path, label: str = "") -> bool:
    info(f"İndiriliyor: {label or url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            written = 0
            last_print = 0.0
            with dest.open("wb") as fp:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    fp.write(chunk)
                    written += len(chunk)
                    now = time.time()
                    if total and now - last_print > 0.2:
                        pct = written / total * 100
                        print(
                            f"\r      {written / 1e6:7.1f} / {total / 1e6:.1f} MB ({pct:5.1f}%)",
                            end="",
                            flush=True,
                        )
                        last_print = now
            if total:
                print()
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print()
        warn(f"indirme hatası: {e}")
        if dest.exists():
            with contextlib.suppress(Exception):
                dest.unlink()
        return False


# ---------------------------------------------------------------------------
# Resource access (works in frozen mode and dev mode)
# ---------------------------------------------------------------------------


def _bundled_path(name: str) -> Path:
    """Path to a resource bundled by PyInstaller (or alongside the script in dev)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / name
    return Path(__file__).resolve().parent / name


# ---------------------------------------------------------------------------
# Install steps
# ---------------------------------------------------------------------------


def extract_app_bundle(target: Path) -> bool:
    """Extract bundled app code (zipped by build_installer.py) into target/."""
    bundle = _bundled_path(APP_BUNDLE_NAME)
    if not bundle.exists():
        warn(f"{APP_BUNDLE_NAME} bulunamadı (installer hatalı paketlenmiş).")
        return False
    info(f"Uygulama kodu çıkarılıyor: {bundle.name}")
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle) as zf:
        zf.extractall(target)
    info("  ✓ kod yerleştirildi")
    return True


def copy_launcher_exe(target: Path) -> bool:
    """Drop the bundled launcher .exe into the install dir."""
    src = _bundled_path(LAUNCHER_BUNDLE_NAME)
    if not src.exists():
        warn("Launcher .exe bundle içinde yok — Baslat.bat kullanılacak.")
        return False
    shutil.copy2(src, target / LAUNCHER_BUNDLE_NAME)
    info(f"  ✓ {LAUNCHER_BUNDLE_NAME}")
    return True


def setup_python_embed(install_dir: Path) -> Path | None:
    """Download + unzip Python embeddable into install_dir/python."""
    py_dir = install_dir / "python"
    if (py_dir / "python.exe").exists():
        info("  ✓ python embed zaten kurulu, atlanıyor")
        return py_dir / "python.exe"
    py_dir.mkdir(parents=True, exist_ok=True)
    zip_path = install_dir / "_python_embed.zip"
    if not download(EMBED_URL, zip_path, label=f"Python {PY_VERSION} embeddable"):
        return None
    info("  açılıyor...")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(py_dir)
    zip_path.unlink(missing_ok=True)

    # Rewrite ._pth so pip + site-packages work
    pth_files = list(py_dir.glob("python*._pth"))
    pth = pth_files[0] if pth_files else (py_dir / "python313._pth")
    pth.write_text(
        "python313.zip\n.\nLib\\site-packages\n\nimport site\n",
        encoding="utf-8",
    )
    info("  ✓ python embeddable hazır")
    return py_dir / "python.exe"


def _isolated_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("PYTHONUSERBASE", None)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def install_pip(py_exe: Path) -> bool:
    info("pip kuruluyor...")
    get_pip = py_exe.parent / "get-pip.py"
    if not download(GET_PIP_URL, get_pip, label="get-pip.py"):
        return False
    rc = subprocess.run(
        [str(py_exe), str(get_pip), "--no-warn-script-location"],
        cwd=str(py_exe.parent),
        env=_isolated_env(),
    ).returncode
    get_pip.unlink(missing_ok=True)
    return rc == 0


def install_packages(py_exe: Path, requirements: Path) -> bool:
    info("Paketler kuruluyor (~500 MB-1 GB, requirements.txt'ten)...")
    cmd = [
        str(py_exe),
        "-m",
        "pip",
        "install",
        "--isolated",
        "--no-user",
        "--ignore-installed",
        "--no-warn-script-location",
        "--disable-pip-version-check",
        "-r",
        str(requirements),
    ]
    rc = subprocess.run(cmd, env=_isolated_env()).returncode
    return rc == 0


def verify_critical(py_exe: Path) -> tuple[bool, list[str]]:
    missing: list[str] = []
    env = _isolated_env()
    for m in CRITICAL_IMPORTS:
        rc = subprocess.run(
            [str(py_exe), "-c", f"import {m}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        ).returncode
        if rc != 0:
            missing.append(m)
    return (not missing, missing)


def setup_clamav(install_dir: Path, py_exe: Path) -> bool:
    """Run scripts/setup_clamav.py with the embedded Python."""
    setup = install_dir / "scripts" / "setup_clamav.py"
    if not setup.exists():
        warn("scripts/setup_clamav.py yok — ClamAV atlandı")
        return False
    info("ClamAV binaries + virüs imza DB indiriliyor (~350 MB)...")
    rc = subprocess.run(
        [str(py_exe), str(setup)],
        cwd=str(install_dir),
        env=_isolated_env(),
    ).returncode
    return rc == 0


def prefetch_easyocr(install_dir: Path, py_exe: Path) -> bool:
    info("EasyOCR modelleri indiriliyor (~500 MB)...")
    models_dir = install_dir / "_EasyOCR_models"
    user_net = models_dir / "user_network"
    models_dir.mkdir(exist_ok=True)
    user_net.mkdir(exist_ok=True)
    code = (
        "import easyocr; "
        f"easyocr.Reader(['tr','en'], gpu=False, verbose=False, "
        f"model_storage_directory=r'{models_dir}', "
        f"user_network_directory=r'{user_net}', "
        f"download_enabled=True)"
    )
    rc = subprocess.run([str(py_exe), "-c", code], env=_isolated_env()).returncode
    return rc == 0


def write_starter_bat(install_dir: Path) -> None:
    bat = r"""@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Admin PDF Toolkit - Sunucu

set "PYTHONHOME="
set "PYTHONPATH=%~dp0;%~dp0python\Lib\site-packages"
set "PATH=%~dp0python;%~dp0python\Scripts;%PATH%"

echo.
echo ============================================================
echo   Admin PDF Toolkit by Engin
echo ============================================================
echo.

start "" /min cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8000"

"%~dp0python\python.exe" "%~dp0app.py"

echo.
echo Sunucu durdu. Kapatmak icin bir tusa basin...
pause >nul
"""
    (install_dir / "Admin PDF Toolkit Baslat.bat").write_text(bat, encoding="utf-8")


def create_shortcuts(install_dir: Path) -> None:
    """Create Desktop + Start Menu shortcuts pointing at the launcher .exe."""
    target = install_dir / LAUNCHER_BUNDLE_NAME
    if not target.exists():
        target = install_dir / "Admin PDF Toolkit Baslat.bat"
    if not target.exists():
        warn("Kısayol hedefi bulunamadı, atlanıyor.")
        return

    desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    start_menu = (
        Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
    )

    for location, label in ((desktop, "masaüstü"), (start_menu, "başlat menüsü")):
        try:
            location.mkdir(parents=True, exist_ok=True)
            lnk = location / f"{APP_NAME}.lnk"
            ps = (
                f"$s = (New-Object -COM WScript.Shell).CreateShortcut('{lnk}'); "
                f"$s.TargetPath = '{target}'; "
                f"$s.WorkingDirectory = '{install_dir}'; "
                f"$s.Save()"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            info(f"  ✓ {label} kısayolu oluşturuldu")
        except Exception as e:
            warn(f"{label} kısayolu oluşturulamadı: {e}")


def launch(install_dir: Path) -> None:
    exe = install_dir / LAUNCHER_BUNDLE_NAME
    if not exe.exists():
        exe = install_dir / "Admin PDF Toolkit Baslat.bat"
    if not exe.exists():
        warn("Çalıştırılacak dosya bulunamadı.")
        return
    try:
        subprocess.Popen([str(exe)], cwd=str(install_dir))
        info("  ✓ uygulama başlatıldı")
    except Exception as e:
        warn(f"başlatılamadı: {e}")


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------


def main() -> int:
    banner()
    install_dir = ask_install_dir()
    print()
    print(f"Kurulum klasörü: {install_dir}")
    if install_dir.exists() and any(install_dir.iterdir()):
        print("  ! bu klasör boş değil — içine kurulum yapılacak")
    if not confirm("Devam edilsin mi?", default=True):
        print("Kurulum iptal edildi.")
        return 0

    install_dir.mkdir(parents=True, exist_ok=True)

    step("1/6 — Uygulama kodu çıkarılıyor")
    if not extract_app_bundle(install_dir):
        return fail("uygulama kodu çıkarılamadı")
    copy_launcher_exe(install_dir)

    step("2/6 — Python 3.13 embeddable")
    py_exe = setup_python_embed(install_dir)
    if py_exe is None:
        return fail("Python embeddable kurulamadı (internet?)")

    step("3/6 — pip kurulumu")
    if not install_pip(py_exe):
        return fail("pip kurulamadı")

    step("4/6 — Paketler (PyTorch + EasyOCR + FastAPI vs.)")
    requirements = install_dir / "requirements.txt"
    if not requirements.exists():
        return fail(f"{requirements} bulunamadı")
    if not install_packages(py_exe, requirements):
        return fail("paket kurulumu başarısız")
    ok, missing = verify_critical(py_exe)
    if not ok:
        return fail(f"kritik modüller import edilemiyor: {missing}")
    info(f"  ✓ {len(CRITICAL_IMPORTS)} kritik modül OK")

    step("5/6 — ClamAV antivirüs (binaries + virüs imza DB)")
    setup_clamav(install_dir, py_exe)  # non-fatal

    step("6/6 — EasyOCR yapay zeka modelleri")
    prefetch_easyocr(install_dir, py_exe)  # non-fatal

    step("Son dokunuşlar")
    write_starter_bat(install_dir)
    info("  ✓ Baslat.bat yazıldı")
    create_shortcuts(install_dir)

    total_mb = sum(f.stat().st_size for f in install_dir.rglob("*") if f.is_file()) / (1024 * 1024)

    print()
    print("=" * 64)
    print("  Kurulum tamamlandı.")
    print(f"  Klasör  : {install_dir}")
    print(f"  Boyut   : ~{total_mb:.0f} MB")
    print("  Kısayol : Masaüstü + Başlat Menüsü")
    print("=" * 64)
    print()

    if confirm("Şimdi başlatılsın mı?", default=True):
        launch(install_dir)

    print()
    input("Kurulumu kapatmak için Enter'a basın...")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nKurulum kullanıcı tarafından iptal edildi.")
        sys.exit(1)
