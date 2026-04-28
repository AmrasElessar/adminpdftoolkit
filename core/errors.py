"""Error sanitisation — strip internal paths before showing to clients."""

from __future__ import annotations

import re

_PATH_SCRUB_PATTERNS = [
    re.compile(r"[A-Za-z]:[\\/][^\s'\"]+"),               # Windows abs paths
    re.compile(r"/(?:home|root|tmp|var|opt)/[^\s'\"]+"),   # POSIX abs paths
    re.compile(r"File \"[^\"]+\""),                        # traceback "File ..." prefix
]
MAX_ERROR_CHARS = 200


def sanitize_error(exc: BaseException | str) -> str:
    """Return a short, leak-free error string safe to send to the client."""
    msg = str(exc).strip() if not isinstance(exc, str) else exc.strip()
    if not msg:
        return "İşlem başarısız."
    for pat in _PATH_SCRUB_PATTERNS:
        msg = pat.sub("<path>", msg)
    msg = re.sub(r"\s+", " ", msg).strip()
    if len(msg) > MAX_ERROR_CHARS:
        msg = msg[: MAX_ERROR_CHARS - 1].rstrip() + "…"
    return msg or "İşlem başarısız."
