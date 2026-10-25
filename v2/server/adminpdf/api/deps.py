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


def not_found(what: str = "Not found") -> HTTPException:
    return HTTPException(status_code=404, detail=what)
