"""
Admin PDF Toolkit — Local Web Server
------------------------------------
Runs on the local/corporate network. Accessible from mobile and desktop browsers.
Uploaded files never leave the machine.

Start with:  python app.py   (or:  ht-pdf,  or one of the bundled .bat scripts)

After the S5 split this file is just the bootstrap — the FastAPI app
instance, the lifespan handler, the mobile-auth middleware, the public
index/health endpoints, and ``main()``. Every endpoint cluster lives
under ``routers/``; every worker lives under ``pipelines/``; every shared
HTTP helper lives in ``app_http``.
"""

from __future__ import annotations

__version__ = "1.11.0"
__author__ = "Orhan Engin Okay"
__license__ = "AGPL-3.0-or-later"

# Embedded/portable Python'da script dizini sys.path'e otomatik eklenmiyor.
# Bu yüzden pdf_converter import edilemiyor. Manuel olarak ekleyelim.
import contextlib
import os as _bootstrap_os
import sys as _bootstrap_sys

_HERE = _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))
if _HERE not in _bootstrap_sys.path:
    _bootstrap_sys.path.insert(0, _HERE)

# Windows console default'u cp1254/cp857; UTF-8'e zorla, böylece print'lerde
# Türkçe karakterler ve ℹ/✓ gibi Unicode'lar bozulmaz, UnicodeEncodeError atmaz.
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(_bootstrap_sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        with contextlib.suppress(Exception):
            _stream.reconfigure(encoding="utf-8", errors="replace")

import hmac
import mimetypes
import os
import shutil
import socket
import threading
import time
from contextlib import asynccontextmanager, suppress
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Register MIME types for ES modules + bundled fonts BEFORE StaticFiles is
# mounted. Browsers refuse to load <script type="module"> over text/plain
# (which is what some Windows installs return for unknown extensions),
# silently swallowing the error in DevTools.
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("font/otf", ".otf")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("font/woff2", ".woff2")

import core
import state as state_mod
from core import logger
from pdf_converter import CALL_LOG_QUESTIONS
from settings import settings
from state import (
    MAX_UPLOAD_MB,
    STATIC_DIR,
    TEMPLATES_DIR,
    WORK_DIR,
    batch_jobs,
    batch_lock,
    convert_jobs,
    convert_lock,
    ocr_jobs,
    ocr_lock,
)

# Mirror to core so the process-pool worker (parse_pdf_for_batch) sees the
# call-log target schema without importing the FastAPI app file.
core.TARGET_SCHEMA = ["Müşteri", "Telefon", "Durum", "Tarih", "Süre", *CALL_LOG_QUESTIONS]


def _prewarm_caches() -> None:
    """Eagerly hit the lazy caches that otherwise stall the first request.

    - ``_find_unicode_font`` walks 9-11 candidate font paths on first call.
    - ``_patch_pisa_for_local_fonts`` patches xhtml2pdf + reportlab; the
      idempotent guard means subsequent renders are free, but the first one
      pays the import cost of xhtml2pdf.context / reportlab.pdfbase.
    - ``_ensure_pisa_unicode_font`` resolves and caches the family name.
    - ``discover_system_fonts`` walks every system font dir + parses each
      TTF's name table — 100-300ms on Windows with a stocked font folder.

    Running them in a daemon thread so an unexpected stall doesn't block
    the HTTP listener from coming up.
    """
    try:
        from core.converters import _ensure_pisa_unicode_font, _patch_pisa_for_local_fonts
        from core.fonts import discover_system_fonts
        from core.pdf_tools import _find_unicode_font

        _find_unicode_font()
        _patch_pisa_for_local_fonts()
        _ensure_pisa_unicode_font()
        discover_system_fonts()
        logger.debug("font caches pre-warmed")
    except Exception as e:
        logger.debug("font cache pre-warm skipped: %s", e)


def _maybe_update_clamav() -> None:
    """Throttled signature refresh on a daemon thread.

    No-op when ClamAV isn't bundled (i.e. ``./clamav/freshclam.exe`` missing).
    Honours the 24 h throttle so frequent app restarts don't hammer the
    mirror. App keeps serving while freshclam runs; ClamAV scans return
    None (graceful skip) until the database lands.
    """
    try:
        from core.clamav_update import maybe_update

        result = maybe_update()
        if result is not None:
            if result["ok"]:
                logger.info("clamav signatures refreshed in %.1fs", result["took_s"])
            else:
                logger.warning("clamav refresh failed: %s", result.get("error"))
    except Exception as e:
        logger.debug("clamav refresh skipped: %s", e)


def _start_clamd_after_signatures() -> None:
    """Wait for freshclam to land the signature DB, then spawn clamd daemon.

    Daemon mode keeps signatures resident in RAM, dropping per-scan overhead
    from 5-15 s (clamscan reloads DB every call) to ~100 ms (clamdscan talks
    to a hot daemon over loopback TCP).
    """
    try:
        # Give freshclam a head start on cold boot. ensure_clamd_running()
        # gracefully returns False if the DB isn't there yet, and the next
        # actual scan will retry.
        import time as _t

        from core.clamav_daemon import ensure_clamd_running

        _t.sleep(3.0)
        ensure_clamd_running(boot_timeout=25.0)
    except Exception as e:
        logger.debug("clamd autostart skipped: %s", e)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    logger.info("Admin PDF Toolkit v%s starting", __version__)
    core.startup_cleanup()
    core.init_history_db()
    threading.Thread(target=core.cleanup_loop, daemon=True).start()
    threading.Thread(target=_prewarm_caches, daemon=True).start()
    threading.Thread(target=_maybe_update_clamav, daemon=True).start()
    threading.Thread(target=_start_clamd_after_signatures, daemon=True).start()
    if settings.preload_ocr_model:
        threading.Thread(target=core.preload_ocr_in_background, daemon=True).start()
    yield
    logger.info("Admin PDF Toolkit shutting down")
    try:
        from core.clamav_daemon import stop_clamd

        stop_clamd()
    except Exception as e:
        logger.debug("clamd stop on shutdown: %s", e)


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Offline PDF → Excel / Word / JPG / OCR converter with web UI.",
    lifespan=_lifespan,
    docs_url=settings.docs_url,
    redoc_url=settings.redoc_url,
    openapi_url="/openapi.json" if settings.docs_url else None,
    contact={
        "name": "Orhan Engin Okay",
        "url": "https://github.com/orhanenginokay/pdfconverter",
    },
    license_info={
        "name": "AGPL-3.0-or-later",
        "url": "https://www.gnu.org/licenses/agpl-3.0.html",
    },
)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Mount every router-based endpoint group. The split is documented in
# ``routers/__init__.py``; new endpoints should land in (or get a new file
# under) ``routers/`` rather than this bootstrap.
from routers import ALL as _ROUTERS

for _r in _ROUTERS:
    app.include_router(_r)


# ---------------------------------------------------------------------------
# Mobile / LAN access control — middleware. Default state (mobile_token ==
# None) only lets loopback through; the user explicitly opens mobile access
# via the local UI, which mints a token that remote clients must present on
# every request.
# ---------------------------------------------------------------------------
_MOBILE_PUBLIC_PATHS: tuple[str, ...] = (
    "/",
    "/static/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/admin/mobile-status",
    "/favicon.ico",
)


def _is_mobile_public(path: str) -> bool:
    """Public paths bypass the mobile-auth middleware. ``"/"`` matches
    exactly (not as a prefix) — otherwise every request would be public.
    """
    for p in _MOBILE_PUBLIC_PATHS:
        if p == "/":
            if path == "/":
                return True
        elif path == p or path.startswith(p):
            return True
    return False


@app.middleware("http")
async def _mobile_auth_middleware(request: Request, call_next):
    """Block remote clients unless they present the live mobile token.

    Local clients always pass; remote clients are accepted only when (1)
    a mobile_token has been issued by the local user, AND (2) they carry
    a matching ``X-Mobile-Key`` header (or ``?key=``). Constant-time
    compare via ``hmac.compare_digest`` defeats timing attacks.
    """
    path = request.url.path
    if _is_mobile_public(path):
        return await call_next(request)
    if core.is_local_request(request):
        return await call_next(request)
    with state_mod.mobile_token_lock:
        token = state_mod.mobile_token
    if not token:
        return JSONResponse(
            {"detail": "Mobil erişim kapalı. Sunucu makinesinden açılmalı."},
            status_code=403,
        )
    provided = request.headers.get("x-mobile-key") or request.query_params.get("key", "")
    if not provided or not hmac.compare_digest(str(provided), token):
        return JSONResponse(
            {"detail": "Geçersiz veya eksik mobil erişim anahtarı."},
            status_code=403,
        )
    return await call_next(request)


# ---------------------------------------------------------------------------
# Public landing + health endpoints — kept on the app instance because
# they're trivial and used directly by Docker / ops.
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    scheme = "https" if request.url.scheme == "https" else "http"
    response = templates.TemplateResponse(
        request,
        "index.html",
        {
            "max_mb": MAX_UPLOAD_MB,
            "lan_ip": core.lan_ip(),
            "port": int(os.environ.get("PORT", "8000")),
            "scheme": scheme,
        },
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


_PROCESS_STARTED_AT = time.time()


@app.get("/health")
async def health() -> dict:
    """Liveness/operational status — used by Docker HEALTHCHECK and ops dashboards."""
    work_bytes = 0
    work_files = 0
    try:
        for p in WORK_DIR.rglob("*"):
            if p.is_file():
                try:
                    work_bytes += p.stat().st_size
                    work_files += 1
                except OSError:
                    continue
    except Exception:
        pass

    free_bytes = None
    with suppress(Exception):
        free_bytes = shutil.disk_usage(str(WORK_DIR)).free

    with convert_lock:
        convert_running = sum(1 for j in convert_jobs.values() if not j.get("done"))
        convert_total = len(convert_jobs)
    with batch_lock:
        batch_running = sum(1 for j in batch_jobs.values() if not j.get("done"))
        batch_total = len(batch_jobs)
    with ocr_lock:
        ocr_running = sum(1 for j in ocr_jobs.values() if not j.get("done"))
        ocr_total = len(ocr_jobs)

    return {
        "ok": True,
        "version": __version__,
        "uptime_seconds": int(time.time() - _PROCESS_STARTED_AT),
        "thread_count": threading.active_count(),
        "work_dir_bytes": work_bytes,
        "work_dir_files": work_files,
        "disk_free_bytes": free_bytes,
        "jobs": {
            "convert": {"running": convert_running, "total": convert_total},
            "batch": {"running": batch_running, "total": batch_total},
            "ocr": {"running": ocr_running, "total": ocr_total},
        },
    }


def main() -> None:
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "8000"))
    use_https = os.environ.get("HTTPS", "0") in ("1", "true", "True", "yes")
    lan = core.lan_ip()
    scheme = "https" if use_https else "http"

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(0.3)
    try:
        probe.connect(("127.0.0.1", port))
        probe.close()
        print("=" * 60)
        print(f"  [UYARI] {port} portu zaten kullanımda.")
        print("  Sunucu muhtemelen zaten çalışıyor:")
        print(f"     {scheme}://127.0.0.1:{port}")
        print(f"     {scheme}://{lan}:{port}")
        print("  Yeni bir kopya başlatılmayacak. Pencereyi kapatabilirsiniz.")
        print("=" * 60)
        return
    except OSError:
        probe.close()

    cert_kwargs: dict[str, Any] = {}
    if use_https:
        try:
            cert_file, key_file = core.ensure_self_signed_cert()
            cert_kwargs = {
                "ssl_keyfile": str(key_file),
                "ssl_certfile": str(cert_file),
            }
        except Exception as e:
            logger.warning("HTTPS certificate generation failed, falling back to HTTP: %s", e)
            scheme = "http"
            use_https = False

    print("=" * 60)
    print("  Admin PDF Toolkit - Web Sunucusu (by Engin)")
    print("=" * 60)
    print(f"  Bu makineden  : {scheme}://127.0.0.1:{port}")
    print(f"  Ağdan (LAN)   : {scheme}://{lan}:{port}")
    print("  Telefondan aynı Wi-Fi'daysanız yukarıdaki LAN adresine girin.")
    if use_https:
        print()
        print("  ℹ İlk girişte tarayıcıda 'sertifika güvensiz' uyarısı çıkar:")
        print("     Chrome/Edge: 'Gelişmiş' → 'Yine de devam et / Devam et'")
        print("     Firefox    : 'Gelişmiş' → 'İstisna ekle'")
        print("     iOS Safari : 'Ayrıntıları Göster' → 'Bu siteyi ziyaret et'")
        print("  Bu uyarı self-signed (kendinden imzalı) sertifika için normaldir;")
        print("  trafik yine de uçtan uca şifrelenmiştir.")
    else:
        print()
        print("  ℹ HTTPS kapalı. Açmak için sunucuyu durdurup:")
        print("       set HTTPS=1   (Windows cmd)")
        print("       $env:HTTPS=1  (PowerShell)")
        print("     ile yeniden başlatın.")
    print("  Durdurmak için: Ctrl+C")
    print("=" * 60)
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,
        **cert_kwargs,
    )


if __name__ == "__main__":
    main()
