"""FastAPI router modules.

Each submodule exposes a single ``router`` (an ``APIRouter`` instance) that
``app.py`` mounts at startup. The split is purely organisational — every
router can be lifted out into its own service later if a feature ever
needs to scale separately.

Routers (S5 split, 2026-04-28):

* ``history`` — conversion audit log (``/history`` GET/DELETE).
* ``admin``   — mobile-access toggles (``/admin/enable-mobile`` etc.).
* ``ocr``     — OCR pipeline endpoints.
* ``convert`` — single-PDF preview / sync / async convert + SSE.
* ``batch``   — batch (Excel merge + Word/JPG ZIP) endpoints.
* ``pdf_tools`` — every ``/pdf/*`` transform (merge / split / compress …
  + the batch dispatcher).
* ``editor``  — ``/pdf/edit/*`` (fonts / spans / save).
"""
from . import (  # noqa: F401  -- re-exported via include_router
    admin,
    batch,
    convert,
    editor,
    history,
    ocr,
    pdf_tools,
)

ALL = (
    history.router,
    admin.router,
    ocr.router,
    convert.router,
    batch.router,
    pdf_tools.router,
    editor.router,
)
