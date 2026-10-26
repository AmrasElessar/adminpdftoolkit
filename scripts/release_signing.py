"""Ed25519 signing of release checksums (SHA256SUMS → SHA256SUMS.sig).

One-time setup by the maintainer:

    python scripts/release_signing.py keygen

prints a private key (store it as the GitHub Actions secret
RELEASE_SIGNING_KEY — never commit it) and a public key (paste it into
server/adminpdf/updater.py as RELEASE_PUBLIC_KEY). The release workflow then
runs ``sign`` and the app installs updates only when the signature verifies.
"""

from __future__ import annotations

import base64
import hashlib
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def keygen() -> None:
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    print("GitHub secret RELEASE_SIGNING_KEY (keep private):")
    print("  " + base64.b64encode(private).decode())
    print("server/adminpdf/updater.py RELEASE_PUBLIC_KEY:")
    print("  " + base64.b64encode(public).decode())


def sums(folder: Path) -> None:
    """Write folder/SHA256SUMS for every release file in ``folder``."""
    lines = []
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.name not in ("SHA256SUMS", "SHA256SUMS.sig"):
            lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n")
    (folder / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")
    print("".join(lines), end="")


def sign(path: Path) -> None:
    secret = os.environ.get("RELEASE_SIGNING_KEY", "").strip()
    if not secret:
        print("RELEASE_SIGNING_KEY is not set: release left unsigned (the app will not auto-install it)")
        return
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(secret))
    sig = base64.b64encode(key.sign(path.read_bytes())).decode()
    path.with_name(path.name + ".sig").write_text(sig + "\n", encoding="ascii")
    print(f"signed {path.name}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "keygen":
        keygen()
    elif cmd == "sums" and len(sys.argv) == 3:
        sums(Path(sys.argv[2]))
    elif cmd == "sign" and len(sys.argv) == 3:
        sign(Path(sys.argv[2]))
    else:
        sys.exit("usage: release_signing.py keygen | sums <dist-folder> | sign <SHA256SUMS>")
