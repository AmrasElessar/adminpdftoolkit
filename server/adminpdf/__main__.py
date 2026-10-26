"""``python -m adminpdf`` — run the server with the configured host/port."""

from __future__ import annotations

import argparse
import secrets
import threading
import webbrowser

import uvicorn

from .config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="adminpdf", description="Admin PDF Toolkit server")
    parser.add_argument("--open", action="store_true", help="open the app in the default browser")
    parser.add_argument("--lan", action="store_true", help="listen on the network with a one-time pairing key")
    args = parser.parse_args()

    settings = get_settings()
    if args.lan:
        settings.host = "0.0.0.0"
        settings.lan_enabled = True
        if not settings.pairing_key:
            settings.pairing_key = secrets.token_urlsafe(16)
        from .core.security import local_addresses

        ips = sorted(a for a in local_addresses() if "." in a and not a.startswith("127."))
        print("\n  LAN eşleştirme / pairing:")
        for ip in ips:
            print(f"    http://{ip}:{settings.port}/#pair={settings.pairing_key}")
        print()

    if args.open:
        url = f"http://127.0.0.1:{settings.port}/"
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()

    # Job state lives in this process: one worker by design. Parallelism comes
    # from the job engine's worker processes, not from uvicorn workers.
    uvicorn.run(
        "adminpdf.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        workers=1,
        proxy_headers=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
