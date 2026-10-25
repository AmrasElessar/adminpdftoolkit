# Üçüncü Taraf Lisansları ve Atıflar / Third-Party Licences and Attributions

Admin PDF Toolkit (AGPL-3.0-or-later) başkalarının emeği üzerine kuruludur. Aşağıda
kullandığımız **her** kütüphane, program, font, veri ve yöntem; kaynağı ve
lisansıyla birlikte anılır. Hepsi ücretsizdir ve AGPL-3.0 ile uyumludur.
Emeği geçen herkese teşekkür ederiz.

*Admin PDF Toolkit is built on other people's work. Every library, program, font,
dataset and method we use is credited below with its source and licence. All are
free and compatible with AGPL-3.0. Thank you to everyone involved.*

## 1. Sunucu kütüphaneleri / Server libraries (Python)

Doğrudan kullandıklarımız. *Libraries the code imports directly.*

| Bileşen | Lisans | Görev |
|---|---|---|
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) / MuPDF | AGPL-3.0 | PDF okuma, yazma, render, düzenleme, karartma |
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | Web API |
| [Starlette](https://github.com/encode/starlette) | BSD-3-Clause | ASGI araç takımı |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | ASGI sunucusu |
| [Pydantic](https://github.com/pydantic/pydantic) / pydantic-settings | MIT | Doğrulama ve ayarlar |
| [pikepdf](https://github.com/pikepdf/pikepdf) / qpdf | MPL-2.0 / Apache-2.0 | Düşük seviye PDF, onarım, güvenlik taraması |
| [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) | MPL-2.0 | OCR, PDF/A |
| [pyHanko](https://github.com/MatthiasValvekens/pyHanko) + certvalidator | MIT | PAdES dijital imza ve doğrulama |
| [cryptography](https://github.com/pyca/cryptography) | Apache-2.0 / BSD | Sertifika üretimi |
| [pdf2docx](https://github.com/ArtifexSoftware/pdf2docx) | MIT | PDF → Word |
| [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl) | MIT | Excel okuma/yazma |
| [python-docx](https://github.com/python-openxml/python-docx) | MIT | Word okuma |
| [fontTools](https://github.com/fonttools/fonttools) | MIT | Font alt kümeleme, glif kapsamı |
| [OpenCV](https://github.com/opencv/opencv-python) (headless) | Apache-2.0 | Belge algılama, perspektif ve eğim düzeltme |
| [NumPy](https://numpy.org/) | BSD-3-Clause | Görüntü işleme |
| [Pillow](https://github.com/python-pillow/Pillow) | MIT-CMU (HPND) | Görsel okuma/yazma |

## 2. Dolaylı Python bağımlılıkları / Transitive Python dependencies

Yukarıdaki kütüphanelerin kurduğu paketlerin tamamı. *Everything the libraries above
pull in.* Güncellemek için / to refresh: `python scripts/python_licenses.py`.
LGPL-3.0 paketleri (fpdf2, img2pdf) değiştirilmeden, ayrı kütüphane olarak kullanılır.
*LGPL-3.0 packages are used unmodified as separate libraries.*

| Paket / Package | Sürüm | Lisans | Gelen / Pulled in by |
|---|---|---|---|
| [aiohappyeyeballs](https://github.com/aio-libs/aiohappyeyeballs) | 2.7.1 | Python Software Foundation License | pyHanko |
| [aiohttp](https://github.com/aio-libs/aiohttp) | 3.14.5 | Apache-2.0 AND MIT | pyHanko |
| [aiosignal](https://github.com/aio-libs/aiosignal) | 1.4.0 | Apache Software License | pyHanko |
| [annotated-doc](https://github.com/fastapi/annotated-doc) | 0.0.5 | MIT | fastapi |
| [annotated-types](https://github.com/annotated-types/annotated-types) | 0.8.0 | MIT | fastapi |
| [anyio](https://github.com/agronholm/anyio) | 4.15.1 | MIT | fastapi |
| [asn1crypto](https://github.com/wbond/asn1crypto) | 1.5.1 | MIT License | pyHanko |
| [attrs](https://github.com/python-attrs/attrs) | 26.1.0 | MIT | pyHanko |
| [certifi](https://github.com/certifi/python-certifi) | 2026.10.18 | Mozilla Public License 2.0 (MPL 2.0) | pyHanko |
| [cffi](https://github.com/python-cffi/cffi) | 2.1.1 | MIT-0 | ocrmypdf |
| [charset-normalizer](https://pypi.org/project/charset-normalizer/) | 3.5.1 | MIT | ocrmypdf |
| [click](https://github.com/pallets/click/) | 8.5.0 | BSD-3-Clause | uvicorn |
| [cryptography](https://github.com/pyca/cryptography) | 50.0.2 | Apache-2.0 OR BSD-3-Clause | ocrmypdf |
| [defusedxml](https://github.com/tiran/defusedxml) | 0.7.1 | Python Software Foundation License | ocrmypdf |
| [et_xmlfile](https://foss.heptapod.net/openpyxl/et_xmlfile) | 2.0.0 | MIT License | openpyxl |
| [fastapi](https://github.com/fastapi/fastapi) | 0.162.0 | MIT | doğrudan / direct |
| [fire](https://github.com/google/python-fire) | 0.7.1 | Apache-2.0 | pdf2docx |
| [fonttools](http://github.com/fonttools/fonttools) | 4.67.0 | MIT | pdf2docx |
| [fpdf2](https://py-pdf.github.io/fpdf2/) | 2.8.9 | LGPL-3.0-only | ocrmypdf |
| [frozenlist](https://github.com/aio-libs/frozenlist) | 1.8.0 | Apache-2.0 | pyHanko |
| [h11](https://github.com/python-hyper/h11) | 0.16.0 | MIT License | uvicorn |
| [idna](https://github.com/kjd/idna) | 3.20 | BSD-3-Clause | fastapi |
| [img2pdf](https://gitlab.mister-muffin.de/josch/img2pdf) | 0.6.3 | GNU Lesser General Public License v3 (LGPLv3) | ocrmypdf |
| [lxml](https://github.com/lxml/lxml) | 6.1.3 | BSD-3-Clause | pdf2docx |
| [markdown-it-py](https://github.com/executablebooks/markdown-it-py) | 4.2.0 | MIT License | ocrmypdf |
| [mdurl](https://github.com/executablebooks/mdurl) | 0.1.2 | MIT License | ocrmypdf |
| [multidict](https://github.com/aio-libs/multidict) | 7.2.1 | Apache-2.0 | pyHanko |
| [numpy](https://numpy.org) | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | pdf2docx |
| [ocrmypdf](https://github.com/ocrmypdf/OCRmyPDF) | 17.13.0 | MPL-2.0 | doğrudan / direct |
| [opencv-python-headless](https://github.com/opencv/opencv-python) | 5.0.0.93 | Apache Software License | pdf2docx |
| [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl) | 3.1.5 | MIT License | doğrudan / direct |
| [opentelemetry-api](https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api) | 1.45.0 | Apache-2.0 | fastapi |
| [oscrypto](https://github.com/wbond/oscrypto) | 1.3.0 | MIT License | pyHanko |
| [packaging](https://github.com/pypa/packaging) | 26.3 | Apache-2.0 OR BSD-2-Clause | pikepdf |
| [pdf2docx](https://artifex.com/) | 0.5.13 | MIT | doğrudan / direct |
| [pdfminer.six](https://github.com/pdfminer/pdfminer.six) | 20260107 | MIT | ocrmypdf |
| [pikepdf](https://github.com/pikepdf/pikepdf) | 10.17.0 | MPL-2.0 | doğrudan / direct |
| [pillow](https://python-pillow.github.io) | 12.3.0 | MIT-CMU | pikepdf |
| [pluggy](https://github.com/pytest-dev/pluggy) | 1.7.0 | MIT License | ocrmypdf |
| [propcache](https://github.com/aio-libs/propcache) | 0.5.4 | Apache-2.0 | pyHanko |
| [pycparser](https://github.com/eliben/pycparser) | 3.0 | BSD-3-Clause | ocrmypdf |
| [pydantic](https://github.com/pydantic/pydantic) | 2.13.5 | MIT | fastapi |
| [pydantic-settings](https://github.com/pydantic/pydantic-settings) | 2.16.1 | MIT | doğrudan / direct |
| [pydantic_core](https://github.com/pydantic) | 2.46.5 | MIT | fastapi |
| [Pygments](https://pygments.org) | 2.21.0 | BSD-2-Clause | ocrmypdf |
| [pyHanko](https://github.com/MatthiasValvekens/pyHanko) | 0.38.0 | MIT | doğrudan / direct |
| [pyhanko-certvalidator](https://github.com/MatthiasValvekens/pyHanko/tree/master/pkgs/pyhanko-certvalidator) | 0.33.0 | MIT | pyHanko |
| [pymupdf](https://github.com/pymupdf/pymupdf) | 1.28.2 | AGPL-3.0 (or Artifex commercial) | doğrudan / direct |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | 5.13.0 | BSD-3-Clause, Apache-2.0, dependency licenses | ocrmypdf |
| [python-docx](https://github.com/python-openxml/python-docx) | 1.2.0 | MIT License | pdf2docx |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 1.2.3 | BSD-3-Clause | pydantic-settings |
| [rich](https://github.com/Textualize/rich) | 15.0.0 | MIT License | ocrmypdf |
| [starlette](https://github.com/Kludex/starlette) | 1.7.0 | BSD-3-Clause | fastapi |
| [termcolor](https://github.com/termcolor/termcolor) | 3.3.0 | MIT | pdf2docx |
| [typing-inspection](https://github.com/pydantic/typing-inspection) | 0.4.4 | MIT | fastapi |
| [typing_extensions](https://github.com/python/typing_extensions) | 4.16.0 | PSF-2.0 | fastapi |
| [tzlocal](https://github.com/regebro/tzlocal) | 5.4.5 | MIT | pyHanko |
| [uharfbuzz](https://github.com/trufont/uharfbuzz) | 0.57.0 | Apache License 2.0 | ocrmypdf |
| [uritools](https://github.com/tkem/uritools/) | 6.1.3 | MIT | pyHanko |
| [uvicorn](https://uvicorn.dev/) | 0.54.0 | BSD-3-Clause | doğrudan / direct |
| [yarl](https://github.com/aio-libs/yarl) | 1.25.1 | Apache-2.0 | pyHanko |

## 3. Harici programlar / External programs

Uygulamaya gömülmez; ayrı süreç olarak çağrılır. Yoksa yalnızca ilgili özellik
kapanır. *Not bundled; run as separate processes. If missing, only the related
feature is disabled.*

| Program | Lisans | Görev | Kaynak |
|---|---|---|---|
| Tesseract OCR | Apache-2.0 | Metin tanıma | https://github.com/tesseract-ocr/tesseract |
| Tesseract Windows derlemesi (UB Mannheim) | Apache-2.0 | Windows kurulum paketi | https://github.com/UB-Mannheim/tesseract |
| Ghostscript (Artifex) | AGPL-3.0 | PDF/A dönüştürme | https://ghostscript.com/ |
| qpdf (pikepdf içinde) | Apache-2.0 | Düşük seviye PDF, onarım | https://github.com/qpdf/qpdf |
| LibreOffice | MPL-2.0 | Office → PDF | https://www.libreoffice.org/ |
| ClamAV (Cisco Talos) | GPL-2.0 | Virüs taraması | https://www.clamav.net/ |
| pngquant / jbig2enc (isteğe bağlı) | GPL-3.0 / Apache-2.0 | OCR çıktısını küçültme | https://pngquant.org/ · https://github.com/agl/jbig2enc |
| winget (Microsoft) | MIT | `OCR Kur (Windows).bat` içinde Tesseract kurulumu | https://github.com/microsoft/winget-cli |
| Python | PSF-2.0 | Çalışma ortamı | https://www.python.org/ |

## 4. Web arayüzü / Web UI

| Bileşen | Lisans | Görev |
|---|---|---|
| [Svelte](https://github.com/sveltejs/svelte) | MIT | Arayüz çatısı |
| [pdf.js](https://github.com/mozilla/pdf.js) (pdfjs-dist) | Apache-2.0 | Tarayıcıda PDF görüntüleme |
| [Vite](https://github.com/vitejs/vite) (derleme) | MIT | Paketleme |
| [TypeScript](https://github.com/microsoft/TypeScript) (derleme) | Apache-2.0 | Tip denetimi |
| [axe-core](https://github.com/dequelabs/axe-core) (test) | MPL-2.0 | Erişilebilirlik denetimi |
| [Playwright](https://github.com/microsoft/playwright) (test) | Apache-2.0 | Uçtan uca test |

Arayüze paketlenen kodun (Svelte çalışma zamanı, pdf.js) tam lisans metinleri her
derlemede otomatik toplanır ve uygulamada **/licenses.txt** adresinden (başlıktaki
"Lisanslar" bağlantısı) okunur. `web/src/lib/viewer/text-layer.css`, pdf.js'in
`pdf_viewer.css` dosyasından alınmış bir alt kümedir (Apache-2.0).
*Full licence texts of everything bundled into the UI are collected on every build
and served at /licenses.txt; `text-layer.css` is a subset of pdf.js's
`pdf_viewer.css` (Apache-2.0).*

## 5. Fontlar / Fonts

| Font | Lisans |
|---|---|
| DejaVu Sans, Bold (paketlenmiş, `server/adminpdf/assets/fonts`) | Bitstream Vera / DejaVu — bkz. `DejaVu-LICENSE.txt` |
| [Liberation](https://github.com/liberationfonts/liberation-fonts) Sans, Serif (4 stil), Mono (2 stil) 2.1.5 — Red Hat, Google (Arimo/Tinos/Cousine) (paketlenmiş) | SIL OFL 1.1 — bkz. `Liberation-LICENSE.txt`. Arial, Times New Roman ve Courier New ile ölçü uyumlu. |
| pdf.js standart fontları (Foxit, Liberation — `web_dist/pdfjs/standard_fonts`) | BSD-3-Clause (PDFium) / SIL OFL 1.1 — bkz. `LICENSE_FOXIT`, `LICENSE_LIBERATION` |
| Cihazdaki fontlar (Microsoft vb.) | **Paketlenmez, başka cihaza gönderilmez.** Yalnızca o bilgisayarda kullanılır; fontun OS/2 `fsType` alanı izin veriyorsa PDF'e alt küme olarak gömülür. Ağdan bağlanan cihazlar önizlemede kendi fontlarını kullanır. |

pdf.js'in görüntü çözücüleri (JBIG2, OpenJPEG, QCMS) kendi lisans dosyalarıyla
`web_dist/pdfjs/wasm/` içinde, pdf.js lisansı `web_dist/pdfjs/LICENSE` olarak dağıtılır.

## 6. OCR dil verisi / OCR language data

| Bileşen | Lisans | Not |
|---|---|---|
| [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) (`tur`, `eng`, `osd`) | Apache-2.0 | Paketlenmez; Tesseract kurulumuyla veya `OCR Kur (Windows).bat` ile resmi kaynaktan indirilir. |

## 7. Algoritmalar ve yöntemler / Algorithms and methods

Kendi kodumuzla uyguladığımız, başkalarının yayımladığı yöntemler.
*Published methods we implemented in our own code.*

| Yöntem | Nerede | Kaynak |
|---|---|---|
| Fotoğraftaki kâğıdın gerçek en/boy oranı (odak uzaklığı kestirimi) | Görselden PDF, perspektif düzeltme (`core/imaging.py`) | Z. Zhang, L. He, *Whiteboard scanning and image enhancement*, Digital Signal Processing 17(2), 2007 |
| İzdüşüm profili varyansıyla eğiklik bulma | Eğiklik düzeltme | W. Postl, *Detection of linear oblique structures and skew scan in digitized documents*, ICPR 1986 |
| Canny kenar algılama | Belge algılama (OpenCV) | J. Canny, *A Computational Approach to Edge Detection*, IEEE TPAMI 8(6), 1986 |
| Ramer–Douglas–Peucker çokgen sadeleştirme | Belge köşeleri (OpenCV `approxPolyDP`) | D. Douglas, T. Peucker, *The Canadian Cartographer* 10(2), 1973 |
| Otsu eşikleme | Eğiklik analizinde mürekkep ayırma | N. Otsu, *A Threshold Selection Method from Gray-Level Histograms*, IEEE SMC 9(1), 1979 |
| Arka plana bölerek ışık/gölge düzeltme, uyarlamalı eşikleme | "Tarama" iyileştirme | OpenCV belgeleri (Apache-2.0) |
| T.C. Kimlik No denetim haneleri | KVKK tarama | T.C. İçişleri Bakanlığı Nüfus ve Vatandaşlık İşleri algoritması (kamuya açık) |
| IBAN mod-97 doğrulama | KVKK tarama | ISO 13616 / ISO 7064 |
| Luhn kart numarası doğrulama | KVKK tarama | H. P. Luhn, ABD patenti 2,950,048 (1960); ISO/IEC 7812 |
| Vergi Kimlik No denetim hanesi | KVKK tarama | Gelir İdaresi Başkanlığı algoritması (kamuya açık) |
| Metin farkı (SequenceMatcher) | Belge karşılaştırma | Python `difflib` (PSF-2.0) |

## 8. Standartlar / Standards

Uyduğumuz standartların listesi ve nasıl uyduğumuz [STANDARDS.md](STANDARDS.md)
dosyasındadır. Standart metinleri telif hakkı sahiplerine (ISO, ETSI, W3C) aittir ve
bu depoda dağıtılmaz. *Standard texts belong to their publishers and are not
redistributed here.*

## 9. Ticari markalar / Trademarks

Adobe ve Acrobat, Adobe Inc.'in ticari markalarıdır; yalnızca karşılaştırma
amacıyla anılır. Bu proje Adobe ile bağlantılı değildir. *Adobe and Acrobat are
trademarks of Adobe Inc., mentioned for comparison only; this project is not
affiliated with Adobe.*
