"""Shared request dependencies."""

from __future__ import annotations

from fastapi import HTTPException, Request

from ..config import Settings
from ..core.files import FileStore
from ..core.security import SessionRegistry
from ..jobs.engine import JobEngine


def settings(request: Request) -> Settings:
    s: Settings = request.app.state.settings
    return s


def store(request: Request) -> FileStore:
    s: FileStore = request.app.state.store
    return s


def engine(request: Request) -> JobEngine:
    e: JobEngine = request.app.state.engine
    return e


def sessions(request: Request) -> SessionRegistry:
    r: SessionRegistry = request.app.state.sessions
    return r


def owner(request: Request) -> str:
    """Who files and jobs belong to: "local" or one id per paired device.
    Set by the security middleware; absent only on the pairing endpoints."""
    o: str | None = getattr(request.state, "apt_owner", None)
    if not o:
        raise HTTPException(status_code=401, detail="Pairing required")
    return o


def is_loopback(request: Request) -> bool:
    """This very machine (no proxy in between), per the security middleware."""
    return bool(getattr(request.state, "apt_loopback", False))


def is_local(request: Request) -> bool:
    return bool(getattr(request.state, "apt_local", False))


def not_found(what: str = "Not found") -> HTTPException:
    return HTTPException(status_code=404, detail=what)
