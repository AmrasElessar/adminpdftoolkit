"""Print the GitHub release notes for a version: install steps + its CHANGELOG section.

python scripts/release_notes.py 2.0.0 > notes.md
"""

# ruff: noqa: E501  (Markdown table rows)
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HEADER = """## İndir ve çalıştır / Download and run

| Dosya / File | Kimin için / For |
|---|---|
| **`AdminPDFToolkit-{v}-Windows.zip`** | **Windows — kurulum gerektirmez.** Python ve tüm kütüphaneler içinde; internetsiz çalışır. *Self-contained, nothing to install, works offline.* |
| `AdminPDFToolkit-{v}-Linux-macOS.zip` | Linux / macOS (Python 3.11+ gerekir) — `sh scripts/start.sh` |

**Windows:** zip'i bir klasöre çıkarın, **`Baslat (Windows).bat`** dosyasına çift tıklayın. Tarayıcı
kendiliğinden açılır. Taranmış belgeler için OCR: **`OCR Kur (Windows).bat`** (bir kerelik, internetten
Tesseract + Türkçe dil paketini kurar). Ayrıntılar paketteki `OKUBENI.txt` dosyasında.

*Windows: unzip, double-click `Baslat (Windows).bat`. OCR for scans: `OCR Kur (Windows).bat` (one-time).*

**Docker:** `docker compose up -d --build` (OCR, LibreOffice, Ghostscript ve ClamAV dahil).

Tüm bileşenler ve lisansları / all components and licences: [THIRD_PARTY_LICENSES.md](https://github.com/AmrasElessar/adminpdftoolkit/blob/v{v}/THIRD_PARTY_LICENSES.md)

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
