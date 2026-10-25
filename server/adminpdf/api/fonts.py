"""Font catalogue for the editor and font files for WYSIWYG preview."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from ..core.fonts import get_catalogue, style_bytes
from . import deps

router = APIRouter(prefix="/api/fonts", tags=["fonts"])

_STYLE_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")
_CACHE = "private, max-age=86400"


@router.get("")
def catalogue() -> list[dict[str, Any]]:
    """Every family the editor can use: PDF standard fonts, bundled fonts
    and fonts installed on the server. Restricted-licence families are
    listed (``restricted: true``) but cannot be embedded or downloaded."""
    return get_catalogue().public()


@router.get("/{style_id}/file")
def font_file(style_id: str) -> Response:
    """The font program of one style, for ``new FontFace(...)``. Style ids
    are opaque catalogue keys — paths are never accepted."""
    if not _STYLE_ID.fullmatch(style_id):
        raise deps.not_found()
    style = get_catalogue().style(style_id)
    if style is None or not style.has_file:
        raise deps.not_found()
    if style.restricted:
        raise HTTPException(status_code=403, detail="Font licence does not allow redistribution")
    path = Path(style.path)
    head = b""
    try:
        with path.open("rb") as f:
            head = f.read(4)
    except OSError:
        raise deps.not_found() from None
    if head == b"ttcf":
        # A collection: hand the browser the single face, rebuilt standalone.
        try:
            data = style_bytes(style)
        except (OSError, ValueError):
            raise deps.not_found() from None
        mime = "font/otf" if data[:4] == b"OTTO" else "font/ttf"
        return Response(data, media_type=mime, headers={"cache-control": _CACHE})
    mime = "font/otf" if head == b"OTTO" else "font/ttf"
    return FileResponse(path, media_type=mime, headers={"cache-control": _CACHE})
