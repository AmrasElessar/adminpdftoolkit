"""Admin router — mobile-access toggles, status endpoint, ClamAV control.

The mobile-auth middleware itself remains attached to the FastAPI app
instance (see ``app.py``); this router only carries the local-only admin
endpoints that issue / revoke / report the token.
"""
from __future__ import annotations

import os
import secrets
import threading

from fastapi import APIRouter, HTTPException, Request

import core
import state as state_mod
from core import logger


router = APIRouter(prefix="/admin")


@router.post("/enable-mobile")
async def enable_mobile(request: Request) -> dict:
    """Issue (or rotate) the mobile-access token. Local-only."""
    if not core.is_local_request(request):
        raise HTTPException(403, "Bu işlem yalnızca sunucu makinesinden yapılabilir.")
    token = secrets.token_urlsafe(32)
    with state_mod.mobile_token_lock:
        state_mod.mobile_token = token
    lan = core.lan_ip()
    port = int(os.environ.get("PORT", "8000"))
    use_https = os.environ.get("HTTPS", "0") in ("1", "true", "True", "yes")
    scheme = "https" if use_https else "http"
    url = f"{scheme}://{lan}:{port}/?key={token}"
    logger.info("Mobile access enabled — token issued (length=%d)", len(token))
    return {
        "enabled": True,
        "token": token,
        "url": url,
        "lan_ip": lan,
        "port": port,
        "scheme": scheme,
    }


@router.post("/disable-mobile")
async def disable_mobile(request: Request) -> dict:
    """Revoke the mobile-access token. Local-only. All remote clients
    immediately start getting 403 on protected endpoints."""
    if not core.is_local_request(request):
        raise HTTPException(403, "Bu işlem yalnızca sunucu makinesinden yapılabilir.")
    with state_mod.mobile_token_lock:
        state_mod.mobile_token = None
    logger.info("Mobile access disabled")
    return {"enabled": False}


@router.get("/mobile-status")
async def mobile_status(request: Request) -> dict:
    """Public — used by the frontend to decide which UI state to show.
    Doesn't leak the token itself."""
    with state_mod.mobile_token_lock:
        enabled = state_mod.mobile_token is not None
    return {
        "enabled": enabled,
        "is_local": core.is_local_request(request),
    }


# ---------------------------------------------------------------------------
# ClamAV signature-DB management
# ---------------------------------------------------------------------------
@router.get("/clamav")
async def clamav_status(request: Request) -> dict:
    """Report bundled-ClamAV state: binary present, DB age, last update."""
    if not core.is_local_request(request):
        raise HTTPException(403, "Bu işlem yalnızca sunucu makinesinden yapılabilir.")
    from core.clamav_update import status
    return status()


@router.post("/clamav-update")
async def clamav_update(request: Request) -> dict:
    """Manually trigger a freshclam run. Returns immediately; the actual
    download runs on a daemon thread so the request doesn't block for the
    duration of a 30+ second sig pull."""
    if not core.is_local_request(request):
        raise HTTPException(403, "Bu işlem yalnızca sunucu makinesinden yapılabilir.")
    from core.clamav_update import update_signatures, status

    pre = status()
    if not pre["bundled"]:
        return {"started": False, "reason": "ClamAV bundled değil — önce "
                "scripts/setup_clamav.py'i çalıştırın."}

    def _run() -> None:
        result = update_signatures()
        if result["ok"]:
            logger.info("manual clamav refresh ok in %.1fs", result["took_s"])
        else:
            logger.warning("manual clamav refresh failed: %s", result.get("error"))

    threading.Thread(target=_run, daemon=True).start()
    return {"started": True, "status": pre}
