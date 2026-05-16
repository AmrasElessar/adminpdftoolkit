"""Security primitives: token validation + SSRF guard."""

from __future__ import annotations

import re
import socket
from typing import Any

from fastapi import HTTPException

from .errors import sanitize_error

_TOKEN_RE = re.compile(r"^[a-f0-9]{32}$")


def check_token(token: str) -> None:
    """Raise 400 if `token` is not a valid uuid4 hex string."""
    if not _TOKEN_RE.fullmatch(token):
        raise HTTPException(400, "Geçersiz token formatı.")


def _assert_public_url(parsed: Any) -> None:
    """SSRF guard: reject URLs that resolve to private/loopback/link-local IPs.

    Resolves the hostname via getaddrinfo and inspects every returned address;
    if any is in a non-public range, the request is refused. Closes the door
    on attacks like ``http://169.254.169.254`` (cloud metadata),
    ``http://127.0.0.1:8000`` (own service), ``http://10.0.0.5`` (LAN).

    -- DNS rebinding (TOCTOU) — accepted residual risk --

    Between this resolution and the eventual ``urlopen()`` call, the DNS
    record for the hostname could change to a private IP (``rebinding``).
    Closing this window cleanly would require pinning the resolved IP and
    passing it to ``HTTPSConnection`` manually with the original hostname
    as the SNI / Host header — a non-trivial rewrite of every callsite
    (``url_to_pdf``, ``html_to_pdf`` redirect chain).

    We deliberately accept this residual risk for this app because:
      1. The HTTP listener binds to ``127.0.0.1`` by default (settings.host).
      2. ``/pdf/from-url`` is exposed only to the operator on the same
         machine, not to the internet.
      3. A successful rebind attack would let an internet site trick the
         operator's own server into fetching another internal URL — but
         the only "internal" target that matters here is this very app,
         and that's already reachable to the operator directly.

    If the app is ever reconfigured to bind to ``0.0.0.0`` and exposed
    behind a reverse proxy, this guard must be hardened: either disable
    the ``/pdf/from-url`` endpoint, restrict it to the admin role, or
    rewrite the fetch path to pin the resolved IP.
    """
    import ipaddress

    host = parsed.hostname
    if not host:
        raise ValueError("URL hostname'i çözümlenemedi.")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise ValueError(f"DNS çözümlenemedi: {sanitize_error(e)}") from e
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("İç ağ / loopback adreslerine istek engellendi.")
