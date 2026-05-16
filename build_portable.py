"""
Admin PDF Toolkit — Portable Build Script (by Engin)
====================================================

Adımlar:
1. Python 3.13 embeddable indir + aç
2. python313._pth dosyasını TAM olarak ayarla (eksik satırlar yüzünden pip'in
   ana paketleri yükleyememesi sorununu çözer)
3. pip kur (get-pip.py)
4. Bağımlılıkları paket-paket kur, her paketten sonra "yüklü mü?" doğrula
5. EasyOCR modellerini önceden indir
6. Proje dosyalarını kopyala
7. Bütünlük kontrolü — kritik paketler yoksa fail et
8. Başlat.bat ve KULLANIM.txt yaz

Çıktı: dist/Admin_PDF_Toolkit_Portable/
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

# Force UTF-8 stdout so "✓" and Turkish chars render on cp1254 consoles.
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        with contextlib.suppress(Exception):
            _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist" / "Admin_PDF_Toolkit_Portable"

PY_VERSION = "3.13.0"
EMBED_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

# Build araçları + uygulama bağımlılıkları. Uygulama paketleri requirements.txt'ten
# okunur; build araçları (pip, setuptools, wheel) embeddable Python için ek olarak.
BUILD_TOOLS = ["pip", "setuptools", "wheel"]


def _read_requirements() -> list[str]:
    req_file = ROOT / "requirements.txt"
    if not req_file.exists():
        return []
    pkgs: list[str] = []
    for line in req_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("-r "):
            pkgs.append(line)
    return pkgs


PACKAGES = BUILD_TOOLS + _read_requirements()

# Build sonu doğrulaması — bu modüller import edilemiyorsa build başarısız sayılır
CRITICAL_IMPORTS = [
    "fitz",  # pymupdf
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


def step(msg: str) -> None:
    print(f"\n{'=' * 60}\n>>> {msg}\n{'=' * 60}")


def info(msg: str) -> None:
    print(f"    {msg}")


def fail(msg: str) -> int:
    print(f"\n[HATA] {msg}")
    return 1


def download(url: str, dest: Path) -> bool:
    info(f"İndiriliyor: {url}")
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception as e:
        info(f"İndirme hatası: {e}")
        return False


def setup_python_embed(py_dir: Path) -> bool:
    embed_zip = DIST / "_python_embed.zip"
    if not download(EMBED_URL, embed_zip):
        return False
    info("Açılıyor...")
    with zipfile.ZipFile(embed_zip) as zf:
        zf.extractall(py_dir)
    embed_zip.unlink(missing_ok=True)

    # ._pth dosyasını TAM olarak yeniden yaz (eksik satırlar pip'i kırıyor)
    pth_files = list(py_dir.glob("python*._pth"))
    if not pth_files:
        info("UYARI: ._pth dosyası bulunamadı, manual oluşturuluyor.")
        pth = py_dir / "python313._pth"
    else:
        pth = pth_files[0]

    pth_content = "python313.zip\n.\nLib\\site-packages\n\nimport site\n"
    pth.write_text(pth_content, encoding="utf-8")
    info(f"._pth ayarlandı: {pth.name}")
    return True


def _isolated_env() -> dict[str, str]:
    """USER site-packages'ı görünmez yapan, embedded Python'un kendi site'ına
    yazmasını zorlayan ortam değişkenleri."""
    env = os.environ.copy()
    # USER site-packages tamamen devre dışı
    env["PYTHONNOUSERSITE"] = "1"
    # Mevcut Python kurulumunun yollarını/cache'ini izole et
    env.pop("PYTHONUSERBASE", None)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def install_pip(py_exe: Path, py_dir: Path) -> bool:
    get_pip = py_dir / "get-pip.py"
    if not download(GET_PIP_URL, get_pip):
        return False
    info("pip kuruluyor (izole)...")
    rc = subprocess.run(
        [str(py_exe), str(get_pip), "--no-warn-script-location"],
        cwd=py_dir,
        env=_isolated_env(),
    ).returncode
    get_pip.unlink(missing_ok=True)
    if rc != 0:
        return False
    rc = subprocess.run(
        [str(py_exe), "-m", "pip", "--version"],
        env=_isolated_env(),
    ).returncode
    return rc == 0


def install_package(py_exe: Path, pkg: str) -> bool:
    info(f"Kuruluyor: {pkg}")
    cmd = [
        str(py_exe),
        "-m",
        "pip",
        "install",
        "--isolated",  # kullanıcı config / env yok say
        "--no-user",  # USER site'a yazma
        "--ignore-installed",  # 'zaten yüklü' mantığını bypass et (kritik!)
        "--no-warn-script-location",
        "--no-cache-dir",
        "--disable-pip-version-check",
        pkg,
    ]
    rc = subprocess.run(cmd, env=_isolated_env()).returncode
    if rc != 0:
        info(f"  → BAŞARISIZ: {pkg}")
        return False
    return True


def verify_imports(py_exe: Path, modules: list[str]) -> tuple[bool, list[str]]:
    """Modüllerin import edilebildiğini doğrular. Eksik olanları döndürür.
    İzole ortamda çağrılır — USER site-packages görünmez."""
    missing: list[str] = []
    env = _isolated_env()
    for m in modules:
        rc = subprocess.run(
            [str(py_exe), "-c", f"import {m}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        ).returncode
        if rc != 0:
            missing.append(m)
    return (len(missing) == 0, missing)


def download_easyocr_models(py_exe: Path, models_dir: Path) -> bool:
    models_dir.mkdir(exist_ok=True)
    user_net = models_dir / "user_network"
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


def ensure_editor_assets() -> None:
    """Make sure ``static/pdfjs/`` + ``static/fonts/`` are populated before copy.

    Runs ``scripts/setup_editor_assets.py`` if either directory is empty.
    Both are git-ignored so a fresh clone needs this bootstrap.
    """
    pdfjs = ROOT / "static" / "pdfjs"
    fonts = ROOT / "static" / "fonts"
    if (pdfjs.exists() and any(pdfjs.iterdir())) and (fonts.exists() and any(fonts.iterdir())):
        info("  ✓ editor assets already in place")
        return
    info("  ↓ fetching editor assets (pdf.js + Noto/DejaVu)…")
    setup = ROOT / "scripts" / "setup_editor_assets.py"
    if not setup.exists():
        info("  ! scripts/setup_editor_assets.py not found — skipping")
        return
    rc = subprocess.run([sys.executable, str(setup)], cwd=str(ROOT)).returncode
    if rc != 0:
        info(f"  ! setup_editor_assets exit code {rc} — continuing without assets")


def copy_project(dist: Path) -> None:
    ensure_editor_assets()
    files = [
        "app.py",
        "app_http.py",
        "state.py",
        "settings.py",
        "pdf_converter.py",
        "pdf_safety.py",
        "requirements.txt",
        "LICENSE",
        "NOTICE.txt",
        "THIRD_PARTY_LICENSES.md",
        "README.md",
    ]
    for f in files:
        src = ROOT / f
        if src.exists():
            shutil.copy(src, dist / f)
            info(f"  ✓ {f}")
    dirs = ["core", "routers", "pipelines", "parsers", "templates", "static", "tests", "scripts"]
    for d in dirs:
        src = ROOT / d
        if src.exists():
            target = dist / d
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
            info(f"  ✓ {d}/")

    # Auto-bundle ClamAV: binaries + signature DB so end users don't need
    # internet on first boot. setup_clamav.py is idempotent — it skips if
    # everything's already in place.
    clamav_src = ROOT / "clamav"
    setup = ROOT / "scripts" / "setup_clamav.py"
    needs_clamav = (
        not (clamav_src / "clamscan.exe").exists() or not (clamav_src / "database").exists()
    )
    if needs_clamav and setup.exists():
        info("  ↓ ClamAV (binaries + signature DB) indiriliyor (~350 MB)…")
        rc = subprocess.run([sys.executable, str(setup)], cwd=str(ROOT)).returncode
        if rc != 0:
            info(f"  ! setup_clamav.py exit {rc} — ClamAV atlandi")
    if (clamav_src / "clamscan.exe").exists():
        target = dist / "clamav"
        if target.exists():
            shutil.rmtree(target)
        # Bundle the database/ subdir too — first boot stays offline.
        shutil.copytree(
            clamav_src,
            target,
            ignore=shutil.ignore_patterns("_download.zip"),
        )
        has_db = (target / "database").exists() and any((target / "database").iterdir())
        info(f"  ✓ clamav/ (binaries{' + signature DB' if has_db else ''})")
    else:
        info("  · clamav/ skipped (setup_clamav.py bulunamadi veya basarisiz)")


def write_starter_bat(dist: Path) -> None:
    bat = r"""@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Admin PDF Toolkit - Sunucu

set "PYTHONHOME="
REM PYTHONPATH: kaynak kod dizini (app.py icin) + site-packages
set "PYTHONPATH=%~dp0;%~dp0python\Lib\site-packages"
set "PATH=%~dp0python;%~dp0python\Scripts;%PATH%"

echo.
echo ============================================================
echo   Admin PDF Toolkit by Engin
echo   Portable Surum - Kurulum gerekmez
echo ============================================================
echo.

start "" /min cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8000"

"%~dp0python\python.exe" "%~dp0app.py"

echo.
echo Sunucu durdu. Kapatmak icin bir tusa basin...
pause >nul
"""
    (dist / "Admin PDF Toolkit Baslat.bat").write_text(bat, encoding="utf-8")


def write_readme(dist: Path) -> None:
    readme = """Admin PDF Toolkit - Portable Sürüm (by Engin)
=============================================

Tek tıkla çalıştırma: "Admin PDF Toolkit Baslat.bat" üzerine çift tıklayın.

NOT:
- Hiçbir kurulum gerekmez (Python da dahil her şey bu klasörde).
- Yönetici izni gerekmez.
- Tarayıcı otomatik açılır (https://127.0.0.1:8000).
- Telefondan kullanmak için aynı Wi-Fi'da olun, sunucu ekranında
  yazan LAN adresine tarayıcıdan girin.

ILK GIRISTE GUVENLIK UYARISI:
=============================
Sunucu kendinden imzali (self-signed) HTTPS sertifikasi kullanir.
Ilk girise tarayici "guvenli degil" diyebilir. BU NORMALDIR.

  Chrome / Edge :  Gelismis -> Yine de devam et
  Firefox       :  Gelismis -> Riski kabul et ve devam et
  Safari (iOS)  :  Ayrintilari Goster -> Bu siteyi ziyaret et
  Android Chrome:  Gelismis -> Yine de devam et

Bir kez kabul edince tarayici hatirlar, sonraki girislerde uyari cikmaz.
Trafik yine de uctan uca sifrelenmistir.

INDIRME UYARISI:
================
Mobilde nadiren "guvenli olarak indirilemedi" uyarisi cikabilir.
"Sakla" veya "Yine de indir" secenegine basin — dosya kendi sunucunuzdan
iniyor, guvenli.

ANA EKRANA EKLEME (PWA):
=========================
iOS Safari    : Paylas -> Ana Ekrana Ekle
Android Chrome: 3 nokta -> Ana Ekrana Ekle / Uygulamayi Yukle

Uygulama ikonuyla acilir, tarayici cubugu gorunmez.

Klasoru silmek = uygulamayi tamamen kaldirmak demektir.

Admin PDF Toolkit · by Engin
Lisans: GNU AGPL-3.0
"""
    (dist / "KULLANIM.txt").write_text(readme, encoding="utf-8")


def write_hashes(dist: Path) -> None:
    """BT'ye verilebilecek SHA-256 hash listesi."""
    targets = [
        dist / "Admin PDF Toolkit Baslat.bat",
        dist / "app.py",
        dist / "pdf_converter.py",
        dist / "python" / "python.exe",
    ]
    lines = ["Admin PDF Toolkit — SHA-256 Hash Listesi", "=" * 60, ""]
    for t in targets:
        if not t.exists():
            continue
        h = hashlib.sha256(t.read_bytes()).hexdigest()
        rel = t.relative_to(dist).as_posix()
        lines.append(f"{h}  {rel}")
    lines.append("")
    lines.append("Doğrulama: 'certutil -hashfile <dosya> SHA256' veya")
    lines.append("           PowerShell 'Get-FileHash <dosya> -Algorithm SHA256'")
    (dist / "HASHES.txt").write_text("\n".join(lines), encoding="utf-8")
    info("HASHES.txt yazıldı (BT için).")


def main() -> int:
    print("=" * 60)
    print(" Admin PDF Toolkit — Portable Build (by Engin)")
    print("=" * 60)

    if DIST.exists():
        step(f"Eski {DIST.name} klasörü siliniyor...")
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    py_dir = DIST / "python"
    py_dir.mkdir()
    py_exe = py_dir / "python.exe"

    # 1. Python embeddable
    step(f"Python {PY_VERSION} embeddable kurulumu")
    if not setup_python_embed(py_dir):
        return fail("Python embeddable kurulamadı.")

    # 2. pip
    step("pip kurulumu")
    if not install_pip(py_exe, py_dir):
        return fail("pip kurulamadı.")

    # 3. Bağımlılıklar — paket paket kur
    step("Bağımlılıklar kuruluyor (paket paket, ~1-2 GB)")
    failed: list[str] = []
    for pkg in PACKAGES:
        if pkg == "pip":
            # pip kendisi zaten kurulu — sadece güncelle (izole)
            subprocess.run(
                [
                    str(py_exe),
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "--isolated",
                    "--no-user",
                    "--ignore-installed",
                    "--no-warn-script-location",
                    "pip",
                ],
                env=_isolated_env(),
            )
            continue
        if not install_package(py_exe, pkg):
            failed.append(pkg)
    if failed:
        info(f"Başarısız paketler: {failed}")
        info("Yeniden deneniyor...")
        retry_failed = []
        for pkg in failed:
            if not install_package(py_exe, pkg):
                retry_failed.append(pkg)
        if retry_failed:
            return fail(f"Şu paketler kurulamadı: {retry_failed}")

    # 4. Doğrulama — kritik modüller import edilebiliyor mu?
    step("Bütünlük kontrolü (kritik modüller)")
    ok, missing = verify_imports(py_exe, CRITICAL_IMPORTS)
    if not ok:
        return fail(
            f"Kritik modüller import edilemiyor: {missing}\n"
            "Build BAŞARISIZ. Yukarıdaki pip çıktısını inceleyin."
        )
    info(f"Tüm {len(CRITICAL_IMPORTS)} kritik modül OK.")

    # 5. EasyOCR modelleri
    step("EasyOCR modelleri indiriliyor (~500 MB)")
    models_dir = DIST / "_EasyOCR_models"
    if not download_easyocr_models(py_exe, models_dir):
        info("UYARI: EasyOCR modelleri indirilemedi. İlk OCR'da indirilir (internet gerekir).")

    # 6. Proje dosyalarını kopyala
    step("Proje dosyaları kopyalanıyor")
    copy_project(DIST)

    # 7. Başlat.bat + KULLANIM.txt + HASHES.txt
    step("Yardımcı dosyalar yazılıyor")
    write_starter_bat(DIST)
    write_readme(DIST)
    write_hashes(DIST)

    # 8. Boyut
    step("Hazır.")
    total_mb = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file()) / (1024 * 1024)
    info(f"Klasör: {DIST}")
    info(f"Boyut : ~{total_mb:.0f} MB")
    if total_mb < 800:
        info("UYARI: Boyut beklenenden küçük (< 800 MB). EasyOCR/PyTorch eksik olabilir.")
    print()
    print("=" * 60)
    print(" Sıradaki adım: bu klasörü ZIP'le ve hedef PC'ye kopyala.")
    print(" Hedef PC'de ZIP'i aç, 'Admin PDF Toolkit Baslat.bat'a tıkla.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
