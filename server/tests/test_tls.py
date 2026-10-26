"""Local certificate authority and server certificate."""

from __future__ import annotations

import datetime as dt
import ipaddress
import sys
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from cryptography.x509.verification import PolicyBuilder, Store, VerificationError

from adminpdf.core import tls


@pytest.fixture(autouse=True)
def _fixed_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tls, "local_addresses", lambda: {"192.168.1.20", "127.0.0.1", "8.8.8.8"})
    monkeypatch.setattr(tls, "_hostname", lambda: "ofis-pc")


def _chain(path: Path) -> list[x509.Certificate]:
    return x509.load_pem_x509_certificates(path.read_bytes())


def _verify(ca: x509.Certificate, leaf: x509.Certificate, name: str) -> None:
    subject: x509.verification.Subject
    try:
        subject = x509.IPAddress(ipaddress.ip_address(name))
    except ValueError:
        subject = x509.DNSName(name)
    verifier = PolicyBuilder().store(Store([ca])).build_server_verifier(subject)
    verifier.verify(leaf, [])


def test_server_certificate_covers_local_names_only(tmp_path: Path) -> None:
    files = tls.ensure(tmp_path)
    ca = x509.load_pem_x509_certificate(files.ca.read_bytes())
    leaf, issuer = _chain(files.cert)
    assert issuer == ca
    for name in ("localhost", "ofis-pc", "ofis-pc.local", "127.0.0.1", "192.168.1.20"):
        _verify(ca, leaf, name)
    san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert "8.8.8.8" not in {str(i) for i in san.get_values_for_type(x509.IPAddress)}  # public address left out
    assert (leaf.not_valid_after_utc - leaf.not_valid_before_utc).days <= tls.SERVER_DAYS
    if sys.platform != "win32":  # Windows has ACLs, not POSIX modes
        assert files.key.stat().st_mode & 0o077 == 0
        assert (tmp_path / "ca.key").stat().st_mode & 0o077 == 0


def test_ca_cannot_vouch_for_real_websites(tmp_path: Path) -> None:
    """Name constraints: even with the CA key, a certificate for a public
    site or address does not verify."""
    tls.ensure(tmp_path)
    ca = x509.load_pem_x509_certificate((tmp_path / "ca.crt").read_bytes())
    ca_key = serialization.load_pem_private_key((tmp_path / "ca.key").read_bytes(), password=None)
    assert isinstance(ca_key, ec.EllipticCurvePrivateKey)
    for name, general in (
        ("bank.example.com", x509.DNSName("bank.example.com")),
        ("8.8.8.8", x509.IPAddress(ipaddress.ip_address("8.8.8.8"))),
    ):
        key = ec.generate_private_key(ec.SECP256R1())
        now = dt.datetime.now(dt.UTC)
        leaf = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
            .issuer_name(ca.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=1))
            .not_valid_after(now + dt.timedelta(days=30))
            .add_extension(x509.SubjectAlternativeName([general]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256())
        )
        with pytest.raises(VerificationError):
            _verify(ca, leaf, name)


def test_reused_and_reissued_when_the_address_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = tls.ensure(tmp_path)
    cert_bytes = first.cert.read_bytes()
    again = tls.ensure(tmp_path)
    assert again.fingerprint == first.fingerprint and again.cert.read_bytes() == cert_bytes

    # DHCP hands the PC a new address: new server certificate, same CA, so
    # phones that trust the CA keep working.
    monkeypatch.setattr(tls, "local_addresses", lambda: {"192.168.1.77"})
    moved = tls.ensure(tmp_path)
    assert moved.fingerprint == first.fingerprint
    assert moved.cert.read_bytes() != cert_bytes
    ca = x509.load_pem_x509_certificate(moved.ca.read_bytes())
    _verify(ca, _chain(moved.cert)[0], "192.168.1.77")


def test_new_ca_when_a_host_name_is_outside_its_constraints(tmp_path: Path) -> None:
    first = tls.ensure(tmp_path)
    assert tls.ensure(tmp_path, ["pdf.ofis.lan"]).fingerprint == first.fingerprint  # *.lan is covered
    changed = tls.ensure(tmp_path, ["pdf.sirket.com.tr"])
    assert changed.fingerprint != first.fingerprint
    ca = x509.load_pem_x509_certificate(changed.ca.read_bytes())
    _verify(ca, _chain(changed.cert)[0], "pdf.sirket.com.tr")


def test_long_computer_names_fit_the_certificate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """X.509 caps a common name at 64 characters; long PC names must still work."""
    long_name = "muhasebe-departmani-ikinci-kat-ortak-bilgisayar-numara-12"
    monkeypatch.setattr(tls, "_hostname", lambda: long_name)
    files = tls.ensure(tmp_path)
    ca = x509.load_pem_x509_certificate(files.ca.read_bytes())
    leaf = _chain(files.cert)[0]
    assert len(ca.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value) <= 64
    _verify(ca, leaf, long_name)
