# Üçüncü Taraf Lisansları / Third-Party Licences

Admin PDF Toolkit (AGPL-3.0) aşağıdaki açık kaynak bileşenleri kullanır. Tümü
ücretsiz ve AGPL-3.0 ile uyumludur. *All components are free and compatible
with AGPL-3.0.*

## Sunucu / Server (Python)

| Bileşen | Lisans | Görev |
|---|---|---|
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) / MuPDF | AGPL-3.0 | PDF okuma, yazma, render, düzenleme, karartma |
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | Web API |
| [Starlette](https://github.com/encode/starlette) | BSD-3-Clause | ASGI araç takımı |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | ASGI sunucusu |
| [Pydantic](https://github.com/pydantic/pydantic) / pydantic-settings | MIT | Doğrulama ve ayarlar |
| [pikepdf](https://github.com/pikepdf/pikepdf) / qpdf | MPL-2.0 / Apache-2.0 | Düşük seviye PDF, onarım, güvenlik taraması |
| [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) | MPL-2.0 | OCR, PDF/A |
| [Tesseract](https://github.com/tesseract-ocr/tesseract) (sistem) | Apache-2.0 | Metin tanıma |
| [Ghostscript](https://ghostscript.com/) (sistem, isteğe bağlı) | AGPL-3.0 | PDF/A dönüştürme |
| [pyHanko](https://github.com/MatthiasValvekens/pyHanko) + certvalidator | MIT | PAdES dijital imza ve doğrulama |
| [cryptography](https://github.com/pyca/cryptography) | Apache-2.0 / BSD | Sertifika üretimi |
| [pdf2docx](https://github.com/ArtifexSoftware/pdf2docx) | MIT | PDF → Word |
| [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl) | MIT | Excel okuma/yazma |
| [python-docx](https://github.com/python-openxml/python-docx) | MIT | Word okuma |
| [fontTools](https://github.com/fonttools/fonttools) | MIT | Font alt kümeleme, glif kapsamı |
| [OpenCV](https://github.com/opencv/opencv-python) (headless) | Apache-2.0 | Belge algılama, perspektif ve eğim düzeltme |
| [NumPy](https://numpy.org/) | BSD-3-Clause | Görüntü işleme |
| [Pillow](https://github.com/python-pillow/Pillow) | MIT-CMU (HPND) | Görsel okuma/yazma |
| [LibreOffice](https://www.libreoffice.org/) (sistem, isteğe bağlı) | MPL-2.0 | Office → PDF |
| [ClamAV](https://www.clamav.net/) (sistem, isteğe bağlı) | GPL-2.0 | Virüs taraması (ayrı süreç) |

## Arayüz / Web UI

| Bileşen | Lisans | Görev |
|---|---|---|
| [Svelte](https://github.com/sveltejs/svelte) | MIT | Arayüz çatısı |
| [pdf.js](https://github.com/mozilla/pdf.js) (pdfjs-dist) | Apache-2.0 | Tarayıcıda PDF görüntüleme |
| [Vite](https://github.com/vitejs/vite) (derleme) | MIT | Paketleme |
| [TypeScript](https://github.com/microsoft/TypeScript) (derleme) | Apache-2.0 | Tip denetimi |
| [axe-core](https://github.com/dequelabs/axe-core) (test) | MPL-2.0 | Erişilebilirlik denetimi |
| [Playwright](https://github.com/microsoft/playwright) (test) | Apache-2.0 | Uçtan uca test |

## Fontlar / Fonts

| Font | Lisans |
|---|---|
| DejaVu Sans (paketlenmiş, `server/adminpdf/assets/fonts`) | Bitstream Vera / DejaVu — bkz. `DejaVu-LICENSE.txt` |
| `scripts/fetch_fonts.py` ile indirilen ek fontlar (Noto vb.) | SIL Open Font License 1.1 |
