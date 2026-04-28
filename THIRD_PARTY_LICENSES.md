# Üçüncü Taraf Kütüphane Lisansları

Bu yazılım, kendi lisansları altında dağıtılan açık kaynak kütüphaneler kullanır.
Aşağıda kullanılan tüm doğrudan bağımlılıklar listelenmiştir.

## Permissive Lisanslı (MIT / BSD / Apache)

Sınırsız kullanım, ticari kullanım, değiştirme ve dağıtım izinli.

| Kütüphane | Lisans | Görev | Sürüm |
|---|---|---|---|
| [FastAPI](https://github.com/tiangolo/fastapi) | MIT | Web framework | 0.136 |
| [Starlette](https://github.com/encode/starlette) | BSD-3-Clause | ASGI toolkit (FastAPI tabanı) | 1.0 |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | ASGI sunucusu | 0.46 |
| [Pydantic](https://github.com/pydantic/pydantic) | MIT | Veri doğrulama | 2.13 |
| [Jinja2](https://github.com/pallets/jinja) | BSD-3-Clause | HTML şablonu | 3.1 |
| [MarkupSafe](https://github.com/pallets/markupsafe) | BSD-3-Clause | Jinja yardımcısı | 3.0 |
| [python-multipart](https://github.com/Kludex/python-multipart) | Apache-2.0 | Form yükleme | 0.0.26 |
| [pdfplumber](https://github.com/jsvine/pdfplumber) | MIT | PDF tablo çıkarma | 0.11 |
| [pdfminer.six](https://github.com/pdfminer/pdfminer.six) | MIT | PDF metin çıkarma | 20251230 |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | Apache-2.0 / BSD-3 | PDFium binding | 5.7 |
| [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl) | MIT | Excel okuma/yazma | 3.1 |
| [python-docx](https://github.com/python-openxml/python-docx) | MIT | Word yazma | 1.2 |
| [lxml](https://lxml.de/) | BSD-3-Clause | XML işleme | 6.1 |
| [EasyOCR](https://github.com/JaidedAI/EasyOCR) | Apache-2.0 | OCR motoru | 1.7 |
| [PyTorch](https://pytorch.org/) | BSD-3-Clause | EasyOCR ML kütüphanesi | 2.11 |
| [TorchVision](https://github.com/pytorch/vision) | BSD-3-Clause | PyTorch görüntü uzantısı | 0.26 |
| [NumPy](https://numpy.org/) | BSD-3-Clause | Sayısal hesaplama | 2.4 |
| [SciPy](https://scipy.org/) | BSD-3-Clause | Bilimsel hesaplama | 1.17 |
| [scikit-image](https://scikit-image.org/) | BSD-3-Clause | Görüntü işleme | 0.26 |
| [OpenCV](https://opencv.org/) (headless) | Apache-2.0 | Bilgisayar görüsü | 4.13 |
| [Pillow](https://python-pillow.org/) | HPND (BSD benzeri) | Görüntü kütüphanesi | 12.2 |
| [Shapely](https://shapely.readthedocs.io/) | BSD-3-Clause | Geometri | 2.1 |
| [pyclipper](https://github.com/fonttools/pyclipper) | MIT | Polygon clipping | 1.4 |
| [fonttools](https://github.com/fonttools/fonttools) | MIT | Font işleme | 4.62 |
| [cryptography](https://github.com/pyca/cryptography) | Apache-2.0 / BSD-3 | Şifreleme | 47.0 |
| [cffi](https://cffi.readthedocs.io/) | MIT | C bağlama | 2.0 |
| [PyYAML](https://github.com/yaml/pyyaml) | MIT | YAML işleme | 6.0 |
| [click](https://github.com/pallets/click) | BSD-3-Clause | CLI | 8.3 |
| [colorama](https://github.com/tartley/colorama) | BSD-3-Clause | Terminal renkleri | 0.4 |
| [anyio](https://github.com/agronholm/anyio) | MIT | Async uyumlamı | 4.13 |
| [h11](https://github.com/python-hyper/h11) | MIT | HTTP/1.1 | 0.16 |
| [httptools](https://github.com/MagicStack/httptools) | MIT | HTTP parser | 0.7 |
| [websockets](https://github.com/python-websockets/websockets) | BSD-3-Clause | WebSocket | 16.0 |
| [watchfiles](https://github.com/samuelcolvin/watchfiles) | MIT | Dosya izleme | 1.1 |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | BSD-3-Clause | Env değişkenleri | 1.2 |
| [filelock](https://github.com/tox-dev/py-filelock) | Unlicense | Dosya kilitleme | 3.29 |
| [networkx](https://networkx.org/) | BSD-3-Clause | Graf algoritmaları (PyTorch dep) | 3.6 |
| [sympy](https://www.sympy.org/) | BSD-3-Clause | Sembolik matematik (PyTorch dep) | 1.14 |
| [imageio](https://imageio.readthedocs.io/) | BSD-2-Clause | Görüntü I/O | 2.37 |
| [tifffile](https://github.com/cgohlke/tifffile) | BSD-3-Clause | TIFF işleme | 2026.4 |

## Copyleft Lisanslı (GPL / AGPL)

Bu kütüphanelerin kullanımı, ana yazılımı da AGPL-3.0 altında dağıtmamızı zorunlu kılıyor
(bu yüzden ana yazılımın lisansı **AGPL-3.0**).

| Kütüphane | Lisans | Görev | Sürüm |
|---|---|---|---|
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) (fitz) | **AGPL-3.0** | Hızlı PDF işleme | 1.27 |
| [pdf2docx](https://github.com/dothinking/pdf2docx) | **GPL-3.0** | PDF → Word dönüşüm | 0.5 |

> **Not:** Permissive lisansa geçilmek istenirse bu iki kütüphane alternatifleriyle değiştirilebilir
> (PyMuPDF → pypdfium2; pdf2docx → manuel docx üretimi).

## Çalışma Zamanı

| Bileşen | Lisans | Kaynak |
|---|---|---|
| Python 3.13 | PSF License | https://www.python.org/ |
| Caveat Font (web) | OFL-1.1 | Google Fonts |

## Lisans Doğrulama

Tüm kütüphane lisansları, kurulum sonrası `dist/Admin_PDF_Toolkit_Portable/python/Lib/site-packages/`
altında her paketin kendi `LICENSE` dosyasında bulunabilir.

---

Son güncelleme: Nisan 2026
