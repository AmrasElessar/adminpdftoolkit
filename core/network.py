"""Network helpers: client-IP, loopback detection, LAN IP, self-signed cert."""

from __future__ import annotations

import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException, Request

from state import BASE_DIR

LOCAL_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "::1", "localhost"})


def client_ip(request: Request) -> str:
    """Best-effort client IP for audit logging.

    X-Forwarded-For is only honoured when the immediate peer is listed in
    HT_TRUSTED_PROXIES (comma-separated env var). Otherwise the header is
    ignored to prevent log-spoofing — a remote attacker would otherwise
    be able to set X-Forwarded-For: 127.0.0.1 and have the audit row
    record a fake IP.
    """
    direct = request.client.host if request.client else None
    if direct is None:
        return "?"
    trusted_raw = os.environ.get("HT_TRUSTED_PROXIES", "")
    trusted = {p.strip() for p in trusted_raw.split(",") if p.strip()}
    if trusted and direct in trusted:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return str(fwd.split(",")[0].strip())
    return str(direct)


def is_local_request(request: Request) -> bool:
    """True if the request comes from the host PC itself (loopback).

    Used to decide whether mobile-token authentication should be enforced.
    Treats X-Forwarded-For ONLY when no real client is set, to avoid spoofing.

    Honours ``settings.loopback_bypass``: operators running behind a
    reverse proxy on 127.0.0.1 should set ``HT_LOOPBACK_BYPASS=false`` to
    force every client — including the proxy's loopback connection — to
    authenticate. Otherwise the proxy invisibly turns every remote
    request into a "local" request and the mobile-auth middleware never
    fires.
    """
    from settings import settings as _settings

    if not _settings.loopback_bypass:
        return False
    return bool(request.client and request.client.host in LOCAL_HOSTS)


def assert_same_origin(request: Request) -> None:
    """Reject state-changing requests whose Origin/Referer points outside
    this server. Defends against cross-origin CSRF: a hostile page in the
    operator's browser POSTing to ``http://127.0.0.1:8000/admin/...``.

    The check is lenient on purpose:

    * Browsers always attach ``Origin`` to cross-origin POST/PUT/DELETE
      requests — that's where the threat lives, and that's the case we
      enforce.
    * For same-origin requests from the bundled UI, the browser supplies
      ``Origin`` matching the server host (loopback / LAN IP / HTTPS
      variants); we accept those.
    * curl/scripts typically omit both headers. We let those through when
      the request is loopback (i.e. the operator is running a tool on the
      same machine). Remote callers without Origin OR Referer get 403.
    """
    origin = (request.headers.get("origin") or "").strip()
    referer = (request.headers.get("referer") or "").strip()
    candidate = origin or referer
    if not candidate:
        # Lazy import via the core facade so tests that monkeypatch
        # ``core.is_local_request`` see their override (the network-module
        # local function would bypass the patch).
        import core as _core

        if _core.is_local_request(request):
            return
        raise HTTPException(
            403,
            "Origin/Referer başlığı eksik — bu işlem tarayıcı üzerinden çağrılmalı.",
        )
    try:
        parsed = urlparse(candidate)
    except ValueError as e:
        raise HTTPException(403, "Origin/Referer geçersiz.") from e
    host = (parsed.hostname or "").lower()
    if not host:
        raise HTTPException(403, "Origin/Referer host eksik.")
    if host in LOCAL_HOSTS:
        return
    if host == lan_ip():
        return
    raise HTTPException(
        403,
        "Origin/Referer bu sunucuyla eşleşmiyor — cross-origin istek engellendi.",
    )


def lan_ip() -> str:
    """Best-effort LAN IPv4 of this machine, for printing on startup."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
        finally:
            s.close()
    except Exception:
        return "127.0.0.1"


_CERT_VALIDITY_DAYS = 365
_CERT_RENEW_THRESHOLD_DAYS = 30


def _existing_cert_still_valid(cert_file: Path) -> bool:
    """Inspect ``cert_file``; return True iff it has more than
    ``_CERT_RENEW_THRESHOLD_DAYS`` of validity left.

    Returns False on any read/parse error so we regenerate aggressively
    rather than serving an unreadable artifact.
    """
    try:
        from cryptography import x509

        cert = x509.load_pem_x509_certificate(cert_file.read_bytes())
        # ``not_valid_after_utc`` is the timezone-aware accessor that
        # supersedes the deprecated ``not_valid_after`` (Python 3.12+).
        try:
            expires = cert.not_valid_after_utc
        except AttributeError:
            expires = cert.not_valid_after.replace(tzinfo=timezone.utc)
        remaining = expires - datetime.now(timezone.utc)
        return remaining.days > _CERT_RENEW_THRESHOLD_DAYS
    except Exception:
        return False


def ensure_self_signed_cert() -> tuple[Path, Path]:
    """Generate (or rotate) a self-signed cert under ``BASE_DIR/cert``.

    Rebuilds the cert when:
      * cert/key files don't exist, OR
      * the existing cert has fewer than ``_CERT_RENEW_THRESHOLD_DAYS``
        of validity left (auto-rotation).

    The cert is valid for ``_CERT_VALIDITY_DAYS`` and SANs every detectable
    interface address: ``localhost``, loopback IPv4/IPv6, and the current
    LAN IP. Operators whose DHCP lease changes will see a SAN mismatch on
    the new IP — at next startup the cert will be rebuilt only if expiry
    is near; force a rotation by deleting ``cert/server.{crt,key}``.
    """
    import ipaddress

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    cert_dir = BASE_DIR / "cert"
    cert_dir.mkdir(exist_ok=True)
    cert_file = cert_dir / "server.crt"
    key_file = cert_dir / "server.key"
    if cert_file.exists() and key_file.exists() and _existing_cert_still_valid(cert_file):
        return cert_file, key_file

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "Admin PDF Toolkit Local"),
        ]
    )
    san_entries: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address("::1")),
    ]
    try:
        san_entries.append(x509.IPAddress(ipaddress.ip_address(lan_ip())))
    except (ValueError, ipaddress.AddressValueError):
        pass
    san = x509.SubjectAlternativeName(san_entries)
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=_CERT_VALIDITY_DAYS))
        .add_extension(san, critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    # Tighten key file permissions on POSIX; on Windows the file inherits
    # the user-profile ACL which already restricts to the current user.
    if os.name != "nt":
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
    return cert_file, key_file
