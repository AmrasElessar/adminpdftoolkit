"""Application factory."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from .config import VERSION, Settings, get_settings
from .core.files import FileStore
from .core.security import SecurityMiddleware, SessionRegistry
from .jobs.engine import JobEngine
from .ops.base import load_all

log = logging.getLogger("adminpdf")

SWEEP_INTERVAL_SECONDS = 300


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
                    await asyncio.get_running_loop().run_in_executor(None, store.sweep)
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
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.sessions = sessions

    from .api import files, jobs, ops, session

    for r in (session.router, files.router, ops.router, jobs.router):
        app.include_router(r)

    @app.get("/api/health", tags=["session"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": VERSION}

    _mount_web(app, settings.web_dist)
    app.add_middleware(SecurityMiddleware, settings=settings, sessions=sessions)
    return app


def _mount_web(app: FastAPI, dist: Path) -> None:
    """Serve the built Svelte app with an SPA fallback to ``index.html``."""
    dist = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str, request: Request) -> Response:
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        index = dist / "index.html"
        if not index.is_file():
            return JSONResponse(
                {"detail": "Web UI not built. Run `npm run build` in v2/web."},
                status_code=503,
            )
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist):
            # Vite emits content-hashed names under assets/ — cache forever.
            immutable = candidate.parent.name == "assets"
            return FileResponse(
                candidate,
                headers={"cache-control": "public, max-age=31536000, immutable" if immutable else "no-cache"},
            )
        return FileResponse(index, headers={"cache-control": "no-cache"})
