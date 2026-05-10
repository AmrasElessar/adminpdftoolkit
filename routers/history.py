"""History router — list / clear the conversion audit log.

Backed by the SQLite DB owned by ``state.HISTORY_DB_PATH`` (single source
of truth, see S1). All writes happen via ``core.log_history``; this router
only reads + bulk-deletes.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Request

import core
from core import _history_lock, init_history_db, logger
from state import HISTORY_DB_PATH

router = APIRouter()


@router.get("/history")
async def history(limit: int = 100) -> dict:
    limit = max(1, min(int(limit), 500))
    init_history_db()  # idempotent — guarantees table exists for first call
    with _history_lock:
        conn = sqlite3.connect(str(HISTORY_DB_PATH))
        try:
            cur = conn.execute(
                "SELECT id, ts, ip, action, target, filename, record_count, note "
                "FROM history ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    items = [
        {
            "id": r[0],
            "ts": r[1],
            "ip": r[2],
            "action": r[3],
            "target": r[4],
            "filename": r[5],
            "record_count": r[6],
            "note": r[7],
        }
        for r in rows
    ]
    return {"items": items, "count": len(items)}


@router.delete("/history")
async def history_clear(request: Request) -> dict:
    """Wipe the audit log. Mutating + destructive — requires loopback origin.

    The audit trail is the only record of who used the tool. A cross-origin
    CSRF that wipes it would let an attacker cover their tracks after
    forcing other endpoints. We require both ``is_local_request`` (so a
    remote caller without a token can't reach it) and an origin that
    matches the server (so a hostile page in the operator's own browser
    can't trigger it via cross-origin DELETE either).
    """
    if not core.is_local_request(request):
        raise HTTPException(403, "Geçmişi silmek yalnızca sunucu makinesinden yapılabilir.")
    core.assert_same_origin(request)
    init_history_db()
    with _history_lock:
        conn = sqlite3.connect(str(HISTORY_DB_PATH))
        conn.execute("DELETE FROM history")
        conn.commit()
        conn.close()
    logger.info("history wiped — caller=%s", core.client_ip(request))
    return {"ok": True}
