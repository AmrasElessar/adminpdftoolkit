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

    There's a small TOCTOU window between resolution and the eventual
    urlopen() call (DNS rebinding) — acceptable for our LAN-only deployment.
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
