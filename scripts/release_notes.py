"""Print the GitHub release notes for a version: install steps + its CHANGELOG section.

python scripts/release_notes.py 2.0.0 > notes.md
"""

# ruff: noqa: E501  (Markdown table rows)
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HEADER = """## İndir / Download

| Sistem / System | Dosya / File | Aç / Open |
|---|---|---|
| **Windows 10 / 11** (64 bit) | **`AdminPDFToolkit-{v}-Windows.zip`** | Çıkarın → **`AdminPDFToolkit.exe`** — Python, OCR (Tesseract + Türkçe) ve PDF/A (Ghostscript) dahil |
| **macOS 11+** (Apple Silicon M1 ve sonrası / M1 and later) | **`AdminPDFToolkit-{v}-macOS-arm64.zip`** | `AdminPDFToolkit.app` → Uygulamalar / Applications |
| **Linux x86_64** (Ubuntu 22.04+, Debian 12+, Mint 21+, Pardus 23+, Fedora 36+) | **`AdminPDFToolkit-{v}-Linux-x86_64.tar.gz`** | `AdminPDFToolkit` |
| Intel Mac, ARM Linux… | `AdminPDFToolkit-{v}-Linux-macOS.zip` | Python 3.11+ → `sh scripts/start.sh` |
| Docker | — | `docker compose up -d --build` |

Hepsi ücretsizdir ve kurulum gerektirmez. *All free, nothing to install.*

> [!IMPORTANT]
> **İlk açılışta işletim sistemi uyarı gösterecek — bu normaldir.** Uygulama ücretsiz ve açık kaynak olduğu için Microsoft ve Apple'ın ücretli kod imzalama / onay hizmetlerinden geçirilmedi. Bir kez onaylayın:
> - **Windows** — *"Windows bilgisayarınızı korudu"*: **Ek bilgi ▸ Yine de çalıştır** (veya zip'i açmadan önce sağ tık ▸ Özellikler ▸ **Engellemeyi kaldır**). *"Sertifika yüklemek üzeresiniz"*: **Evet** (yalnızca yerel HTTPS içindir). Güvenlik duvarı: yalnızca **Özel ağlar**.
> - **macOS** — *"Geliştirici doğrulanamadığından açılamıyor"*: **Bitti ▸ Sistem Ayarları ▸ Gizlilik ve Güvenlik ▸ Yine de Aç**.
>
> **The operating system will warn on first start — that is expected.** The app is free and open source and has not gone through Microsoft's / Apple's paid signing. Confirm once:
> - **Windows** — *"Windows protected your PC"*: **More info ▸ Run anyway** (or right-click the zip ▸ Properties ▸ **Unblock** before extracting). *"You are about to install a certificate"*: **Yes** (local HTTPS only). Firewall: **Private networks** only.
> - **macOS** — *"cannot be opened because the developer cannot be verified"*: **Done ▸ System Settings ▸ Privacy & Security ▸ Open Anyway**.

**Doğrulama / Verify:** `SHA256SUMS` (Ed25519 imzası `SHA256SUMS.sig`) — Windows `certutil -hashfile <dosya> SHA256` · macOS `shasum -a 256 <file>` · Linux `sha256sum <file>`.
Ghostscript kaynak kodu (AGPL-3.0) bu sürümün dosyaları arasındadır. *Ghostscript's source tarball (AGPL-3.0) is attached to this release.*

Tüm bileşenler ve lisansları (Türkçe ve İngilizce) / all components and licences: [THIRD_PARTY_LICENSES.md](https://github.com/AmrasElessar/adminpdftoolkit/blob/v{v}/THIRD_PARTY_LICENSES.md) — uygulamada **Hakkında ve Lisanslar** / in the app: **About & Licences**.

"""


def section(version: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[)", text, re.M | re.S)
    if not match:
        sys.exit(f"CHANGELOG.md has no section for {version}")
    return match.group(1).strip()


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: release_notes.py <version>")
    version = sys.argv[1].removeprefix("v")
    print(HEADER.format(v=version) + "## Değişiklikler / Changes\n\n" + section(version))


if __name__ == "__main__":
    main()
