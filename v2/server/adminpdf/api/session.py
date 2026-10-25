"""Session bootstrap: CSRF token and LAN pairing."""

from __future__ import annotations

import hmac
import secrets
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..config import VERSION, Settings
from ..core.security import CSRF_COOKIE, SESSION_COOKIE, SessionRegistry, is_loopback
from . import deps

router = APIRouter(prefix="/api/session", tags=["session"])

_PAIR_WINDOW_SECONDS = 60
_PAIR_MAX_ATTEMPTS = 5
_attempts: dict[str, deque[float]] = defaultdict(deque)


@router.get("")
def get_session(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(deps.settings)],
    sessions: Annotated[SessionRegistry, Depends(deps.sessions)],
) -> dict[str, object]:
    token = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
    response.set_cookie(CSRF_COOKIE, token, httponly=True, samesite="strict", secure=request.url.scheme == "https")
    client = request.client.host if request.client else None
    local = is_loopback(client)
    return {
        "version": VERSION,
        "csrf": token,
        "local": local,
        "paired": local or sessions.valid(request.cookies.get(SESSION_COOKIE)),
        "lan_enabled": settings.lan_enabled,
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
    now = time.monotonic()
    window = _attempts[client]
    while window and now - window[0] > _PAIR_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= _PAIR_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts, wait a minute")
    window.append(now)

    if not settings.pairing_key or not hmac.compare_digest(
        body.key.encode("utf-8"), settings.pairing_key.encode("utf-8")
    ):
        raise HTTPException(status_code=403, detail="Invalid pairing key")
    window.clear()
    response.set_cookie(
        SESSION_COOKIE,
        sessions.create(),
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        max_age=60 * 60 * 24 * 30,
    )
    return {"paired": True}
