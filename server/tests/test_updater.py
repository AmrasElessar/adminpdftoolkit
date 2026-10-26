"""Signed self-update of the Windows package."""

from __future__ import annotations

import base64
import hashlib
import io
import zipfile
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from adminpdf import updater


def _keys() -> tuple[Ed25519PrivateKey, str]:
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return key, base64.b64encode(pub).decode()


def _package(extra: dict[str, bytes] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("AdminPDFToolkit/AdminPDFToolkit.exe", b"MZ launcher")
        zf.writestr("AdminPDFToolkit/python/python.exe", b"MZ python")
        for name, data in (extra or {}).items():
            zf.writestr(name, data)
    return buf.getvalue()


class _Response(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_a: object) -> None:
        self.close()


def _serve(monkeypatch: pytest.MonkeyPatch, version: str, zip_bytes: bytes, sums: bytes, sig: bytes) -> None:
    name = f"AdminPDFToolkit-{version}-Windows.zip"
    files = {"pkg": zip_bytes, "sums": sums, "sig": sig}
    monkeypatch.setattr(
        updater,
        "latest_release",
        lambda: {
            "tag": f"v{version}",
            "page": "https://example.invalid/r",
            "package": name,
            "package_url": "https://example.invalid/pkg",
            "sums_url": "https://example.invalid/sums",
            "sig_url": "https://example.invalid/sig",
            "components": {},
        },
    )
    monkeypatch.setattr(updater, "_get", lambda url, timeout=0: files[url.rsplit("/", 1)[-1]])
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda req, timeout=0: _Response(files["pkg"]))


def _signed(key: Ed25519PrivateKey, version: str, data: bytes) -> tuple[bytes, bytes]:
    sums = f"{hashlib.sha256(data).hexdigest()}  AdminPDFToolkit-{version}-Windows.zip\n".encode()
    return sums, base64.b64encode(key.sign(sums))


def test_parse_version() -> None:
    assert updater.parse_version("v2.10.1") > updater.parse_version("2.9.9")
    assert updater.parse_version("2.0.0") == (2, 0, 0)


def test_signature_must_verify() -> None:
    key, pub = _keys()
    sums = b"0" * 64 + b"  a.zip\n"
    assert updater.verify_sums(sums, base64.b64encode(key.sign(sums)), pub) == {"a.zip": "0" * 64}
    other, _ = _keys()
    with pytest.raises(updater.UpdateError, match="signature"):
        updater.verify_sums(sums, base64.b64encode(other.sign(sums)), pub)
    with pytest.raises(updater.UpdateError, match="signature"):
        updater.verify_sums(sums + b"x", base64.b64encode(key.sign(sums)), pub)
    with pytest.raises(updater.UpdateError, match="no release signing key"):
        updater.verify_sums(sums, b"", "")


def test_genuine_update_is_staged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key, pub = _keys()
    monkeypatch.setattr(updater, "RELEASE_PUBLIC_KEY", pub)
    data = _package()
    _serve(monkeypatch, "9.0.0", data, *_signed(key, "9.0.0", data))
    staged = updater.download(tmp_path / "upd")
    assert (staged / "AdminPDFToolkit.exe").read_bytes() == b"MZ launcher"


def test_tampered_package_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key, pub = _keys()
    monkeypatch.setattr(updater, "RELEASE_PUBLIC_KEY", pub)
    sums, sig = _signed(key, "9.0.0", _package())
    _serve(monkeypatch, "9.0.0", _package({"AdminPDFToolkit/evil.dll": b"MZ"}), sums, sig)
    with pytest.raises(updater.UpdateError, match="does not match"):
        updater.download(tmp_path / "upd")
    assert not (tmp_path / "upd" / "AdminPDFToolkit").exists()


def test_unsigned_or_forged_release_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _key, pub = _keys()
    forger, _ = _keys()
    monkeypatch.setattr(updater, "RELEASE_PUBLIC_KEY", pub)
    data = _package()
    _serve(monkeypatch, "9.0.0", data, *_signed(forger, "9.0.0", data))
    with pytest.raises(updater.UpdateError, match="signature"):
        updater.download(tmp_path / "upd")


def test_old_signed_release_is_not_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key, pub = _keys()
    monkeypatch.setattr(updater, "RELEASE_PUBLIC_KEY", pub)
    data = _package()
    _serve(monkeypatch, "1.0.0", data, *_signed(key, "1.0.0", data))
    with pytest.raises(updater.UpdateError, match="not newer"):
        updater.download(tmp_path / "upd")


def test_zip_slip_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key, pub = _keys()
    monkeypatch.setattr(updater, "RELEASE_PUBLIC_KEY", pub)
    data = _package({"AdminPDFToolkit/../../outside.txt": b"x"})
    _serve(monkeypatch, "9.0.0", data, *_signed(key, "9.0.0", data))
    with pytest.raises(updater.UpdateError, match="unsafe path"):
        updater.download(tmp_path / "upd")
    assert not (tmp_path / "outside.txt").exists()


def test_check_reports_without_installing_when_unsigned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "RELEASE_PUBLIC_KEY", "")
    rel: dict[str, Any] = {
        "tag": "v9.0.0",
        "page": "https://example.invalid/r",
        "package": "AdminPDFToolkit-9.0.0-Windows.zip",
        "package_url": "https://example.invalid/pkg",
        "sums_url": "https://example.invalid/sums",
        "sig_url": None,
        "components": {"tesseract": "v5.6.0"},
    }
    monkeypatch.setattr(updater, "latest_release", lambda: rel)
    result = updater.check("2.0.0")
    assert result["available"] and not result["installable"]
    assert result["components"] == {"tesseract": "v5.6.0"}
    monkeypatch.setattr(updater, "latest_release", lambda: (_ for _ in ()).throw(OSError("blocked")))
    assert updater.check("2.0.0") == {"type": "update", "ok": False, "current": "2.0.0", "error": "blocked"}


def test_only_https(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(updater.UpdateError, match="non-HTTPS"):
        updater._get("http://example.invalid/x")


def test_selfcheck_lines_are_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from adminpdf import selfcheck
    from adminpdf.config import Settings

    settings = Settings(data_dir=tmp_path / "d", port=8765)
    results = list(selfcheck.run_checks(settings))
    ids = [r["id"] for r in results]
    assert ids[:3] == ["python", "libraries", "web"] and "tls" in ids and "ocr" in ids
    assert all(r["status"] in ("ok", "warn", "missing", "error") for r in results)
    assert next(r for r in results if r["id"] == "libraries")["status"] == "ok"
    info = selfcheck.info(settings, results)
    assert info["url"] == "https://localhost:8765/"


def test_selfcheck_output_is_ascii(tmp_path: Path) -> None:
    """Windows consoles default to legacy code pages; Turkish must survive."""
    import os
    import subprocess
    import sys

    env = {**os.environ, "APT_DATA_DIR": str(tmp_path / "d"), "PYTHONIOENCODING": "cp1252", "APT_PORT": "8766"}
    env.pop("PYTHONUTF8", None)
    r = subprocess.run(
        [sys.executable, "-m", "adminpdf.selfcheck"], capture_output=True, env=env, timeout=120, check=False
    )
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(b"{")]
    assert lines and all(ln.isascii() for ln in lines)
    import json

    titles = [json.loads(ln).get("title", {}).get("tr", "") for ln in lines]
    assert "Kütüphaneler" in titles


def test_server_banner_survives_legacy_code_page(tmp_path: Path) -> None:
    """The start-up banner is Turkish; a cp1252 console must not crash the server."""
    import os
    import subprocess
    import sys
    import threading
    import time

    env = {
        **os.environ,
        "APT_DATA_DIR": str(tmp_path / "d"),
        "PYTHONIOENCODING": "cp1252",
        "APT_PORT": "8767",
        # Unbuffered: every line is encoded (and would fail) the moment it is printed.
        "PYTHONUNBUFFERED": "1",
    }
    env.pop("PYTHONUTF8", None)
    log = tmp_path / "stderr.log"
    out = bytearray()
    with log.open("wb") as err_file:
        p = subprocess.Popen(
            [sys.executable, "-m", "adminpdf", "--lan"], stdout=subprocess.PIPE, stderr=err_file, env=env
        )
        assert p.stdout is not None
        stdout = p.stdout

        def read() -> None:
            for line in stdout:
                out.extend(line)

        # Read in the background: start-up time varies a lot between CI machines.
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        try:
            deadline = time.monotonic() + 90
            while b"Yerel a" not in out and p.poll() is None and time.monotonic() < deadline:
                time.sleep(0.5)
            assert p.poll() is None, log.read_bytes()[-800:]
        finally:
            p.terminate()
            p.wait(timeout=30)
            reader.join(timeout=10)
    err = log.read_bytes()
    assert b"UnicodeEncodeError" not in err, err[-800:]
    assert b"Yerel a" in out  # the banner was printed, letters it cannot show replaced


def test_each_system_looks_for_its_own_package(monkeypatch: pytest.MonkeyPatch) -> None:
    names = {
        "win32": "AdminPDFToolkit-2.1.0-Windows.zip",
        "darwin": "AdminPDFToolkit-2.1.0-macOS-arm64.zip",
        "linux": "AdminPDFToolkit-2.1.0-Linux-x86_64.tar.gz",
    }
    for system, name in names.items():
        monkeypatch.setattr(updater.sys, "platform", system)
        pattern = updater.platform_asset()
        assert pattern.match(name) and not any(pattern.match(n) for n in names.values() if n != name)


def test_only_windows_installs_in_place(monkeypatch: pytest.MonkeyPatch) -> None:
    _key, pub = _keys()
    monkeypatch.setattr(updater, "RELEASE_PUBLIC_KEY", pub)
    rel: dict[str, Any] = {
        "tag": "v9.0.0",
        "page": "https://example.invalid/r",
        "package": "AdminPDFToolkit-9.0.0-macOS-arm64.zip",
        "package_url": "https://example.invalid/pkg",
        "sums_url": "https://example.invalid/sums",
        "sig_url": "https://example.invalid/sig",
        "components": {},
    }
    monkeypatch.setattr(updater, "latest_release", lambda: rel)
    monkeypatch.setattr(updater.sys, "platform", "darwin")
    result = updater.check("2.0.0")
    assert result["available"] and not result["installable"]
    monkeypatch.setattr(updater.sys, "platform", "win32")
    assert updater.check("2.0.0")["installable"]
