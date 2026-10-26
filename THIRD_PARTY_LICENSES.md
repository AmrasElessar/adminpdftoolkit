# Üçüncü Taraf Lisansları / Third-Party Licences

Bu dosya otomatik üretilir: `python scripts/third_party.py`. *This file is generated: `python scripts/third_party.py`.*

- [Türkçe](#üçüncü-taraf-lisansları-ve-atıflar)
- [English](#third-party-licences-and-attributions)

## Üçüncü Taraf Lisansları ve Atıflar

Admin PDF Toolkit özgür yazılımdır: GNU Affero Genel Kamu Lisansı sürüm 3 veya sonrası (AGPL-3.0-or-later) ile dağıtılır. Ücretsizdir; kullanabilir, inceleyebilir, değiştirebilir ve paylaşabilirsiniz. Değiştirilmiş bir sürümü ağ üzerinden başkalarına sunarsanız, değiştirilmiş kaynak kodunu da onlarla paylaşmanız gerekir. Uygulama başkalarının emeği üzerine kuruludur: kullandığı her kütüphane, program, font, veri ve yöntem aşağıda kaynağı ve lisansıyla anılır. Hepsi ücretsizdir ve AGPL-3.0 ile uyumludur. Emeği geçen herkese teşekkür ederiz.

### Çalıştığı sistemler

**Sunucu: uygulamanın kurulduğu bilgisayar**

- **Windows 10 / 11 (64 bit, x64)** — Kurulumsuz paket: AdminPDFToolkit.exe başlatıcısı; Python, OCR (Tesseract + Türkçe) ve PDF/A (Ghostscript) dahil.
- **macOS 11 ve üstü, Apple Silicon (M1 ve sonrası: M1–M5…)** — Kurulumsuz AdminPDFToolkit.app; ilk açılışta bir kez Sistem Ayarları ▸ Gizlilik ve Güvenlik ▸ Yine de Aç. OCR ve PDF/A için: brew install tesseract tesseract-lang ghostscript.
- **Linux x86_64 (glibc 2.35+: Ubuntu 22.04+, Debian 12+, Linux Mint 21+, Pardus 23+, Fedora 36+)** — Kurulumsuz tar.gz paketi ve başlatıcı penceresi. OCR ve PDF/A için: sudo apt install tesseract-ocr tesseract-ocr-tur ghostscript.
- **Intel Mac, ARM Linux ve diğer sistemler** — Python 3.11+ ile çalışan paket (scripts/start.sh); ilk açılışta kütüphaneleri kurar.
- **Docker (Linux sunucu, NAS)** — OCR, PDF/A, LibreOffice ve ClamAV dahil tüm araçlarla.

**Kullanıcılar: uygulamayı açan cihazlar**

- **Bilgisayar tarayıcıları** — Chrome / Edge 119+, Firefox 121+, Safari 17.4+ (Windows, macOS, Linux).
- **Telefon ve tablet** — Android 10+ (Chrome), iPhone / iPad iOS-iPadOS 17.4+ (Safari); ana ekrana uygulama olarak eklenebilir.
- **Ağ** — Yalnızca aynı yerel ağdaki cihazlar bağlanabilir, bağlantı her zaman HTTPS'tir; internet gerekmez ve internetten erişilemez.

### İlk açılış uyarıları

Uygulama ücretsiz ve açık kaynak olduğu için Microsoft ve Apple'ın ücretli kod imzalama / onay hizmetlerinden geçirilmemiştir. Bu yüzden işletim sistemi ilk açılışta "tanınmayan uygulama" uyarısı gösterir. Bu bir hata ya da virüs bulgusu değildir; aşağıdaki adımlarla bir kez onaylarsınız, sonra uyarı çıkmaz. İndirdiğiniz dosyanın değiştirilmediğini, sürüm sayfasındaki SHA256SUMS listesiyle karşılaştırarak doğrulayabilirsiniz.

- **Windows — "Windows bilgisayarınızı korudu" (SmartScreen):** AdminPDFToolkit.exe'yi ilk çalıştırdığınızda mavi bir pencere çıkar: "Ek bilgi"ye, ardından "Yine de çalıştır"a tıklayın. Zip'i açmadan önce dosyaya sağ tıklayıp Özellikler ▸ "Engellemeyi kaldır" işaretlemek de uyarıyı önler.
- **Windows — Sertifika yükleme onayı ("Güvenlik Uyarısı"):** İlk açılışta Windows, "Admin PDF Toolkit yerel CA" adlı bir sertifikayı yüklemek isteyip istemediğinizi sorar: "Evet" deyin. Bu sertifika yalnızca bu bilgisayardaki uygulamaya ve yerel ağ adreslerine güvenmek içindir; ad kısıtlı olduğundan hiçbir internet sitesi için geçerli değildir.
- **Windows — Güvenlik duvarı (ağ paylaşımı açıkken):** Ağ paylaşımını açınca Windows Defender Güvenlik Duvarı python.exe için izin ister: YALNIZCA "Özel ağlar"ı işaretleyin, "Ortak ağlar"ı işaretlemeyin.
- **macOS — "Geliştirici doğrulanamadığından açılamıyor" (Gatekeeper):** "Bitti"ye basın. Sistem Ayarları ▸ Gizlilik ve Güvenlik'i açıp aşağı kaydırın, "AdminPDFToolkit.app engellendi" yanındaki "Yine de Aç"a basın ve parolanızı girin. Bir kez yeterlidir. (Terminal ile: xattr -dr com.apple.quarantine /Applications/AdminPDFToolkit.app)
- **macOS — Anahtar Zinciri parolası:** İlk açılışta macOS, uygulamanın yerel HTTPS sertifikasına güvenmek için parolanızı ister. Vazgeçerseniz tarayıcı sertifika uyarısı gösterir; sonradan başlatıcıda Diğer ▸ Sertifikaya güven ile yapabilirsiniz.
- **Linux — Tarayıcı sertifika uyarısı:** Linux sistem sertifikalarını otomatik değiştirmiyoruz. Veri klasöründeki tls/ca.crt dosyasını tarayıcının Ayarlar ▸ Gizlilik ve güvenlik ▸ Sertifikalar ▸ Yetkililer bölümünden bir kez içe aktarın ("web sitelerini tanımlamak için güven").
- **Android / iPhone / iPad — Telefonda sertifika uyarısı:** Eşleştirme ekranındaki "Sertifikayı yükle" ile sertifikayı bir kez yükleyin. iPhone / iPad'de ayrıca Ayarlar ▸ Genel ▸ Hakkında ▸ Sertifika Güven Ayarları'ndan açın. Yükleme sırasında parmak izini sunucu bilgisayarındaki "Cihaz bağla" penceresiyle karşılaştırın.

İndirmeyi doğrulamak için sürüm sayfasındaki SHA256SUMS dosyasındaki değerle karşılaştırın — Windows: certutil -hashfile <dosya> SHA256 · macOS: shasum -a 256 <dosya> · Linux: sha256sum <dosya>

### Python kütüphaneleri

Uygulamanın kullandığı Python paketlerinin tamamı: önce doğrudan kullandıklarımız, sonra onların kurduğu paketler. Bu liste kurulu paketlerin kendi kayıtlarından otomatik üretilir (`python scripts/third_party.py`); uygulamadaki liste ise o pakette gerçekten kurulu olanları gösterir.

| Paket | Sürüm | Lisans | Görev / Gelen |
|---|---|---|---|
| [cryptography](https://github.com/pyca/cryptography) | 50.0.2 | Apache-2.0 OR BSD-3-Clause | Sertifikalar, HTTPS yerel CA, güncelleme imzası |
| [fastapi](https://github.com/fastapi/fastapi) | 0.162.0 | MIT | Web API |
| [fonttools](http://github.com/fonttools/fonttools) | 4.67.0 | MIT | Font alt kümeleme, glif kapsamı |
| [numpy](https://numpy.org) | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Görüntü işleme |
| [ocrmypdf](https://github.com/ocrmypdf/OCRmyPDF) | 17.13.0 | MPL-2.0 | OCR ve PDF/A |
| [opencv-python-headless](https://github.com/opencv/opencv-python) | 5.0.0.93 | Apache Software License | Belge algılama, perspektif ve eğiklik düzeltme |
| [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl) | 3.1.5 | MIT License | Excel okuma / yazma |
| [pdf2docx](https://artifex.com/) | 0.5.13 | MIT | PDF → Word |
| [pikepdf](https://github.com/pikepdf/pikepdf) | 10.17.0 | MPL-2.0 | Düşük seviye PDF (qpdf), onarım, güvenlik taraması |
| [pillow](https://python-pillow.org) | 13.0.0 | MIT-CMU | Görsel okuma / yazma |
| [pydantic](https://github.com/pydantic/pydantic) | 2.14.1 | MIT | Veri doğrulama |
| [pydantic-settings](https://github.com/pydantic/pydantic-settings) | 2.16.1 | MIT | Ayarlar |
| [pyHanko](https://github.com/MatthiasValvekens/pyHanko) | 0.38.0 | MIT | PAdES dijital imza |
| [pyhanko-certvalidator](https://github.com/MatthiasValvekens/pyHanko/tree/master/pkgs/pyhanko-certvalidator) | 0.33.0 | MIT | İmza sertifikası doğrulama |
| [pymupdf](https://github.com/pymupdf/pymupdf) | 1.28.2 | AGPL-3.0 (or Artifex commercial) | PDF okuma, yazma, görüntüleme, düzenleme, karartma |
| [python-docx](https://github.com/python-openxml/python-docx) | 1.2.0 | MIT License | Word okuma |
| [segno](https://github.com/heuer/segno/) | 1.6.6 | BSD License | Telefon / tablet eşleştirme QR kodu |
| [uvicorn](https://uvicorn.dev/) | 0.54.0 | BSD-3-Clause | HTTPS sunucusu |
| [aiohappyeyeballs](https://github.com/aio-libs/aiohappyeyeballs) | 2.7.1 | Python Software Foundation License | pyHanko ile gelir |
| [aiohttp](https://github.com/aio-libs/aiohttp) | 3.14.5 | Apache-2.0 AND MIT | pyHanko ile gelir |
| [aiosignal](https://github.com/aio-libs/aiosignal) | 1.4.0 | Apache Software License | pyHanko ile gelir |
| [annotated-doc](https://github.com/fastapi/annotated-doc) | 0.0.5 | MIT | fastapi ile gelir |
| [annotated-types](https://github.com/annotated-types/annotated-types) | 0.8.0 | MIT | pydantic ile gelir |
| [anyio](https://github.com/agronholm/anyio) | 4.15.1 | MIT | fastapi ile gelir |
| [asn1crypto](https://github.com/wbond/asn1crypto) | 1.5.1 | MIT License | pyHanko ile gelir |
| [attrs](https://github.com/python-attrs/attrs) | 26.1.0 | MIT | pyHanko ile gelir |
| [certifi](https://github.com/certifi/python-certifi) | 2026.10.23 | Mozilla Public License 2.0 (MPL 2.0) | pyhanko-certvalidator ile gelir |
| [cffi](https://github.com/python-cffi/cffi) | 2.1.1 | MIT-0 | cryptography ile gelir |
| [charset-normalizer](https://github.com/jawah/charset_normalizer) | 3.5.2 | MIT | ocrmypdf ile gelir |
| [click](https://github.com/pallets/click/) | 8.5.0 | BSD-3-Clause | uvicorn ile gelir |
| [defusedxml](https://github.com/tiran/defusedxml) | 0.7.1 | Python Software Foundation License | ocrmypdf ile gelir |
| [et_xmlfile](https://foss.heptapod.net/openpyxl/et_xmlfile) | 2.0.0 | MIT License | openpyxl ile gelir |
| [fire](https://github.com/google/python-fire) | 0.7.1 | Apache-2.0 | pdf2docx ile gelir |
| [fpdf2](https://py-pdf.github.io/fpdf2/) | 2.8.9 | LGPL-3.0-only | ocrmypdf ile gelir |
| [frozenlist](https://github.com/aio-libs/frozenlist) | 1.8.0 | Apache-2.0 | pyHanko ile gelir |
| [h11](https://github.com/python-hyper/h11) | 0.16.0 | MIT License | uvicorn ile gelir |
| [idna](https://github.com/kjd/idna) | 3.20 | BSD-3-Clause | fastapi ile gelir |
| [img2pdf](https://gitlab.mister-muffin.de/josch/img2pdf) | 0.6.3 | GNU Lesser General Public License v3 (LGPLv3) | ocrmypdf ile gelir |
| [lxml](https://github.com/lxml/lxml) | 6.1.3 | BSD-3-Clause | python-docx ile gelir |
| [markdown-it-py](https://github.com/executablebooks/markdown-it-py) | 4.2.0 | MIT License | ocrmypdf ile gelir |
| [mdurl](https://github.com/executablebooks/mdurl) | 0.1.2 | MIT License | ocrmypdf ile gelir |
| [multidict](https://github.com/aio-libs/multidict) | 7.2.1 | Apache-2.0 | pyHanko ile gelir |
| [opentelemetry-api](https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api) | 1.45.1 | Apache-2.0 | fastapi ile gelir |
| [oscrypto](https://github.com/wbond/oscrypto) | 1.3.0 | MIT License | pyhanko-certvalidator ile gelir |
| [packaging](https://github.com/pypa/packaging) | 26.3 | Apache-2.0 OR BSD-2-Clause | pikepdf ile gelir |
| [pdfminer.six](https://github.com/pdfminer/pdfminer.six) | 20260107 | MIT | ocrmypdf ile gelir |
| [pluggy](https://github.com/pytest-dev/pluggy) | 1.7.0 | MIT License | ocrmypdf ile gelir |
| [propcache](https://github.com/aio-libs/propcache) | 0.5.4 | Apache-2.0 | pyHanko ile gelir |
| [pycparser](https://github.com/eliben/pycparser) | 3.12 | BSD-3-Clause | cryptography ile gelir |
| [pydantic_core](https://github.com/pydantic) | 2.50.1 | MIT | pydantic ile gelir |
| [Pygments](https://pygments.org) | 2.21.0 | BSD-2-Clause | ocrmypdf ile gelir |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | 5.14.0 | BSD-3-Clause, Apache-2.0, dependency licenses | ocrmypdf ile gelir |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 1.2.4 | BSD-3-Clause | pydantic-settings ile gelir |
| [rich](https://github.com/Textualize/rich) | 15.0.0 | MIT License | ocrmypdf ile gelir |
| [starlette](https://github.com/Kludex/starlette) | 1.10.0 | BSD-3-Clause | fastapi ile gelir |
| [termcolor](https://github.com/termcolor/termcolor) | 3.3.0 | MIT | pdf2docx ile gelir |
| [typing-inspection](https://github.com/pydantic/typing-inspection) | 0.4.4 | MIT | fastapi ile gelir |
| [typing_extensions](https://github.com/python/typing_extensions) | 4.16.0 | PSF-2.0 | fastapi ile gelir |
| [tzlocal](https://github.com/regebro/tzlocal) | 5.4.5 | MIT | pyHanko ile gelir |
| [uharfbuzz](https://github.com/trufont/uharfbuzz) | 0.57.0 | Apache License 2.0 | ocrmypdf ile gelir |
| [uritools](https://github.com/tkem/uritools/) | 6.1.3 | MIT | pyhanko-certvalidator ile gelir |
| [yarl](https://github.com/aio-libs/yarl) | 1.25.1 | Apache-2.0 | pyHanko ile gelir |

### Web arayüzü

Arayüze paketlenen npm kodunun listesi ve tam lisans metinleri her derlemede otomatik toplanır; uygulamada Hakkında ve Lisanslar penceresinde ve /licenses.txt adresinde okunur. Şu an: [Svelte](https://svelte.dev) (MIT) ve [pdf.js](https://github.com/mozilla/pdf.js) (Apache-2.0). `web/src/lib/viewer/text-layer.css`, pdf.js'in `pdf_viewer.css` dosyasının bir alt kümesidir (Apache-2.0).

### Programlar ve araçlar

Ayrı süreç olarak çalıştırılır. Yoksa yalnızca ilgili özellik kapanır.

| Bileşen | Lisans | Görev | Nerede |
|---|---|---|---|
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) | Apache-2.0 | Metin tanıma (OCR) | Windows paketinde ocr/ klasöründe gömülü; diğer sistemlerde sistemden kurulur |
| [Tesseract Windows build (UB Mannheim)](https://github.com/UB-Mannheim/tesseract) | Apache-2.0 | Tesseract'ın Windows derlemesi ve DLL'leri | Windows paketi (ocr/); dosyaların tam listesi aşağıda 'Pakete gömülü dosyalar' bölümünde |
| [Leptonica](http://www.leptonica.org/) | BSD-2-Clause | Tesseract'ın görüntü kütüphanesi | Windows paketi, Tesseract ile |
| [libpng · libjpeg-turbo · libtiff · zlib · libwebp · OpenJPEG · giflib](https://github.com/UB-Mannheim/tesseract) | libpng · IJG/BSD-3-Clause · libtiff · Zlib · BSD-3-Clause · BSD-2-Clause · MIT | Tesseract'ın görsel biçimi kütüphaneleri | Windows paketi, Tesseract ile |
| [Ghostscript (Artifex)](https://ghostscript.com/) | AGPL-3.0 | PDF/A dönüştürme | Windows paketinde gs/ klasöründe değiştirilmeden gömülü; birebir kaynak arşivi her sürümle birlikte yayımlanır (AGPL-3.0 §6). Diğer sistemlerde sistemden kurulur |
| [qpdf](https://github.com/qpdf/qpdf) | Apache-2.0 | Düşük seviye PDF, onarım | pikepdf'in içinde |
| [LibreOffice](https://www.libreoffice.org/) | MPL-2.0 | Word / Excel / PowerPoint → PDF (yüksek doğruluk) | İsteğe bağlı, sistemden; Docker'da dahil |
| [ClamAV (Cisco Talos)](https://www.clamav.net/) | GPL-2.0 | Virüs taraması | İsteğe bağlı, sistemden; Docker'da dahil |
| [pngquant · jbig2enc](https://pngquant.org/) | GPL-3.0 · Apache-2.0 | OCR çıktısını küçültme (OCRmyPDF üzerinden) | İsteğe bağlı, sistemden |
| [winget (Microsoft)](https://github.com/microsoft/winget-cli) | MIT | Python paketiyle çalışırken Tesseract kurulumu (OCR Kur.bat) | Windows'un parçası; dağıtılmaz |

### Paketlere gömülü çalışma ortamları

Kurulumsuz paketlerin içinde gelir.

| Bileşen | Lisans | Görev | Nerede |
|---|---|---|---|
| [Python (CPython, Windows embeddable)](https://www.python.org/) | PSF-2.0 | Çalışma ortamı; içinde OpenSSL (Apache-2.0), SQLite (kamu malı), libffi (MIT), bzip2, xz (0BSD), zlib, expat (MIT), mpdecimal (BSD-2-Clause) | Windows paketi (python/) |
| [python-build-standalone](https://github.com/astral-sh/python-build-standalone) | PSF-2.0 (CPython) · MPL-2.0 (build scripts) | Taşınabilir CPython; içinde Tcl/Tk (Tcl lisansı, BSD tarzı) başlatıcı penceresi için, OpenSSL (Apache-2.0), SQLite (kamu malı), libffi (MIT), zlib, bzip2, xz (0BSD), expat (MIT), mpdecimal (BSD-2-Clause), ncurses (MIT-X11), libedit (BSD-3-Clause) | macOS ve Linux paketleri |
| [.NET Framework 4.x (Microsoft)](https://dotnet.microsoft.com/) | Windows bileşeni / Windows component | AdminPDFToolkit.exe başlatıcısı bununla derlenir ve çalışır | Windows'un parçası; dağıtılmaz |

### Docker görüntüsü

Yalnızca Docker kurulumunda.

| Bileşen | Lisans | Görev | Nerede |
|---|---|---|---|
| [python:3.13-slim (Debian)](https://hub.docker.com/_/python) | PSF-2.0 · Debian (DFSG) | Temel görüntü | Docker |
| [tini](https://github.com/krallin/tini) | MIT | Süreç yöneticisi | Docker |
| [Tesseract (tur, eng) · Ghostscript · qpdf · ClamAV · LibreOffice (writer, calc, impress)](https://packages.debian.org/) | Apache-2.0 · AGPL-3.0 · Apache-2.0 · GPL-2.0 · MPL-2.0 | Debian paketleri olarak | Docker |
| [fonts-dejavu-core · fonts-liberation2 · fonts-noto-core](https://packages.debian.org/) | Bitstream Vera · SIL OFL 1.1 · SIL OFL 1.1 | Sistem fontları | Docker |

### Fontlar

Bilgisayardaki fontlar (Microsoft vb.) pakete konmaz ve başka cihaza gönderilmez; yalnızca o bilgisayarda, fontun izin verdiği ölçüde (OS/2 fsType) PDF'e alt küme olarak gömülür.

| Bileşen | Lisans | Görev | Nerede |
|---|---|---|---|
| [DejaVu Sans (Regular, Bold)](https://dejavu-fonts.github.io/) | Bitstream Vera / DejaVu | Türkçe karakter kapsamlı varsayılan font | Tüm paketler (assets/fonts, DejaVu-LICENSE.txt) |
| [Liberation Sans · Serif · Mono 2.1.5 (Red Hat, Google)](https://github.com/liberationfonts/liberation-fonts) | SIL OFL 1.1 | Arial, Times New Roman ve Courier New ile ölçü uyumlu | Tüm paketler (assets/fonts, Liberation-LICENSE.txt) |
| [pdf.js standard fonts (Foxit, Liberation)](https://github.com/mozilla/pdf.js) | BSD-3-Clause (PDFium) · SIL OFL 1.1 | Tarayıcıda PDF'in standart 14 fontu | web_dist/pdfjs/standard_fonts (LICENSE_FOXIT, LICENSE_LIBERATION) |

### Veriler

| Bileşen | Lisans | Görev | Nerede |
|---|---|---|---|
| [tessdata_fast (tur, eng, osd) 4.1.0](https://github.com/tesseract-ocr/tessdata_fast) | Apache-2.0 | OCR dil modelleri | Windows paketi (ocr/tessdata, SHA-256 sabitli) |
| [pdf.js CMaps · ICC profiles · wasm decoders (OpenJPEG, JBIG2, QCMS)](https://github.com/mozilla/pdf.js) | Apache-2.0 · BSD-3-Clause (Adobe CMaps) · BSD-2-Clause (OpenJPEG) · MIT (QCMS) | Tarayıcıda Asya fontları, renk profilleri, JPEG 2000 / JBIG2 görselleri | web_dist/pdfjs (lisans dosyalarıyla) |

### Geliştirme, derleme ve test araçları

Uygulamayı üretmek ve sınamak için kullanılır; paketlere girmez.

| Bileşen | Lisans | Görev | Nerede |
|---|---|---|---|
| [Node.js](https://nodejs.org/) | MIT | Arayüz derlemesi | Derleme |
| [Vite · Rolldown](https://github.com/vitejs/vite) | MIT | Arayüz paketleme | Derleme |
| [TypeScript](https://github.com/microsoft/TypeScript) | Apache-2.0 | Tip denetimi | Derleme |
| [@sveltejs/vite-plugin-svelte · svelte-check · @tsconfig/svelte](https://github.com/sveltejs) | MIT | Svelte derleme ve denetim | Derleme |
| [Playwright](https://github.com/microsoft/playwright) | Apache-2.0 | Uçtan uca test | Test |
| [axe-core (Deque)](https://github.com/dequelabs/axe-core) | MPL-2.0 | Erişilebilirlik (WCAG) denetimi | Test |
| [pytest · httpx · ruff · mypy](https://pytest.org/) | MIT · BSD-3-Clause · MIT · MIT | Sunucu testleri, biçim ve tip denetimi | Test |
| [pip · setuptools · wheel](https://pip.pypa.io/) | MIT | Python paketleme | Derleme |
| [7-Zip](https://www.7-zip.org/) | LGPL-2.1 | Tesseract / Ghostscript kurulum dosyalarını derlemede açmak | Derleme (Windows) |
| [Docker Buildx](https://github.com/docker/buildx) | Apache-2.0 | Docker görüntüsü | Derleme |

### Yöntemler ve algoritmalar

Başkalarının yayımladığı, kendi kodumuzla uyguladığımız yöntemler.

| Yöntem | Nerede | Kaynak |
|---|---|---|
| Fotoğraftaki kâğıdın gerçek en/boy oranı (odak uzaklığı kestirimi) | Görselden PDF, perspektif düzeltme | Z. Zhang, L. He, Whiteboard scanning and image enhancement, Digital Signal Processing 17(2), 2007 |
| İzdüşüm profili varyansıyla eğiklik bulma | Eğiklik düzeltme | W. Postl, Detection of linear oblique structures and skew scan in digitized documents, ICPR 1986 |
| Canny kenar algılama | Belge algılama (OpenCV) | J. Canny, A Computational Approach to Edge Detection, IEEE TPAMI 8(6), 1986 |
| Ramer–Douglas–Peucker çokgen sadeleştirme | Belge köşeleri (OpenCV) | D. Douglas, T. Peucker, The Canadian Cartographer 10(2), 1973 |
| Otsu eşikleme | Eğiklik analizinde mürekkep ayırma | N. Otsu, A Threshold Selection Method from Gray-Level Histograms, IEEE SMC 9(1), 1979 |
| Arka plana bölerek gölge düzeltme, uyarlamalı eşikleme | Tarama iyileştirme | OpenCV documentation (Apache-2.0) |
| T.C. Kimlik No denetim haneleri | KVKK tarama | T.C. İçişleri Bakanlığı Nüfus ve Vatandaşlık İşleri (public algorithm) |
| IBAN mod-97 doğrulama | KVKK tarama | ISO 13616 / ISO 7064 |
| Luhn kart numarası doğrulama | KVKK tarama | H. P. Luhn, US patent 2,950,048 (1960); ISO/IEC 7812 |
| Vergi Kimlik No denetim hanesi | KVKK tarama | Gelir İdaresi Başkanlığı (public algorithm) |
| Metin farkı (SequenceMatcher) | Belge karşılaştırma | Python difflib (PSF-2.0) |
| Ed25519 imza, SHA-256 | Güncelleme ve paket doğrulama | RFC 8032; FIPS 180-4 (via cryptography / hashlib) |

### Notlar

- Standartlar ve nasıl uyduğumuz STANDARDS.md dosyasındadır; standart metinleri yayıncılarına (ISO, ETSI, W3C) aittir ve dağıtılmaz.
- Adobe ve Acrobat, Adobe Inc.'in ticari markalarıdır; yalnızca karşılaştırma amacıyla anılır. Bu proje Adobe ile bağlantılı değildir. Apple, macOS, iPhone ve iPad Apple Inc.'in; Windows Microsoft Corporation'ın ticari markalarıdır.
- LGPL-3.0 lisanslı Python paketleri (fpdf2, img2pdf) değiştirilmeden, ayrı kütüphane olarak kullanılır.

## Third-Party Licences and Attributions

Admin PDF Toolkit is free software, distributed under the GNU Affero General Public License version 3 or later (AGPL-3.0-or-later). It costs nothing; you may use, study, change and share it. If you offer a modified version to others over a network, you must share the modified source code with them too. The app is built on other people's work: every library, program, font, dataset and method it uses is credited below with its source and licence. All are free and compatible with AGPL-3.0. Thank you to everyone involved.

### Supported systems

**Server: the computer the app runs on**

- **Windows 10 / 11 (64-bit, x64)** — No-install package: AdminPDFToolkit.exe launcher; Python, OCR (Tesseract + Turkish) and PDF/A (Ghostscript) included.
- **macOS 11 or later, Apple Silicon (M1 and later: M1–M5…)** — No-install AdminPDFToolkit.app; on first start once: System Settings ▸ Privacy & Security ▸ Open Anyway. For OCR and PDF/A: brew install tesseract tesseract-lang ghostscript.
- **Linux x86_64 (glibc 2.35+: Ubuntu 22.04+, Debian 12+, Linux Mint 21+, Pardus 23+, Fedora 36+)** — No-install tar.gz package with the launcher window. For OCR and PDF/A: sudo apt install tesseract-ocr tesseract-ocr-tur ghostscript.
- **Intel Macs, ARM Linux and other systems** — Package for Python 3.11+ (scripts/start.sh); installs the libraries on first start.
- **Docker (Linux server, NAS)** — With every tool: OCR, PDF/A, LibreOffice and ClamAV.

**Users: the devices that open the app**

- **Desktop browsers** — Chrome / Edge 119+, Firefox 121+, Safari 17.4+ (Windows, macOS, Linux).
- **Phones and tablets** — Android 10+ (Chrome), iPhone / iPad on iOS / iPadOS 17.4+ (Safari); can be added to the home screen as an app.
- **Network** — Only devices on the same local network can connect, always over HTTPS; no internet is needed and the app cannot be reached from the internet.

### First-start warnings

Because the app is free and open source, it has not gone through Microsoft's and Apple's paid code-signing / approval services. The operating system therefore shows an "unrecognised app" warning on first start. This is not an error or a virus finding; you confirm it once with the steps below and it does not appear again. You can check that your download was not altered by comparing it with the SHA256SUMS list on the release page.

- **Windows — "Windows protected your PC" (SmartScreen):** When you first run AdminPDFToolkit.exe a blue window appears: click "More info", then "Run anyway". Ticking Properties ▸ "Unblock" on the zip before extracting it also avoids the warning.
- **Windows — Certificate install confirmation ("Security Warning"):** On first start Windows asks whether to install a certificate named "Admin PDF Toolkit local CA": answer "Yes". It only makes this PC trust the app and local-network addresses; being name-constrained, it is not valid for any website.
- **Windows — Firewall (with network sharing on):** When you turn on network sharing, Windows Defender Firewall asks about python.exe: tick ONLY "Private networks", not "Public networks".
- **macOS — "cannot be opened because the developer cannot be verified" (Gatekeeper):** Click "Done". Open System Settings ▸ Privacy & Security, scroll down, click "Open Anyway" next to "AdminPDFToolkit.app was blocked" and enter your password. Once is enough. (In Terminal: xattr -dr com.apple.quarantine /Applications/AdminPDFToolkit.app)
- **macOS — Keychain password:** On first start macOS asks for your password to trust the app's local HTTPS certificate. If you cancel, the browser shows a certificate warning; you can do it later via More ▸ Trust the certificate in the launcher.
- **Linux — Browser certificate warning:** We do not change Linux system certificates automatically. Import tls/ca.crt from the data folder once under the browser's Settings ▸ Privacy and security ▸ Certificates ▸ Authorities ("trust for identifying websites").
- **Android / iPhone / iPad — Certificate warning on phones:** Install the certificate once via "Install certificate" on the pairing screen. On iPhone / iPad also enable it under Settings ▸ General ▸ About ▸ Certificate Trust Settings. While installing, compare the fingerprint with the "Connect device" window on the server PC.

To verify a download, compare it with the value in SHA256SUMS on the release page — Windows: certutil -hashfile <file> SHA256 · macOS: shasum -a 256 <file> · Linux: sha256sum <file>

### Python libraries

Every Python package the app uses: first the ones we import ourselves, then what they pull in. Generated from the installed packages' own metadata (`python scripts/third_party.py`); the list inside the app shows exactly what is installed in that package.

| Package | Version | Licence | Role / Pulled in by |
|---|---|---|---|
| [cryptography](https://github.com/pyca/cryptography) | 50.0.2 | Apache-2.0 OR BSD-3-Clause | Certificates, the local HTTPS CA, update signatures |
| [fastapi](https://github.com/fastapi/fastapi) | 0.162.0 | MIT | Web API |
| [fonttools](http://github.com/fonttools/fonttools) | 4.67.0 | MIT | Font subsetting, glyph coverage |
| [numpy](https://numpy.org) | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Image processing |
| [ocrmypdf](https://github.com/ocrmypdf/OCRmyPDF) | 17.13.0 | MPL-2.0 | OCR and PDF/A |
| [opencv-python-headless](https://github.com/opencv/opencv-python) | 5.0.0.93 | Apache Software License | Document detection, perspective and skew correction |
| [openpyxl](https://foss.heptapod.net/openpyxl/openpyxl) | 3.1.5 | MIT License | Excel reading / writing |
| [pdf2docx](https://artifex.com/) | 0.5.13 | MIT | PDF → Word |
| [pikepdf](https://github.com/pikepdf/pikepdf) | 10.17.0 | MPL-2.0 | Low-level PDF (qpdf), repair, security scan |
| [pillow](https://python-pillow.org) | 13.0.0 | MIT-CMU | Image reading / writing |
| [pydantic](https://github.com/pydantic/pydantic) | 2.14.1 | MIT | Data validation |
| [pydantic-settings](https://github.com/pydantic/pydantic-settings) | 2.16.1 | MIT | Settings |
| [pyHanko](https://github.com/MatthiasValvekens/pyHanko) | 0.38.0 | MIT | PAdES digital signatures |
| [pyhanko-certvalidator](https://github.com/MatthiasValvekens/pyHanko/tree/master/pkgs/pyhanko-certvalidator) | 0.33.0 | MIT | Signing certificate validation |
| [pymupdf](https://github.com/pymupdf/pymupdf) | 1.28.2 | AGPL-3.0 (or Artifex commercial) | PDF reading, writing, rendering, editing, redaction |
| [python-docx](https://github.com/python-openxml/python-docx) | 1.2.0 | MIT License | Word reading |
| [segno](https://github.com/heuer/segno/) | 1.6.6 | BSD License | Phone / tablet pairing QR code |
| [uvicorn](https://uvicorn.dev/) | 0.54.0 | BSD-3-Clause | HTTPS server |
| [aiohappyeyeballs](https://github.com/aio-libs/aiohappyeyeballs) | 2.7.1 | Python Software Foundation License | via pyHanko |
| [aiohttp](https://github.com/aio-libs/aiohttp) | 3.14.5 | Apache-2.0 AND MIT | via pyHanko |
| [aiosignal](https://github.com/aio-libs/aiosignal) | 1.4.0 | Apache Software License | via pyHanko |
| [annotated-doc](https://github.com/fastapi/annotated-doc) | 0.0.5 | MIT | via fastapi |
| [annotated-types](https://github.com/annotated-types/annotated-types) | 0.8.0 | MIT | via pydantic |
| [anyio](https://github.com/agronholm/anyio) | 4.15.1 | MIT | via fastapi |
| [asn1crypto](https://github.com/wbond/asn1crypto) | 1.5.1 | MIT License | via pyHanko |
| [attrs](https://github.com/python-attrs/attrs) | 26.1.0 | MIT | via pyHanko |
| [certifi](https://github.com/certifi/python-certifi) | 2026.10.23 | Mozilla Public License 2.0 (MPL 2.0) | via pyhanko-certvalidator |
| [cffi](https://github.com/python-cffi/cffi) | 2.1.1 | MIT-0 | via cryptography |
| [charset-normalizer](https://github.com/jawah/charset_normalizer) | 3.5.2 | MIT | via ocrmypdf |
| [click](https://github.com/pallets/click/) | 8.5.0 | BSD-3-Clause | via uvicorn |
| [defusedxml](https://github.com/tiran/defusedxml) | 0.7.1 | Python Software Foundation License | via ocrmypdf |
| [et_xmlfile](https://foss.heptapod.net/openpyxl/et_xmlfile) | 2.0.0 | MIT License | via openpyxl |
| [fire](https://github.com/google/python-fire) | 0.7.1 | Apache-2.0 | via pdf2docx |
| [fpdf2](https://py-pdf.github.io/fpdf2/) | 2.8.9 | LGPL-3.0-only | via ocrmypdf |
| [frozenlist](https://github.com/aio-libs/frozenlist) | 1.8.0 | Apache-2.0 | via pyHanko |
| [h11](https://github.com/python-hyper/h11) | 0.16.0 | MIT License | via uvicorn |
| [idna](https://github.com/kjd/idna) | 3.20 | BSD-3-Clause | via fastapi |
| [img2pdf](https://gitlab.mister-muffin.de/josch/img2pdf) | 0.6.3 | GNU Lesser General Public License v3 (LGPLv3) | via ocrmypdf |
| [lxml](https://github.com/lxml/lxml) | 6.1.3 | BSD-3-Clause | via python-docx |
| [markdown-it-py](https://github.com/executablebooks/markdown-it-py) | 4.2.0 | MIT License | via ocrmypdf |
| [mdurl](https://github.com/executablebooks/mdurl) | 0.1.2 | MIT License | via ocrmypdf |
| [multidict](https://github.com/aio-libs/multidict) | 7.2.1 | Apache-2.0 | via pyHanko |
| [opentelemetry-api](https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api) | 1.45.1 | Apache-2.0 | via fastapi |
| [oscrypto](https://github.com/wbond/oscrypto) | 1.3.0 | MIT License | via pyhanko-certvalidator |
| [packaging](https://github.com/pypa/packaging) | 26.3 | Apache-2.0 OR BSD-2-Clause | via pikepdf |
| [pdfminer.six](https://github.com/pdfminer/pdfminer.six) | 20260107 | MIT | via ocrmypdf |
| [pluggy](https://github.com/pytest-dev/pluggy) | 1.7.0 | MIT License | via ocrmypdf |
| [propcache](https://github.com/aio-libs/propcache) | 0.5.4 | Apache-2.0 | via pyHanko |
| [pycparser](https://github.com/eliben/pycparser) | 3.12 | BSD-3-Clause | via cryptography |
| [pydantic_core](https://github.com/pydantic) | 2.50.1 | MIT | via pydantic |
| [Pygments](https://pygments.org) | 2.21.0 | BSD-2-Clause | via ocrmypdf |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | 5.14.0 | BSD-3-Clause, Apache-2.0, dependency licenses | via ocrmypdf |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 1.2.4 | BSD-3-Clause | via pydantic-settings |
| [rich](https://github.com/Textualize/rich) | 15.0.0 | MIT License | via ocrmypdf |
| [starlette](https://github.com/Kludex/starlette) | 1.10.0 | BSD-3-Clause | via fastapi |
| [termcolor](https://github.com/termcolor/termcolor) | 3.3.0 | MIT | via pdf2docx |
| [typing-inspection](https://github.com/pydantic/typing-inspection) | 0.4.4 | MIT | via fastapi |
| [typing_extensions](https://github.com/python/typing_extensions) | 4.16.0 | PSF-2.0 | via fastapi |
| [tzlocal](https://github.com/regebro/tzlocal) | 5.4.5 | MIT | via pyHanko |
| [uharfbuzz](https://github.com/trufont/uharfbuzz) | 0.57.0 | Apache License 2.0 | via ocrmypdf |
| [uritools](https://github.com/tkem/uritools/) | 6.1.3 | MIT | via pyhanko-certvalidator |
| [yarl](https://github.com/aio-libs/yarl) | 1.25.1 | Apache-2.0 | via pyHanko |

### Web UI

The npm code bundled into the UI and its full licence texts are collected on every build and shown in the app's About & Licences window and at /licenses.txt. Currently: [Svelte](https://svelte.dev) (MIT) and [pdf.js](https://github.com/mozilla/pdf.js) (Apache-2.0). `web/src/lib/viewer/text-layer.css` is a subset of pdf.js's `pdf_viewer.css` (Apache-2.0).

### Programs and tools

Run as separate processes. If one is missing, only its feature is off.

| Component | Licence | Role | Where |
|---|---|---|---|
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) | Apache-2.0 | Text recognition (OCR) | Bundled in ocr/ in the Windows package; installed from the system elsewhere |
| [Tesseract Windows build (UB Mannheim)](https://github.com/UB-Mannheim/tesseract) | Apache-2.0 | Windows build of Tesseract and its DLLs | Windows package (ocr/); full file list below under 'Files bundled in this package' |
| [Leptonica](http://www.leptonica.org/) | BSD-2-Clause | Tesseract's image library | Windows package, with Tesseract |
| [libpng · libjpeg-turbo · libtiff · zlib · libwebp · OpenJPEG · giflib](https://github.com/UB-Mannheim/tesseract) | libpng · IJG/BSD-3-Clause · libtiff · Zlib · BSD-3-Clause · BSD-2-Clause · MIT | Tesseract's image format libraries | Windows package, with Tesseract |
| [Ghostscript (Artifex)](https://ghostscript.com/) | AGPL-3.0 | PDF/A conversion | Bundled unmodified in gs/ in the Windows package; its exact source tarball is published with every release (AGPL-3.0 §6). Installed from the system elsewhere |
| [qpdf](https://github.com/qpdf/qpdf) | Apache-2.0 | Low-level PDF, repair | Inside pikepdf |
| [LibreOffice](https://www.libreoffice.org/) | MPL-2.0 | Word / Excel / PowerPoint → PDF (high fidelity) | Optional, from the system; included in Docker |
| [ClamAV (Cisco Talos)](https://www.clamav.net/) | GPL-2.0 | Virus scan | Optional, from the system; included in Docker |
| [pngquant · jbig2enc](https://pngquant.org/) | GPL-3.0 · Apache-2.0 | Shrinking OCR output (through OCRmyPDF) | Optional, from the system |
| [winget (Microsoft)](https://github.com/microsoft/winget-cli) | MIT | Installing Tesseract with the Python package (OCR Kur.bat) | Part of Windows; not redistributed |

### Runtimes bundled in the packages

Shipped inside the no-install packages.

| Component | Licence | Role | Where |
|---|---|---|---|
| [Python (CPython, Windows embeddable)](https://www.python.org/) | PSF-2.0 | Runtime; includes OpenSSL (Apache-2.0), SQLite (public domain), libffi (MIT), bzip2, xz (0BSD), zlib, expat (MIT), mpdecimal (BSD-2-Clause) | Windows package (python/) |
| [python-build-standalone](https://github.com/astral-sh/python-build-standalone) | PSF-2.0 (CPython) · MPL-2.0 (build scripts) | Relocatable CPython; includes Tcl/Tk (Tcl licence, BSD-style) for the launcher window, OpenSSL (Apache-2.0), SQLite (public domain), libffi (MIT), zlib, bzip2, xz (0BSD), expat (MIT), mpdecimal (BSD-2-Clause), ncurses (MIT-X11), libedit (BSD-3-Clause) | macOS and Linux packages |
| [.NET Framework 4.x (Microsoft)](https://dotnet.microsoft.com/) | Windows bileşeni / Windows component | AdminPDFToolkit.exe is built with and runs on it | Part of Windows; not redistributed |

### Docker image

Docker installs only.

| Component | Licence | Role | Where |
|---|---|---|---|
| [python:3.13-slim (Debian)](https://hub.docker.com/_/python) | PSF-2.0 · Debian (DFSG) | Base image | Docker |
| [tini](https://github.com/krallin/tini) | MIT | Init process | Docker |
| [Tesseract (tur, eng) · Ghostscript · qpdf · ClamAV · LibreOffice (writer, calc, impress)](https://packages.debian.org/) | Apache-2.0 · AGPL-3.0 · Apache-2.0 · GPL-2.0 · MPL-2.0 | As Debian packages | Docker |
| [fonts-dejavu-core · fonts-liberation2 · fonts-noto-core](https://packages.debian.org/) | Bitstream Vera · SIL OFL 1.1 · SIL OFL 1.1 | System fonts | Docker |

### Fonts

Fonts installed on the computer (Microsoft etc.) are never packaged or sent to other devices; they are only embedded into PDFs on that computer, as far as the font allows (OS/2 fsType).

| Component | Licence | Role | Where |
|---|---|---|---|
| [DejaVu Sans (Regular, Bold)](https://dejavu-fonts.github.io/) | Bitstream Vera / DejaVu | Default font with full Turkish coverage | All packages (assets/fonts, DejaVu-LICENSE.txt) |
| [Liberation Sans · Serif · Mono 2.1.5 (Red Hat, Google)](https://github.com/liberationfonts/liberation-fonts) | SIL OFL 1.1 | Metric-compatible with Arial, Times New Roman and Courier New | All packages (assets/fonts, Liberation-LICENSE.txt) |
| [pdf.js standard fonts (Foxit, Liberation)](https://github.com/mozilla/pdf.js) | BSD-3-Clause (PDFium) · SIL OFL 1.1 | The 14 PDF standard fonts in the browser | web_dist/pdfjs/standard_fonts (LICENSE_FOXIT, LICENSE_LIBERATION) |

### Data

| Component | Licence | Role | Where |
|---|---|---|---|
| [tessdata_fast (tur, eng, osd) 4.1.0](https://github.com/tesseract-ocr/tessdata_fast) | Apache-2.0 | OCR language models | Windows package (ocr/tessdata, SHA-256 pinned) |
| [pdf.js CMaps · ICC profiles · wasm decoders (OpenJPEG, JBIG2, QCMS)](https://github.com/mozilla/pdf.js) | Apache-2.0 · BSD-3-Clause (Adobe CMaps) · BSD-2-Clause (OpenJPEG) · MIT (QCMS) | Asian fonts, colour profiles, JPEG 2000 / JBIG2 images in the browser | web_dist/pdfjs (with their licence files) |

### Development, build and test tools

Used to build and test the app; not part of the packages.

| Component | Licence | Role | Where |
|---|---|---|---|
| [Node.js](https://nodejs.org/) | MIT | UI build | Build |
| [Vite · Rolldown](https://github.com/vitejs/vite) | MIT | UI bundling | Build |
| [TypeScript](https://github.com/microsoft/TypeScript) | Apache-2.0 | Type checking | Build |
| [@sveltejs/vite-plugin-svelte · svelte-check · @tsconfig/svelte](https://github.com/sveltejs) | MIT | Svelte build and checks | Build |
| [Playwright](https://github.com/microsoft/playwright) | Apache-2.0 | End-to-end tests | Tests |
| [axe-core (Deque)](https://github.com/dequelabs/axe-core) | MPL-2.0 | Accessibility (WCAG) audit | Tests |
| [pytest · httpx · ruff · mypy](https://pytest.org/) | MIT · BSD-3-Clause · MIT · MIT | Server tests, linting and type checking | Tests |
| [pip · setuptools · wheel](https://pip.pypa.io/) | MIT | Python packaging | Build |
| [7-Zip](https://www.7-zip.org/) | LGPL-2.1 | Unpacking the Tesseract / Ghostscript installers at build time | Build (Windows) |
| [Docker Buildx](https://github.com/docker/buildx) | Apache-2.0 | Docker image | Build |

### Methods and algorithms

Published methods we implemented in our own code.

| Method | Where | Source |
|---|---|---|
| True aspect ratio of a photographed sheet (focal-length estimate) | Images to PDF, perspective correction | Z. Zhang, L. He, Whiteboard scanning and image enhancement, Digital Signal Processing 17(2), 2007 |
| Skew detection by projection-profile variance | Deskew | W. Postl, Detection of linear oblique structures and skew scan in digitized documents, ICPR 1986 |
| Canny edge detection | Document detection (OpenCV) | J. Canny, A Computational Approach to Edge Detection, IEEE TPAMI 8(6), 1986 |
| Ramer–Douglas–Peucker polygon simplification | Document corners (OpenCV) | D. Douglas, T. Peucker, The Canadian Cartographer 10(2), 1973 |
| Otsu thresholding | Ink separation in skew analysis | N. Otsu, A Threshold Selection Method from Gray-Level Histograms, IEEE SMC 9(1), 1979 |
| Shadow removal by background division, adaptive thresholding | Scan enhancement | OpenCV documentation (Apache-2.0) |
| Turkish ID number check digits | Personal-data scan | T.C. İçişleri Bakanlığı Nüfus ve Vatandaşlık İşleri (public algorithm) |
| IBAN mod-97 check | Personal-data scan | ISO 13616 / ISO 7064 |
| Luhn card number check | Personal-data scan | H. P. Luhn, US patent 2,950,048 (1960); ISO/IEC 7812 |
| Turkish tax number check digit | Personal-data scan | Gelir İdaresi Başkanlığı (public algorithm) |
| Text difference (SequenceMatcher) | Document comparison | Python difflib (PSF-2.0) |
| Ed25519 signatures, SHA-256 | Update and package verification | RFC 8032; FIPS 180-4 (via cryptography / hashlib) |

### Notes

- The standards we follow and how are listed in STANDARDS.md; standard texts belong to their publishers (ISO, ETSI, W3C) and are not redistributed.
- Adobe and Acrobat are trademarks of Adobe Inc., mentioned for comparison only; this project is not affiliated with Adobe. Apple, macOS, iPhone and iPad are trademarks of Apple Inc.; Windows is a trademark of Microsoft Corporation.
- LGPL-3.0 Python packages (fpdf2, img2pdf) are used unmodified, as separate libraries.
