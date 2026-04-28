"""Network helpers: client-IP, loopback detection, LAN IP, self-signed cert."""

from __future__ import annotations

import os
import socket
from datetime import datetime
from pathlib import Path

from fastapi import Request

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
            return fwd.split(",")[0].strip()
    return direct


def is_local_request(request: Request) -> bool:
    """True if the request comes from the host PC itself (loopback).

    Used to decide whether mobile-token authentication should be enforced.
    Treats X-Forwarded-For ONLY when no real client is set, to avoid spoofing.
    """
    if request.client and request.client.host in LOCAL_HOSTS:
        return True
    return False


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


def ensure_self_signed_cert() -> tuple[Path, Path]:
    """Generate a self-signed cert under BASE_DIR/cert if not present."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    cert_dir = BASE_DIR / "cert"
    cert_dir.mkdir(exist_ok=True)
    cert_file = cert_dir / "server.crt"
    key_file = cert_dir / "server.key"
    if cert_file.exists() and key_file.exists():
        return cert_file, key_file

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Admin PDF Toolkit Local"),
    ])
    san = x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.IPAddress(__import__("ipaddress").ip_address("127.0.0.1")),
        x509.IPAddress(__import__("ipaddress").ip_address(lan_ip())),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow().replace(year=datetime.utcnow().year + 5))
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
    return cert_file, key_file
