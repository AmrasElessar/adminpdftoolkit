"""Upload, download and delete files."""

from __future__ import annotations

import asyncio
from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse

from ..core.files import FileStore, MissingFileError, UploadTooLargeError
from . import deps

router = APIRouter(prefix="/api/files", tags=["files"])


@router.put("", status_code=201)
async def upload(
    request: Request,
    store: Annotated[FileStore, Depends(deps.store)],
    x_filename: Annotated[str, Header(max_length=1024)] = "file",
    content_length: Annotated[int | None, Header()] = None,
) -> dict[str, object]:
    """Raw-body upload. The client sends the bytes as the request body and the
    (URI-encoded) name in ``X-Filename``; the size cap is enforced while
    streaming, before anything is fully buffered."""
    if content_length is not None and content_length > store.max_bytes:
        raise HTTPException(status_code=413, detail="File too large")
    try:
        meta = await store.save_stream(unquote(x_filename), request.stream())
    except UploadTooLargeError:
        raise HTTPException(status_code=413, detail="File too large") from None
    if meta.size == 0:
        store.delete(meta.id)
        raise HTTPException(status_code=400, detail="Empty file")
    if meta.kind == "pdf":
        meta = await asyncio.get_running_loop().run_in_executor(None, store.probe, meta)
    return meta.public()


@router.get("/{file_id}/meta")
def file_meta(file_id: str, store: Annotated[FileStore, Depends(deps.store)]) -> dict[str, object]:
    try:
        return store.get(file_id).public()
    except MissingFileError:
        raise deps.not_found() from None


@router.get("/{file_id}")
def download(file_id: str, store: Annotated[FileStore, Depends(deps.store)], inline: bool = False) -> FileResponse:
    try:
        meta = store.get(file_id)
        path = store.path(file_id)
    except MissingFileError:
        raise deps.not_found() from None
    return FileResponse(
        path,
        media_type=meta.mime,
        filename=meta.name,
        content_disposition_type="inline" if inline else "attachment",
    )


@router.delete("/{file_id}", status_code=204)
def delete(file_id: str, store: Annotated[FileStore, Depends(deps.store)]) -> None:
    try:
        store.get(file_id)
    except MissingFileError:
        raise deps.not_found() from None
    store.delete(file_id)
