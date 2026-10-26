"""Request-level security, applied to every request as one ASGI middleware.

Checks, in order:

1. Host allow-list — defeats DNS rebinding (a hostile page resolving its own
   name to 127.0.0.1 and reading our API same-origin).
2. Client access — only this machine and devices on the local network
   (private and link-local addresses) are ever served; anything from a
   public address is refused, whatever the settings. Loopback is always allowed; other clients need LAN mode
   enabled and a session cookie obtained by pairing. A loopback request that
   carries proxy forwarding headers came through a reverse proxy, so it is
   treated as remote: a local nginx must not make the whole LAN "local".
3. CSRF — unsafe methods on ``/api`` must carry ``X-CSRF-Token`` equal to the
   ``apt_csrf`` cookie. A custom header forces a CORS preflight, and we never
   answer preflights, so a cross-site page cannot forge it. A present
   ``Origin`` must also match this server exactly (scheme, host and port).

Every response gets strict security headers; API responses are never cached.

The middleware also records who is asking in ``scope["state"]``: whether the
client is this machine, and the *owner* id that files and jobs are scoped to
("local" for this machine and trusted networks, one id per paired device), so
paired devices cannot reach each other's documents.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import secrets
import socket
import time
from collections import OrderedDict, deque
from collections.abc import Awaitable, Callable, MutableMapping
from http.cookies import SimpleCookie
from pathlib import Path
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
LOCAL_OWNER = "local"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30
MAX_SESSIONS = 1000
MIN_PAIRING_KEY_LENGTH = 12
# "gateway" in APT_TRUSTED_NETWORKS: this host's default gateway, i.e. the
# Docker host as seen from inside a container.
GATEWAY_KEYWORD = "gateway"
FORWARDING_HEADERS = (b"forwarded", b"x-forwarded-for", b"x-real-ip", b"x-forwarded-host")

log = logging.getLogger("adminpdf.security")

# The only addresses ever served: this machine and the local network.
PRIVATE_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = tuple(
    ipaddress.ip_network(n)
    for n in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)


def _ip(host: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not host:
        return None
    try:
        ip = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def is_private(host: str | None) -> bool:
    """A loopback, private (RFC 1918 / ULA) or link-local address."""
    ip = _ip(host)
    return ip is not None and any(ip in net for net in PRIVATE_NETWORKS)


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Paths a non-paired LAN client may reach (the pairing flow itself).
# The CA certificate is public: a phone must be able to fetch it before pairing.
PAIRING_PATHS = frozenset({"/api/session", "/api/session/pair", "/api/session/ca.crt"})

SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=()"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"x-permitted-cross-domain-policies", b"none"),
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
    ip = _ip(host)
    return ip is not None and ip.is_loopback


def default_gateway() -> str | None:
    """The IPv4 default gateway from ``/proc/net/route`` (Linux only)."""
    try:
        lines = Path("/proc/net/route").read_text(encoding="ascii").splitlines()[1:]
    except OSError:
        return None
    for line in lines:
        fields = line.split()
        if len(fields) > 2 and fields[1] == "00000000":
            return str(ipaddress.IPv4Address(bytes.fromhex(fields[2])[::-1]))
    return None


def parse_networks(spec: str, *, lan_enabled: bool = False) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    nets = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if part.lower() == GATEWAY_KEYWORD:
            # With LAN mode on, every device pairs — and on Docker Desktop all
            # published-port traffic arrives from the gateway, so trusting it
            # would let the whole network in without a key.
            gw = None if lan_enabled else default_gateway()
            if gw:
                nets.append(ipaddress.ip_network(f"{gw}/32"))
            continue
        net = ipaddress.ip_network(part, strict=False)
        if not any(net.version == p.version and net.subnet_of(p) for p in PRIVATE_NETWORKS):  # type: ignore[arg-type]
            raise ValueError(f"APT_TRUSTED_NETWORKS may only list local-network ranges, not {part}")
        nets.append(net)
    return nets


def in_networks(host: str | None, nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network]) -> bool:
    ip = _ip(host)
    if ip is None or not nets:
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


def lan_urls(settings: Settings) -> list[str]:
    """Pairing links for every local-network IPv4 address of this machine."""
    ips = sorted(a for a in local_addresses() if "." in a and not a.startswith("127.") and is_private(a))
    return [f"{settings.scheme}://{ip}:{settings.port}/#pair={settings.pairing_key}" for ip in ips]


def split_host(host_header: str) -> str:
    """``example:8000`` → ``example``; ``[::1]:8000`` → ``::1``."""
    host = host_header.strip().lower()
    if host.startswith("["):
        return host[1 : host.find("]")] if "]" in host else host
    if host.count(":") == 1:
        return host.split(":", 1)[0]
    return host


class SessionRegistry:
    """In-memory paired LAN sessions, plus the pairing attempt limiter.

    Sessions expire after 30 days and the registry is capped (oldest dropped
    first). Restart = re-pair, by design.
    """

    PAIR_WINDOW_SECONDS = 60
    PAIR_MAX_PER_CLIENT = 5
    # Across all clients, so rotating addresses (IPv6) buys no extra guesses.
    PAIR_MAX_GLOBAL = 30
    MAX_TRACKED_CLIENTS = 10_000

    def __init__(self) -> None:
        self._ids: OrderedDict[str, float] = OrderedDict()
        self._attempts: dict[str, deque[float]] = {}
        self._global: deque[float] = deque()

    def create(self) -> str:
        sid = secrets.token_urlsafe(32)
        self._ids[sid] = time.monotonic()
        while len(self._ids) > MAX_SESSIONS:
            self._ids.popitem(last=False)
        return sid

    def valid(self, sid: str | None) -> bool:
        if not sid:
            return False
        created = self._ids.get(sid)
        if created is None:
            return False
        if time.monotonic() - created > SESSION_TTL_SECONDS:
            del self._ids[sid]
            return False
        return True

    @staticmethod
    def owner(sid: str) -> str:
        """Owner id for a paired session; a hash, so the cookie never lands on disk."""
        return "s-" + hashlib.sha256(sid.encode()).hexdigest()[:32]

    def clear(self) -> None:
        self._ids.clear()

    def allow_attempt(self, client: str) -> bool:
        """Record a pairing attempt; False when the client or everyone is over the limit."""
        now = time.monotonic()

        def prune(q: deque[float]) -> None:
            while q and now - q[0] > self.PAIR_WINDOW_SECONDS:
                q.popleft()

        prune(self._global)
        for key in [k for k, q in self._attempts.items() if not q or now - q[-1] > self.PAIR_WINDOW_SECONDS]:
            del self._attempts[key]
        window = self._attempts.get(client)
        if window is None:
            if len(self._attempts) >= self.MAX_TRACKED_CLIENTS:
                return False
            window = self._attempts[client] = deque()
        prune(window)
        if len(window) >= self.PAIR_MAX_PER_CLIENT or len(self._global) >= self.PAIR_MAX_GLOBAL:
            return False
        window.append(now)
        self._global.append(now)
        return True

    def reset_attempts(self, client: str) -> None:
        self._attempts.pop(client, None)


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


def check_pairing_key(settings: Settings) -> None:
    """Refuse to start LAN mode with a guessable pairing key."""
    if settings.lan_enabled and settings.pairing_key and len(settings.pairing_key) < MIN_PAIRING_KEY_LENGTH:
        raise RuntimeError(
            f"APT_PAIRING_KEY must be at least {MIN_PAIRING_KEY_LENGTH} characters "
            '(generate one: python -c "import secrets; print(secrets.token_urlsafe(16))")'
        )
    if settings.lan_enabled and not settings.pairing_key:
        log.warning("LAN mode is on but APT_PAIRING_KEY is empty: no device can pair")


class SecurityMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings, sessions: SessionRegistry) -> None:
        check_pairing_key(settings)
        self.app = app
        self.settings = settings
        self.sessions = sessions
        self.allowed_hosts = {"localhost", "127.0.0.1", "::1"} | {
            h.strip().lower() for h in settings.allowed_hosts.split(",") if h.strip()
        }
        if settings.lan_enabled or settings.trusted_networks:
            self.allowed_hosts |= local_addresses()
        self.trusted = parse_networks(settings.trusted_networks, lan_enabled=settings.lan_enabled)
        self._reported: set[str] = set()

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

        api = str(scope.get("path", "")).startswith("/api/")
        hsts = scope.get("scheme") == "https" and _hsts_host(_header(scope, b"host") or "")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                headers.extend(h for h in SECURITY_HEADERS if h[0] not in present)
                if api and b"cache-control" not in present:
                    # Documents and job results must not linger in browser caches.
                    headers.append((b"cache-control", b"no-store"))
                if hsts:
                    headers.append((b"strict-transport-security", b"max-age=31536000"))
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
        if not is_private(client_host):
            # Never served outside the local network, whatever the settings.
            self._report(client_host, False, "not on the local network")
            return 403, "Only devices on the local network are served"

        proxied = any(_header(scope, h) is not None for h in FORWARDING_HEADERS)
        loopback = is_loopback(client_host) and not proxied
        local = loopback or (in_networks(client_host, self.trusted) and not proxied)
        sid = cookies.get(SESSION_COOKIE)
        paired = not local and self.sessions.valid(sid)

        if not local:
            if not self.settings.lan_enabled:
                self._report(client_host, proxied)
                return 403, "LAN access is disabled"
            if path not in PAIRING_PATHS and not paired:
                return 401, "Pairing required"

        state = scope.setdefault("state", {})
        state["apt_loopback"] = loopback
        state["apt_local"] = local
        state["apt_owner"] = LOCAL_OWNER if local else (self.sessions.owner(sid) if paired and sid else None)

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

    def _report(self, client_host: str | None, proxied: bool, reason: str = "LAN access is disabled") -> None:
        """Log each refused address once, so a misconfigured Docker or proxy
        setup is easy to diagnose."""
        key = f"{client_host}:{proxied}"
        if key in self._reported or len(self._reported) > 1000:
            return
        self._reported.add(key)
        log.warning(
            "refused %s client %s: %s (see APT_LAN_ENABLED / APT_TRUSTED_NETWORKS)",
            "proxied" if proxied else "non-local",
            client_host,
            reason,
        )


def _hsts_host(host_header: str) -> bool:
    """HSTS only for real DNS names: browsers ignore it on IPs, and on
    ``localhost`` it would break every other local web app on this PC."""
    host = split_host(host_header)
    return bool(host) and host != "localhost" and _ip(host) is None


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
                (b"cache-control", b"no-store"),
                *SECURITY_HEADERS,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
