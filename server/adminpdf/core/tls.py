"""HTTPS for the local network, with no outside certificate authority.

On first start the server creates its own small certificate authority (CA)
and, with it, a certificate for this computer's names and LAN addresses.
Devices trust the CA once (install ``ca.crt``); after that every connection
is encrypted and verified, also after the PC gets a new IP address — the
server certificate is reissued automatically, the CA stays the same.

The CA is *name-constrained*: it can only vouch for private addresses
(10/8, 172.16/12, 192.168/16, link-local, loopback, IPv6 ULA) and local
names (``localhost``, ``*.local``, ``*.lan``, ``*.home.arpa``,
``*.internal`` and this computer's name). Even if its key leaked, it could
not be used to impersonate a real website.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import ipaddress
import logging
import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .security import PRIVATE_NETWORKS, local_addresses

log = logging.getLogger("adminpdf.tls")

CA_DAYS = 3650
# Apple caps TLS server certificates at 825 days for user-installed roots and
# 398 for public ones; stay under both.
SERVER_DAYS = 397
RENEW_BEFORE = dt.timedelta(days=30)
LOCAL_SUFFIXES = ("local", "lan", "home.arpa", "internal")
# OpenSSL 1.2 cipher list (TLS 1.3 suites are always on): forward secrecy, AEAD only.
CIPHERS = "ECDHE+AESGCM:ECDHE+CHACHA20"


@dataclass(frozen=True)
class TlsFiles:
    cert: Path
    key: Path
    ca: Path
    fingerprint: str  # SHA-256 of the CA certificate, "AB:CD:…"


def fingerprint(cert: x509.Certificate) -> str:
    digest = cert.fingerprint(hashes.SHA256()).hex().upper()
    return ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))


def short_fingerprint(fp: str) -> str:
    """First 8 bytes — enough to compare by eye on a phone screen."""
    return fp[:23]


def _hostname() -> str:
    return socket.gethostname().split(".")[0].lower()


def _cn(text: str) -> str:
    """X.509 limits a common name to 64 characters (long PC names exceed it);
    the names that matter for verification live in the SAN anyway."""
    return text if len(text) <= 64 else text[:61] + "..."


def _dns_constraints(extra: list[str]) -> list[str]:
    names = ["localhost", *LOCAL_SUFFIXES, _hostname(), *extra]
    return sorted({n.strip(".").lower() for n in names if n.strip(".")})


def _covered(name: str, constraints: list[str]) -> bool:
    name = name.lower().strip(".")
    return any(name == c or name.endswith("." + c) for c in constraints)


def _write_private(path: Path, data: bytes) -> None:
    """Write a key readable by this user only (best effort on Windows)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


def _pem_key(key: ec.EllipticCurvePrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _make_ca(directory: Path, dns: list[str]) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Admin PDF Toolkit"),
            x509.NameAttribute(NameOID.COMMON_NAME, _cn(f"Admin PDF Toolkit yerel CA ({_hostname()})")),
        ]
    )
    now = _now()
    permitted: list[x509.GeneralName] = [x509.DNSName(n) for n in dns]
    permitted += [x509.IPAddress(net) for net in PRIVATE_NETWORKS]
    ski = x509.SubjectKeyIdentifier.from_public_key(key.public_key())
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=CA_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.NameConstraints(permitted_subtrees=permitted, excluded_subtrees=None), critical=True)
        .add_extension(ski, critical=False)
        .sign(key, hashes.SHA256())
    )
    _write_private(directory / "ca.key", _pem_key(key))
    (directory / "ca.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    log.warning("created a new local certificate authority: devices must (re)install %s", directory / "ca.crt")
    return cert, key


def _load_ca(directory: Path) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey] | None:
    try:
        cert = x509.load_pem_x509_certificate((directory / "ca.crt").read_bytes())
        key = serialization.load_pem_private_key((directory / "ca.key").read_bytes(), password=None)
    except (OSError, ValueError):
        return None
    if not isinstance(key, ec.EllipticCurvePrivateKey) or cert.not_valid_after_utc - RENEW_BEFORE < _now():
        return None
    return cert, key


def _ca_constraints(ca: x509.Certificate) -> list[str]:
    try:
        nc = ca.extensions.get_extension_for_class(x509.NameConstraints).value
    except x509.ExtensionNotFound:
        return []
    return [str(g.value) for g in nc.permitted_subtrees or [] if isinstance(g, x509.DNSName)]


def wanted_names(extra_hosts: list[str]) -> tuple[list[str], list[str]]:
    """``(dns_names, ip_addresses)`` the server certificate must cover."""
    host = _hostname()
    dns = sorted({"localhost", host, f"{host}.local", *(h.lower() for h in extra_hosts)})
    ips = {"127.0.0.1", "::1"}
    for addr in local_addresses():
        try:
            ip = ipaddress.ip_address(addr.split("%", 1)[0])
        except ValueError:
            continue
        if any(ip in net for net in PRIVATE_NETWORKS):
            ips.add(str(ip))
    return dns, sorted(ips)


def _server_ok(cert_path: Path, ca: x509.Certificate, dns: list[str], ips: list[str]) -> bool:
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except (OSError, ValueError, x509.ExtensionNotFound):
        return False
    if cert.issuer != ca.subject or cert.not_valid_after_utc - RENEW_BEFORE < _now():
        return False
    try:
        cert.verify_directly_issued_by(ca)
    except Exception:  # any failure means reissue
        return False
    have_dns = set(san.get_values_for_type(x509.DNSName))
    have_ips = {str(i) for i in san.get_values_for_type(x509.IPAddress)}
    return set(dns) <= have_dns and set(ips) <= have_ips


def _make_server(
    directory: Path, ca: x509.Certificate, ca_key: ec.EllipticCurvePrivateKey, dns: list[str], ips: list[str]
) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    now = _now()
    san: list[x509.GeneralName] = [x509.DNSName(n) for n in dns]
    san += [x509.IPAddress(ipaddress.ip_address(i)) for i in ips]
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, _cn(_hostname()))]))
        .issuer_name(ca.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(min(now + dt.timedelta(days=SERVER_DAYS), ca.not_valid_after_utc))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    _write_private(directory / "server.key", _pem_key(key))
    # Chain: browsers that did not install the CA still see who issued it.
    chain = cert.public_bytes(serialization.Encoding.PEM) + ca.public_bytes(serialization.Encoding.PEM)
    (directory / "server.crt").write_bytes(chain)


def ensure(directory: Path, extra_hosts: list[str] | None = None) -> TlsFiles:
    """Create or refresh the CA and server certificate in ``directory``."""
    extra = [h for h in (extra_hosts or []) if h and not _is_ip(h)]
    directory.mkdir(parents=True, exist_ok=True)
    dns, ips = wanted_names(extra)
    loaded = _load_ca(directory)
    if loaded is None or not all(_covered(n, _ca_constraints(loaded[0])) for n in dns):
        loaded = _make_ca(directory, _dns_constraints(extra))
    ca, ca_key = loaded
    if not _server_ok(directory / "server.crt", ca, dns, ips) or not (directory / "server.key").is_file():
        _make_server(directory, ca, ca_key, dns, ips)
    return TlsFiles(directory / "server.crt", directory / "server.key", directory / "ca.crt", fingerprint(ca))


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def trust_ca(ca: Path) -> bool:
    """Ask the OS to trust the CA for the current user. The OS shows its own
    confirmation dialog; returns whether the command succeeded."""
    cmd: list[str]
    if sys.platform == "win32":
        cmd = ["certutil", "-user", "-addstore", "Root", str(ca)]
    elif sys.platform == "darwin":
        keychain = Path.home() / "Library" / "Keychains" / "login.keychain-db"
        cmd = ["security", "add-trusted-cert", "-r", "trustRoot", "-k", str(keychain), str(ca)]
    else:
        return False
    try:
        return subprocess.run(cmd, check=False, timeout=300).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
