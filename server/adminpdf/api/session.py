"""Session bootstrap: CSRF token and LAN pairing."""

from __future__ import annotations

import hmac
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..config import VERSION, Settings
from ..core.security import CSRF_COOKIE, SESSION_COOKIE, SESSION_TTL_SECONDS, SessionRegistry, lan_urls
from . import deps

router = APIRouter(prefix="/api/session", tags=["session"])


@router.get("")
def get_session(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(deps.settings)],
    sessions: Annotated[SessionRegistry, Depends(deps.sessions)],
) -> dict[str, object]:
    token = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
    response.set_cookie(CSRF_COOKIE, token, httponly=True, samesite="strict", secure=request.url.scheme == "https")
    local = deps.is_local(request)
    return {
        "version": VERSION,
        "csrf": token,
        "local": local,
        "paired": local or sessions.valid(request.cookies.get(SESSION_COOKIE)),
        "lan_enabled": settings.lan_enabled,
        "tls": settings.tls,
        "max_upload_mb": settings.max_upload_mb,
    }


class PairBody(BaseModel):
    key: str = Field(min_length=1, max_length=256)


@router.post("/pair")
def pair(
    body: PairBody,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(deps.settings)],
    sessions: Annotated[SessionRegistry, Depends(deps.sessions)],
) -> dict[str, bool]:
    client = request.client.host if request.client else "?"
    if not sessions.allow_attempt(client):
        raise HTTPException(status_code=429, detail="Too many attempts, wait a minute")

    if not settings.pairing_key or not hmac.compare_digest(
        body.key.encode("utf-8"), settings.pairing_key.encode("utf-8")
    ):
        raise HTTPException(status_code=403, detail="Invalid pairing key")
    sessions.reset_attempts(client)
    response.set_cookie(
        SESSION_COOKIE,
        sessions.create(),
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        max_age=SESSION_TTL_SECONDS,
    )
    return {"paired": True}


@router.get("/ca.crt")
def ca_certificate(settings: Annotated[Settings, Depends(deps.settings)]) -> FileResponse:
    """This server's local CA, to install on phones, tablets and other PCs.
    Public on purpose; compare its fingerprint with the one on the server."""
    path = settings.tls_dir / "ca.crt"
    if not settings.tls or not path.is_file():
        raise deps.not_found("No local certificate authority")
    return FileResponse(
        path,
        media_type="application/x-x509-ca-cert",
        filename="AdminPDFToolkit-CA.crt",
        headers={"cache-control": "no-store"},
    )


def _ca_fingerprint(settings: Settings) -> str | None:
    from cryptography import x509

    from ..core.tls import fingerprint

    try:
        return fingerprint(x509.load_pem_x509_certificate((settings.tls_dir / "ca.crt").read_bytes()))
    except (OSError, ValueError):
        return None


def _local_only(request: Request) -> None:
    if not deps.is_local(request):
        raise HTTPException(status_code=403, detail="Only on the server computer")


@router.get("/devices")
def devices(request: Request, settings: Annotated[Settings, Depends(deps.settings)]) -> dict[str, object]:
    """Pairing links for phones and tablets — shown only on the server PC."""
    _local_only(request)
    urls = lan_urls(settings) if settings.lan_enabled and settings.pairing_key else []
    return {
        "lan_enabled": settings.lan_enabled,
        "urls": urls,
        "tls": settings.tls,
        "fingerprint": _ca_fingerprint(settings) if settings.tls else None,
    }


@router.get("/devices/qr.svg")
def device_qr(request: Request, settings: Annotated[Settings, Depends(deps.settings)], i: int = 0) -> Response:
    """QR code of pairing link ``i``, so a phone can scan it from the screen."""
    import io

    import segno

    _local_only(request)
    urls = lan_urls(settings) if settings.lan_enabled and settings.pairing_key else []
    if not 0 <= i < len(urls):
        raise deps.not_found()
    buf = io.BytesIO()
    segno.make(urls[i], error="m").save(
        # Always dark on white: inverted codes defeat many phone scanners.
        buf,
        kind="svg",
        scale=6,
        border=3,
        dark="#000000",
        light="#ffffff",
        xmldecl=False,
    )
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"cache-control": "no-store"})
