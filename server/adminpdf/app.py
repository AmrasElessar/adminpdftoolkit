"""Application factory."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from functools import partial
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from .config import VERSION, Settings, get_settings
from .core.files import FileStore
from .core.security import SecurityMiddleware, SessionRegistry
from .jobs.engine import JobEngine
from .ops.base import load_all

log = logging.getLogger("adminpdf")

SWEEP_INTERVAL_SECONDS = 300
# Types the stdlib guesses wrong or not at all on some platforms (Windows
# registry overrides are a classic source of text/plain module scripts).
_MEDIA_TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".webmanifest": "application/manifest+json",
    ".wasm": "application/wasm",
    ".svg": "image/svg+xml",
    ".bcmap": "application/octet-stream",
    ".pfb": "application/octet-stream",
    ".txt": "text/plain; charset=utf-8",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    load_all()
    sessions = SessionRegistry()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store = FileStore(
            settings.files_dir,
            max_bytes=settings.max_upload_bytes,
            ttl_seconds=settings.file_ttl_minutes * 60,
            max_total_bytes=settings.max_storage_mb * 1024 * 1024,
        )
        engine = JobEngine(
            store,
            settings.jobs_dir,
            max_workers=settings.max_workers,
            timeout_seconds=settings.job_timeout_seconds,
            memory_mb=settings.worker_memory_mb,
        )
        app.state.store = store
        app.state.engine = engine

        async def sweeper() -> None:
            while True:
                await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
                try:
                    keep = engine.files_in_use()
                    await asyncio.get_running_loop().run_in_executor(None, partial(store.sweep, keep=keep))
                    engine.sweep(store.ttl_seconds)
                except Exception:
                    log.exception("sweep failed")

        task = asyncio.create_task(sweeper())
        try:
            yield
        finally:
            task.cancel()
            await engine.shutdown()

    app = FastAPI(
        title="Admin PDF Toolkit",
        version=VERSION,
        lifespan=lifespan,
        docs_url="/api/docs" if settings.api_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.api_docs else None,
    )
    app.state.settings = settings
    app.state.sessions = sessions

    from .api import files, fonts, jobs, ops, session

    for r in (session.router, files.router, ops.router, jobs.router, fonts.router):
        app.include_router(r)

    @app.get("/api/health", tags=["session"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": VERSION}

    @app.get("/api/about", tags=["session"])
    def about() -> dict[str, Any]:
        """Systems, first-run notes and every component with its licence."""
        from .about import about as collect

        return collect(settings.web_dist)

    _mount_web(app, settings.web_dist)
    app.add_middleware(SecurityMiddleware, settings=settings, sessions=sessions)
    return app


def _mount_web(app: FastAPI, dist: Path) -> None:
    """Serve the built Svelte app with an SPA fallback to ``index.html``."""
    dist = dist.resolve()

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def web(path: str, request: Request) -> Response:
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        index = dist / "index.html"
        if not index.is_file():
            return JSONResponse(
                {"detail": "Web UI not built. Run `npm run build` in web/."},
                status_code=503,
            )
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist):
            # Vite emits content-hashed names under assets/ — cache forever.
            immutable = candidate.parent.name == "assets"
            return FileResponse(
                candidate,
                media_type=_MEDIA_TYPES.get(candidate.suffix),
                headers={"cache-control": "public, max-age=31536000, immutable" if immutable else "no-cache"},
            )
        return FileResponse(index, headers={"cache-control": "no-cache"})
