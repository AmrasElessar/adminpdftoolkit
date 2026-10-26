"""``python -m adminpdf.selfcheck`` — check every component, one by one.

Prints one JSON object per line as each check finishes, so the Windows
launcher can tick them off live, then a final ``{"type": "done", ...}``:

    {"type": "check", "id": "python", "status": "ok", "title": {...}, "version": "3.13.1", ...}
    ...
    {"type": "done", "ready": true, "info": {...}}

``status`` is ``ok``, ``warn`` (works, with a caveat), ``missing`` (an
optional tool is absent; only its features are off) or ``error`` (the app
cannot start). Nothing here touches the network.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from importlib import import_module, metadata
from pathlib import Path
from typing import Any

from .config import VERSION, Settings, get_settings

Result = dict[str, Any]

# (import name, distribution, display name) — the libraries every tool relies on.
LIBRARIES = (
    ("pymupdf", "pymupdf", "PyMuPDF"),
    ("pikepdf", "pikepdf", "pikepdf / qpdf"),
    ("fastapi", "fastapi", "FastAPI"),
    ("uvicorn", "uvicorn", "Uvicorn"),
    ("pydantic", "pydantic", "Pydantic"),
    ("ocrmypdf", "ocrmypdf", "OCRmyPDF"),
    ("pyhanko", "pyhanko", "pyHanko"),
    ("cryptography", "cryptography", "cryptography"),
    ("PIL", "pillow", "Pillow"),
    ("cv2", "opencv-python-headless", "OpenCV"),
    ("docx", "python-docx", "python-docx"),
    ("openpyxl", "openpyxl", "openpyxl"),
    ("pdf2docx", "pdf2docx", "pdf2docx"),
    ("fontTools", "fonttools", "fontTools"),
    ("segno", "segno", "segno"),
)


def _text(tr: str, en: str) -> dict[str, str]:
    return {"tr": tr, "en": en}


def _result(
    cid: str, title: dict[str, str], status: str, version: str = "", detail: dict[str, str] | None = None
) -> Result:
    return {"type": "check", "id": cid, "title": title, "status": status, "version": version, "detail": detail or {}}


def _run_version(cmd: list[str], timeout: float = 20) -> str:
    """First non-empty output line of ``cmd`` (no console window on Windows)."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False, creationflags=flags)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    for line in (r.stdout + r.stderr).decode("utf-8", "replace").splitlines():
        if line.strip():
            return line.strip()[:120]
    return ""


def _install_hint(packages: dict[str, str]) -> str:
    """The command that installs a missing tool on this system."""
    if sys.platform == "darwin":
        return f" — brew install {packages['brew']}"
    if sys.platform.startswith("linux"):
        return f" — sudo apt install {packages['apt']} (Fedora: sudo dnf install {packages['dnf']})"
    return ""


_OCR_PACKAGES = {
    "brew": "tesseract tesseract-lang",
    "apt": "tesseract-ocr tesseract-ocr-tur",
    "dnf": "tesseract tesseract-langpack-tur",
}
_GS_PACKAGES = {"brew": "ghostscript", "apt": "ghostscript", "dnf": "ghostscript"}


def check_python(_s: Settings) -> Result:
    ok = sys.version_info >= (3, 11)
    embedded = (Path(sys.executable).parent / f"python{sys.version_info[0]}{sys.version_info[1]}._pth").exists()
    detail = (
        _text("Pakete gömülü", "Bundled with the package") if embedded else _text("Sistem Python'u", "System Python")
    )
    return _result("python", _text("Python", "Python"), "ok" if ok else "error", sys.version.split()[0], detail)


def check_libraries(_s: Settings) -> Result:
    missing, versions = [], []
    for module, dist, name in LIBRARIES:
        try:
            import_module(module)
        except Exception:
            missing.append(name)
            continue
        try:
            ver = metadata.version(dist)
        except metadata.PackageNotFoundError:
            ver = ""
        versions.append(f"{name} {ver}".strip())
    if missing:
        return _result(
            "libraries",
            _text("Kütüphaneler", "Libraries"),
            "error",
            "",
            _text(f"Eksik: {', '.join(missing)}", f"Missing: {', '.join(missing)}"),
        )
    return _result(
        "libraries",
        _text("Kütüphaneler", "Libraries"),
        "ok",
        f"{len(versions)}",
        _text(", ".join(versions), ", ".join(versions)),
    )


def check_web(s: Settings) -> Result:
    ok = (s.web_dist / "index.html").is_file()
    return _result(
        "web",
        _text("Arayüz", "Web UI"),
        "ok" if ok else "error",
        VERSION,
        {} if ok else _text("Arayüz derlenmemiş.", "The web UI is not built."),
    )


def check_ocr(_s: Settings) -> Result:
    from .core.tools import bundled_ocr
    from .ops.ocr import find_tesseract, tesseract_languages

    title = _text("OCR (Tesseract)", "OCR (Tesseract)")
    bundled, problem = bundled_ocr()
    if problem == "damaged":
        return _result(
            "ocr",
            title,
            "warn",
            "",
            _text(
                "Paketteki OCR dosyaları bozuk; 'OCR Onar' çalıştırın.",
                "The bundled OCR files are damaged; run 'OCR Onar'.",
            ),
        )
    exe = bundled or find_tesseract()
    if not exe:
        hint = _install_hint(_OCR_PACKAGES)
        return _result(
            "ocr", title, "missing", "", _text("Kurulu değil; OCR kapalı" + hint, "Not installed; OCR is off" + hint)
        )
    version = _run_version([exe, "--version"]).removeprefix("tesseract ").strip()
    langs = tesseract_languages()
    where = (
        _text("Pakete gömülü, doğrulandı", "Bundled, verified") if bundled else _text("Sistemde kurulu", "Installed")
    )
    if "tur" not in langs:
        return _result(
            "ocr", title, "warn", version, _text("Türkçe dil verisi yok.", "Turkish language data is missing.")
        )
    langs_text = "+".join(sorted(langs & {"tur", "eng", "osd"}))
    return _result("ocr", title, "ok", version, {k: f"{v} · {langs_text}" for k, v in where.items()})


def check_ghostscript(_s: Settings) -> Result:
    from .core.tools import bundled_ghostscript
    from .ops._ocrmypdf import find_ghostscript

    title = _text("Ghostscript (PDF/A)", "Ghostscript (PDF/A)")
    bundled, problem = bundled_ghostscript()
    if problem == "damaged":
        return _result(
            "ghostscript", title, "warn", "", _text("Paketteki dosyalar bozuk.", "The bundled files are damaged.")
        )
    exe = bundled or find_ghostscript()
    if not exe:
        return _result(
            "ghostscript",
            title,
            "missing",
            "",
            _text(
                "Kurulu değil; PDF/A kapalı" + _install_hint(_GS_PACKAGES),
                "Not installed; PDF/A is off" + _install_hint(_GS_PACKAGES),
            ),
        )
    where = (
        _text("Pakete gömülü, doğrulandı", "Bundled, verified") if bundled else _text("Sistemde kurulu", "Installed")
    )
    return _result("ghostscript", title, "ok", _run_version([exe, "--version"]), where)


def check_libreoffice(_s: Settings) -> Result:
    from .ops.office import find_soffice

    title = _text("LibreOffice (Office → PDF)", "LibreOffice (Office → PDF)")
    exe = find_soffice()
    if not exe:
        return _result(
            "libreoffice",
            title,
            "missing",
            "",
            _text("İsteğe bağlı; yoksa dahili basit motor kullanılır.", "Optional; the basic built-in engine is used."),
        )
    return _result("libreoffice", title, "ok", "", _text("Sistemde kurulu", "Installed"))


def check_clamav(_s: Settings) -> Result:
    title = _text("ClamAV (virüs taraması)", "ClamAV (virus scan)")
    exe = shutil.which("clamscan")
    if not exe:
        return _result("clamav", title, "missing", "", _text("İsteğe bağlı.", "Optional."))
    return _result("clamav", title, "ok", _run_version([exe, "--version"]), _text("Sistemde kurulu", "Installed"))


def check_certificate(s: Settings) -> Result:
    title = _text("HTTPS sertifikası", "HTTPS certificate")
    if not s.tls:
        return _result(
            "tls", title, "warn", "", _text("HTTPS kapalı (APT_TLS=false).", "HTTPS is off (APT_TLS=false).")
        )
    if s.tls_cert_file and s.tls_key_file:
        ok = s.tls_cert_file.is_file() and s.tls_key_file.is_file()
        return _result(
            "tls", title, "ok" if ok else "error", "", _text("Kurum sertifikası", "Organisation certificate")
        )
    from .core import tls

    hosts = [h.strip() for h in s.allowed_hosts.split(",") if h.strip()]
    try:
        files = tls.ensure(s.tls_dir, hosts)
    except OSError as e:
        return _result("tls", title, "error", "", _text(f"Oluşturulamadı: {e}", f"Could not create: {e}"))
    short = tls.short_fingerprint(files.fingerprint)
    return _result("tls", title, "ok", short, _text("Yerel CA, ad kısıtlı", "Local CA, name-constrained"))


def check_port(s: Settings) -> Result:
    title = _text(f"Bağlantı noktası {s.port}", f"Port {s.port}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", s.port))
        except OSError:
            return _result(
                "port",
                title,
                "warn",
                "",
                _text("Kullanımda — uygulama zaten açık olabilir.", "In use — the app may already be running."),
            )
    return _result("port", title, "ok", "", _text("Boş", "Free"))


def check_disk(s: Settings) -> Result:
    title = _text("Disk alanı", "Disk space")
    s.data_dir.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(s.data_dir).free / 1024**3
    status = "ok" if free_gb >= 2 else "warn"
    return _result("disk", title, status, f"{free_gb:.1f} GB", _text(str(s.data_dir), str(s.data_dir)))


def check_network(s: Settings) -> Result:
    from .core.security import is_private, local_addresses

    ips = sorted(a for a in local_addresses() if "." in a and not a.startswith("127.") and is_private(a))
    title = _text("Yerel ağ", "Local network")
    if not ips:
        return _result(
            "network",
            title,
            "warn",
            "",
            _text("Yerel ağ adresi yok; yalnızca bu bilgisayar.", "No local-network address; this computer only."),
        )
    return _result("network", title, "ok", ", ".join(ips), _text("Telefon/tablet bağlanabilir", "Phones can connect"))


CHECKS: tuple[Callable[[Settings], Result], ...] = (
    check_python,
    check_libraries,
    check_web,
    check_certificate,
    check_ocr,
    check_ghostscript,
    check_libreoffice,
    check_clamav,
    check_port,
    check_disk,
    check_network,
)


def run_checks(settings: Settings) -> Iterator[Result]:
    for check in CHECKS:
        try:
            # Libraries chatter on stdout while importing; keep it for JSON.
            with contextlib.redirect_stdout(sys.stderr):
                result = check(settings)
            yield result
        except Exception as e:  # a broken check must not hide the others
            name = check.__name__.removeprefix("check_")
            yield _result(name, _text(name, name), "error", "", _text(str(e)[:200], str(e)[:200]))


def info(settings: Settings, results: list[Result]) -> dict[str, Any]:
    from .core.security import lan_urls

    fingerprint = next((r["version"] for r in results if r["id"] == "tls"), "")
    return {
        "version": VERSION,
        "url": f"{settings.scheme}://localhost:{settings.port}/",
        "lan_urls": [u.split("#", 1)[0] for u in lan_urls(settings)],
        "data_dir": str(settings.data_dir.resolve()),
        "fingerprint": fingerprint,
    }


def main() -> None:
    # Output is ASCII-only JSON (\uXXXX escapes), so any console code page
    # (cp1252, cp857, …) carries Turkish text intact.
    settings = get_settings()
    results = []
    for result in run_checks(settings):
        results.append(result)
        print(json.dumps(result), flush=True)
        time.sleep(0.05)  # lets the launcher tick items one by one
    ready = not any(r["status"] == "error" for r in results)
    print(json.dumps({"type": "done", "ready": ready, "info": info(settings, results)}), flush=True)
    sys.exit(0 if ready else 1)


if __name__ == "__main__":
    main()
