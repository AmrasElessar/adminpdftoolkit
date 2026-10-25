"""``python -m adminpdf`` — run the server with the configured host/port."""

from __future__ import annotations

import uvicorn

from .config import get_settings


def main() -> None:
    settings = get_settings()
    # Job state lives in this process: one worker by design. Parallelism comes
    # from the job engine's worker processes, not from uvicorn workers.
    uvicorn.run(
        "adminpdf.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        workers=1,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
