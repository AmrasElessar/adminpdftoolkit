"""Request-level security, applied to every request as one ASGI middleware.

Checks, in order:

1. Host allow-list — defeats DNS rebinding (a hostile page resolving its own
   name to 127.0.0.1 and reading our API same-origin).
2. Client access — loopback is always allowed; other clients need LAN mode
   enabled and a session cookie obtained by pairing.
3. CSRF — unsafe methods on ``/api`` must carry ``X-CSRF-Token`` equal to the
   ``apt_csrf`` cookie. A custom header forces a CORS preflight, and we never
   answer preflights, so a cross-site page cannot forge it. A present
   ``Origin`` must also match this server exactly (scheme, host and port).

Every response gets strict security headers.
"""

from __future__ import annotations

import hmac
import ipaddress
import secrets
import socket
from collections.abc import Awaitable, Callable, MutableMapping
from http.cookies import SimpleCookie
from typing import Any

from ..config import Settings

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

CSRF_COOKIE = "apt_csrf"
CSRF_HEADER = "x-csrf-token"
SESSION_COOKIE = "apt_session"

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Paths a non-paired LAN client may reach (the pairing flow itself).
PAIRING_PATHS = frozenset({"/api/session", "/api/session/pair"})

SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (
        b"content-security-policy",
        b"default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; "
        b"style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
        b"font-src 'self' data:; worker-src 'self' blob:; connect-src 'self'; "
        b"object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
    ),
]


def is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def parse_networks(spec: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    nets = []
    for part in spec.split(","):
        if part.strip():
            nets.append(ipaddress.ip_network(part.strip(), strict=False))
    return nets


def in_networks(host: str | None, nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network]) -> bool:
    if not host or not nets:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in n for n in nets)


def local_addresses() -> set[str]:
    """IP addresses of this machine, used to accept ``Host: <lan-ip>``."""
    addrs: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            addrs.add(str(info[4][0]))
    except OSError:
        pass
    # The UDP connect trick reveals the default-route interface without
    # sending a packet.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            addrs.add(s.getsockname()[0])
        except OSError:
            pass
    return addrs


def split_host(host_header: str) -> str:
    """``example:8000`` → ``example``; ``[::1]:8000`` → ``::1``."""
    host = host_header.strip().lower()
    if host.startswith("["):
        return host[1 : host.find("]")] if "]" in host else host
    if host.count(":") == 1:
        return host.split(":", 1)[0]
    return host


class SessionRegistry:
    """In-memory set of paired LAN sessions. Restart = re-pair, by design."""

    def __init__(self) -> None:
        self._ids: set[str] = set()

    def create(self) -> str:
        sid = secrets.token_urlsafe(32)
        self._ids.add(sid)
        return sid

    def valid(self, sid: str | None) -> bool:
        return bool(sid) and sid in self._ids

    def clear(self) -> None:
        self._ids.clear()


def _cookies(scope: Scope) -> dict[str, str]:
    for name, value in scope.get("headers", []):
        if name == b"cookie":
            jar: SimpleCookie = SimpleCookie()
            try:
                jar.load(value.decode("latin-1"))
            except Exception:
                return {}
            return {k: m.value for k, m in jar.items()}
    return {}


def _header(scope: Scope, name: bytes) -> str | None:
    for k, v in scope.get("headers", []):
        if k == name:
            return str(v.decode("latin-1"))
    return None


class SecurityMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings, sessions: SessionRegistry) -> None:
        self.app = app
        self.settings = settings
        self.sessions = sessions
        self.allowed_hosts = {"localhost", "127.0.0.1", "::1"} | {
            h.strip().lower() for h in settings.allowed_hosts.split(",") if h.strip()
        }
        if settings.lan_enabled or settings.trusted_networks:
            self.allowed_hosts |= local_addresses()
        self.trusted = parse_networks(settings.trusted_networks)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            # No websocket endpoints exist; refuse rather than half-check.
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        error = self._check(scope)
        if error is not None:
            status, detail = error
            await _send_error(send, status, detail)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                headers.extend(h for h in SECURITY_HEADERS if h[0] not in present)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _check(self, scope: Scope) -> tuple[int, str] | None:
        host_header = _header(scope, b"host") or ""
        if split_host(host_header) not in self.allowed_hosts:
            return 400, "Host not allowed"

        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")
        cookies = _cookies(scope)
        client = scope.get("client")
        client_host = client[0] if client else None

        if not is_loopback(client_host) and not in_networks(client_host, self.trusted):
            if not self.settings.lan_enabled:
                return 403, "LAN access is disabled"
            if path not in PAIRING_PATHS and not self.sessions.valid(cookies.get(SESSION_COOKIE)):
                return 401, "Pairing required"

        if path.startswith("/api") and method not in SAFE_METHODS:
            origin = _header(scope, b"origin")
            if origin is not None:
                scheme = scope.get("scheme", "http")
                if origin.lower() != f"{scheme}://{host_header.lower()}":
                    return 403, "Cross-origin request rejected"
            token = _header(scope, CSRF_HEADER.encode())
            cookie = cookies.get(CSRF_COOKIE)
            if not token or not cookie or not hmac.compare_digest(token.encode(), cookie.encode()):
                return 403, "CSRF token missing or invalid"
        return None


async def _send_error(send: Send, status: int, detail: str) -> None:
    import json

    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                *SECURITY_HEADERS,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
