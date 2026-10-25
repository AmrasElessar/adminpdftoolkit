"""Job status, live progress (SSE) and cancellation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ..jobs.engine import TERMINAL, Job, JobEngine
from . import deps

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

HEARTBEAT_SECONDS = 15.0


def _job(job_id: str, engine: JobEngine) -> Job:
    job = engine.get(job_id)
    if job is None:
        raise deps.not_found("Job not found")
    return job


@router.get("/{job_id}")
def status(job_id: str, engine: Annotated[JobEngine, Depends(deps.engine)]) -> dict[str, Any]:
    return _job(job_id, engine).public()


@router.get("/{job_id}/events")
async def events(
    job_id: str, request: Request, engine: Annotated[JobEngine, Depends(deps.engine)]
) -> StreamingResponse:
    job = _job(job_id, engine)

    async def stream() -> AsyncIterator[str]:
        seen = -1
        while True:
            if job.version != seen:
                seen = job.version
                yield f"data: {json.dumps(job.public())}\n\n"
                if job.status in TERMINAL:
                    return
            else:
                yield ": keep-alive\n\n"
            if await request.is_disconnected():
                return
            await engine.wait_change(job, seen, HEARTBEAT_SECONDS)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"cache-control": "no-store", "x-accel-buffering": "no"},
    )


@router.post("/{job_id}/cancel")
async def cancel(job_id: str, engine: Annotated[JobEngine, Depends(deps.engine)]) -> dict[str, Any]:
    job = _job(job_id, engine)
    await engine.cancel(job_id)
    return job.public()
