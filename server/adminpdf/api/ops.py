"""Operation catalogue and job submission."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError

from ..core.files import FileStore, MissingFileError
from ..jobs.engine import JobEngine
from ..ops.base import REGISTRY, file_params
from . import deps

router = APIRouter(prefix="/api/ops", tags=["ops"])


@router.get("")
def catalogue() -> list[dict[str, Any]]:
    return [cls.describe() for cls in REGISTRY.values()]


class InputRef(BaseModel):
    id: str = Field(max_length=64)
    password: str = Field("", max_length=256)


class RunBody(BaseModel):
    inputs: list[InputRef] = Field(max_length=1000)
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/{name}", status_code=202)
async def run(
    name: str,
    body: RunBody,
    store: Annotated[FileStore, Depends(deps.store)],
    engine: Annotated[JobEngine, Depends(deps.engine)],
) -> dict[str, Any]:
    op = REGISTRY.get(name)
    if op is None:
        raise deps.not_found("Unknown operation")
    if not op.min_inputs <= len(body.inputs) <= op.max_inputs:
        raise HTTPException(
            status_code=422,
            detail=f"{op.name} needs {op.min_inputs}–{op.max_inputs} input files, got {len(body.inputs)}",
        )
    inputs = []
    for ref in body.inputs:
        try:
            meta = store.get(ref.id)
            path = store.path(ref.id)
        except MissingFileError:
            raise deps.not_found("Input file not found (it may have expired)") from None
        if meta.kind not in op.accepts:
            raise HTTPException(status_code=415, detail=f"{meta.name}: {op.name} does not accept {meta.kind} files")
        inputs.append((path, meta.name, ref.password))
    try:
        params = op.Params.model_validate(body.params)
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=[{"field": ".".join(map(str, err["loc"])), "message": err["msg"]} for err in e.errors()],
        ) from None
    files: dict[str, tuple[Path, str]] = {}
    for field_name, accept in file_params(op.Params).items():
        file_id = getattr(params, field_name, "")
        if not file_id:
            continue
        try:
            meta = store.get(file_id)
            files[field_name] = (store.path(file_id), meta.name)
        except MissingFileError:
            raise deps.not_found(f"{field_name}: file not found (it may have expired)") from None
        if accept and meta.kind not in accept:
            raise HTTPException(status_code=415, detail=f"{field_name}: expected {', '.join(accept)}, got {meta.kind}")
    job = engine.submit(op.name, params.model_dump(mode="json"), inputs, files)
    return job.public()
