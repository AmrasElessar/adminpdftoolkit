"""Print the GitHub release notes for a version: install steps + its CHANGELOG section.

python scripts/release_notes.py 2.0.0 > notes.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HEADER = """## İndir ve çalıştır / Download and run

**Windows:** `AdminPDFToolkit-{v}.zip` dosyasını indirip bir klasöre açın, **`Baslat (Windows).bat`**
dosyasına çift tıklayın (Python 3.11+ gerekir; ilk açılışta gerekli paketler kurulur).
Taranmış belgeler için OCR: **`OCR Kur (Windows).bat`**. Ayrıntılar paketteki `OKUBENI.txt` dosyasında.

**Docker:** `docker compose up -d --build` (OCR, LibreOffice, Ghostscript ve ClamAV dahil).

*Windows: unzip `AdminPDFToolkit-{v}.zip`, double-click `Baslat (Windows).bat` (needs Python 3.11+).
OCR: run `OCR Kur (Windows).bat`. Docker: `docker compose up -d --build`.*

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
