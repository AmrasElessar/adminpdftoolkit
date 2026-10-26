"""``python -m adminpdf`` — run the server with the configured host/port."""

from __future__ import annotations

import argparse
import secrets
import sys
import threading
import webbrowser

import uvicorn

from .config import Settings, get_settings


def _tls(settings: Settings) -> tuple[str, str, str | None]:
    """``(certfile, keyfile, ca_fingerprint)``, creating certificates as needed."""
    if settings.tls_cert_file and settings.tls_key_file:
        return str(settings.tls_cert_file), str(settings.tls_key_file), None
    from .core import tls

    hosts = [h.strip() for h in settings.allowed_hosts.split(",") if h.strip()]
    files = tls.ensure(settings.tls_dir, hosts)
    return str(files.cert), str(files.key), files.fingerprint


def _trust_once(settings: Settings, fingerprint: str) -> None:
    """On the desktop launch, ask the OS once to trust our CA, so this PC's
    browser opens the app without a certificate warning."""
    from .core import tls

    marker = settings.tls_dir / f"trusted-{fingerprint.replace(':', '')[:16]}"
    if marker.exists():
        return
    marker.touch()
    if tls.trust_ca(settings.tls_dir / "ca.crt"):
        print("  Sertifika bu bilgisayarda güvenilir olarak eklendi. / Certificate trusted on this computer.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="adminpdf", description="Admin PDF Toolkit server")
    parser.add_argument("--open", action="store_true", help="open the app in the default browser")
    parser.add_argument("--lan", action="store_true", help="listen on the local network with a one-time pairing key")
    parser.add_argument(
        "--trust-ca", action="store_true", help="trust this server's certificate authority on this computer, then exit"
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.lan:
        settings.host = "0.0.0.0"
        settings.lan_enabled = True
        if not settings.pairing_key:
            settings.pairing_key = secrets.token_urlsafe(16)

    ssl: dict[str, str] = {}
    fingerprint = None
    if settings.tls:
        cert, key, fingerprint = _tls(settings)
        from .core.tls import CIPHERS

        ssl = {"ssl_certfile": cert, "ssl_keyfile": key, "ssl_ciphers": CIPHERS}
    else:
        print(
            "\n  UYARI / WARNING: HTTPS kapalı (APT_TLS=false) — yalnızca kendi TLS vekil sunucunuzun"
            " arkasında kullanın. / Only use behind your own TLS proxy."
        )

    if args.trust_ca:
        from .core import tls

        if not settings.tls or fingerprint is None:
            sys.exit("Kendi sertifikanız kullanılıyor; yerel CA yok. / Using your own certificate; no local CA.")
        ok = tls.trust_ca(settings.tls_dir / "ca.crt")
        print(f"  CA: {settings.tls_dir / 'ca.crt'}\n  SHA-256: {fingerprint}")
        sys.exit(0 if ok else 1)

    if fingerprint:
        print(f"\n  HTTPS sertifika parmak izi / certificate fingerprint (SHA-256):\n    {fingerprint}")
        print(f"  CA dosyası / CA file: {settings.tls_dir / 'ca.crt'}")
    if args.lan:
        print("\n  Yerel ağ eşleştirme / local-network pairing (yalnızca aynı ağdaki cihazlar / same network only):")
        from .core.security import lan_urls

        for url in lan_urls(settings):
            print(f"    {url}")
        print("  Telefon/tablet: uygulamada sağ üstteki 'Cihaz bağla' QR kodunu okutun.")
        print("  Phone/tablet: scan the QR code under 'Connect a device' in the app.")
    print()

    if args.open:
        if fingerprint and sys.platform in ("win32", "darwin"):
            _trust_once(settings, fingerprint)
        url = f"{settings.scheme}://localhost:{settings.port}/"
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
        **ssl,  # type: ignore[arg-type]
    )


if __name__ == "__main__":
    main()
