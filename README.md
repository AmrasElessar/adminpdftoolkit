# Admin PDF Toolkit · _by Engin_

[🇹🇷 Türkçe](#türkçe) · [🇬🇧 English](#english)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/AmrasElessar/adminpdftoolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/AmrasElessar/adminpdftoolkit/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AmrasElessar/adminpdftoolkit/actions/workflows/codeql.yml/badge.svg)](https://github.com/AmrasElessar/adminpdftoolkit/actions/workflows/codeql.yml)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![VirusTotal](https://img.shields.io/badge/VirusTotal-clean-success?logo=virustotal&logoColor=white)](https://www.virustotal.com/gui/file/40e7d5ff7210b1de389496274d915a82708ad2123ede82bed20a9a93804ea538)
[![Hybrid Analysis](https://img.shields.io/badge/Hybrid_Analysis-clean-success?logo=crowdstrike&logoColor=white)](https://hybrid-analysis.com/sample/40e7d5ff7210b1de389496274d915a82708ad2123ede82bed20a9a93804ea538)

> AGPL-3.0 · © 2026 Orhan Engin Okay

---

## Türkçe

**LAN-first, çevrimdışı, açık kaynak PDF işlem hattı.**
Şirket içi kullanım için: dosyalar makineyi terk etmez, kurumsal ağda telefondan/masaüstünden erişilir, harici servis bağımlılığı yoktur.

### Hızlı başlangıç

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python app.py                       # http://127.0.0.1:8000
```

Docker ile:
```bash
docker compose up -d
```

Portable Windows kurulumu (kurulum/Python/internet gerektirmez):
```cmd
Portable Paket.bat        REM tek menüden: build · update · 7z · SFX-EXE
```

### Güvenlik

Bu projenin asıl tasarım önceliği — KVKK'lı kurumsal ortamlara uygun:

- **Çevrimdışı çalışır.** Yüklenen dosya makineden çıkmaz; OCR modeli ilk kullanımda yerele indirilir, sonra internet bile gerekmez.
- **Çok katmanlı PDF güvenlik tarayıcısı.** Yapısal scanner (`/JavaScript`, `/OpenAction`, `/Launch` vb. işaretleri arar) + opsiyonel ClamAV + Windows Defender (`MpCmdRun.exe`). Politika `HT_SAFETY_POLICY=off|warn|block_danger` ile kontrol edilir, varsayılan **block_danger**.
- **SSRF guard:** URL→PDF dönüşümünde private/loopback/link-local hedefler reddedilir.
- **XFF guard:** `X-Forwarded-For` yalnızca güvenilir proxy'lerden (`HT_TRUSTED_PROXIES`) kabul edilir; default'ta header tamamen yok sayılır.
- **Symlink defense:** Tüm iş klasörleri tek bir `make_job_dir` kapısından açılır, work-dir'in dışına çıkmaya çalışan symlink'ler reddedilir.
- **Mobil-auth middleware:** Loopback dışındaki istemciler tek seferlik token ile geçer; token sabit zamanlı (`hmac.compare_digest`) doğrulanır.
- **Çıktı sanitization:** Hata mesajlarında mutlak path / kullanıcı dizini sızmaz.

#### Bağımsız Güvenlik Doğrulaması

Yayınlanan paketler bağımsız çoklu motor tarayıcılarda kontrol ediliyor. En son `main` taraması — **66+ antivirüs motoru, hiçbiri detection vermedi:**

[![VirusTotal](https://img.shields.io/badge/VirusTotal-clean-success?logo=virustotal&logoColor=white)](https://www.virustotal.com/gui/file/40e7d5ff7210b1de389496274d915a82708ad2123ede82bed20a9a93804ea538)
[![Hybrid Analysis](https://img.shields.io/badge/Hybrid_Analysis-clean-success?logo=crowdstrike&logoColor=white)](https://hybrid-analysis.com/sample/40e7d5ff7210b1de389496274d915a82708ad2123ede82bed20a9a93804ea538)
&nbsp; ClamAV · Microsoft · Kaspersky · Bitdefender · ESET · Sophos · Symantec · McAfee · Trellix · Avira · Emsisoft · Sangfor · CrowdStrike Falcon · Fortinet · GData · TrendMicro · WithSecure · ZoneAlarm + diğerleri

Her **GitHub Release** sayfasında o sürüme ait SHA-256 + tarama bağlantıları listelenir
([Releases](https://github.com/AmrasElessar/adminpdftoolkit/releases)). Kendi indirdiğin ZIP'in hash'ini herhangi bir tarayıcıda
sorgulayabilirsin (PowerShell: `Get-FileHash adminpdftoolkit-main.zip -Algorithm SHA256`).

> **Not:** Bazı sandbox'lar paket içindeki ClamAV binary'lerini (Cisco-Talos imzalı) ve PowerShell `Unblock-File` çağrılarını sezgisel olarak işaretleyebilir; statik AV taramalarının **tamamı temizdir**.

### Özellikler

**Dönüştürme**
- PDF → Excel/Word/JPG (call-log için özel parser, jenerik tablo için fallback parser)
- OCR (EasyOCR · TR + EN), modeller ilk kullanımda yerele indirilir

**PDF araçları (33+ endpoint)**
Birleştir, böl, sıkıştır, AES-256 şifrele/kaldır, metin/görsel filigran, sayfa numarası, header/footer, kırp, döndür, sırala, sil, image→PDF, docx/xlsx/html/url→PDF, PDF→Markdown, PDF→CSV, find, outline, metadata read/write, extract images, thumbnail, deep-analyze, extractability, blank detect/remove, signature detect, otomatik kategori (fatura/dekont/sözleşme/…), batch dispatcher.

**PDF Editör**
- Görüntüleyici: pdf.js, sayfa nav, zoom, font seçici (Noto/DejaVu gömülü)
- Annotation: vurgu / altçizgi / üstçizgi / sticky / serbest çizim / görsel-imza
- Overlay: metin (Türkçe %100), dikdörtgen / elips / çizgi
- Smart replace: mevcut metni tıkla → düzenle → orijinal font + boyut + renk korunarak yaz
- Geri al / sayfayı temizle her sayfa için ayrı op yığını

**Toplu işlem & dağıtım**
- Birden fazla PDF → tek birleşik Excel
- Mükerrer telefon silme (ilk geçen kalır)
- Sütun bazlı çoklu filtre (AND mantığı)
- Ekip dağıtımı: sıralı / round-robin / özel oran

**Platform**
- PWA (telefonda Ana Ekrana Ekle), responsive UI
- Live progress (polling + SSE)
- SQLite tabanlı işlem geçmişi
- TR/EN UI (runtime dil değiştirme)

### Klasör yapısı

```
app.py             # FastAPI bootstrap (lifespan + middleware + /, /health)
app_http.py        # Router'ların paylaştığı HTTP yardımcıları
core/              # Pure helpers paketi (logging, errors, jobs, files, cleanup,
                   #   history_db, network, security, distribution, ocr_preload,
                   #   batch, pdf_tools, converters, analysis, editor, fonts, metadata)
state.py           # Paylaşılan state + JobStore wrapper
settings.py        # pydantic-settings (HT_* env vars, dev/prod profile)
routers/           # FastAPI router'ları (convert, batch, ocr, pdf_tools, editor, history, admin)
pipelines/         # Arka plan worker'ları (convert, batch_convert, ocr)
parsers/           # PDF parser registry (call-log, scanned, generic)
pdf_converter.py   # Çekirdek dönüşüm fonksiyonları
pdf_safety.py     # Yapısal + ClamAV + Defender PDF güvenlik tarayıcısı
templates/         # index.html (vanilla TR/EN)
static/            # PWA manifest, ikonlar, fonts, pdf.js, sw.js
tests/             # 379 test, ~%66 coverage
scripts/           # setup_editor_assets.py, check_packaging.py
build_portable.py  # Portable build script
Dockerfile         # Multi-stage prod image
```

### Test

```bash
pip install -r requirements-dev.txt
pytest --cov=. --cov-fail-under=62
```

Test paketi: 394 test, **%65+ branch coverage**. Kapsam:
- Birim: parser registry, distribution algoritmaları, app_http helpers, JobStore, sanitize_error, token validation, persistent state recovery
- Entegrasyon: tüm endpoint kontratları, OCR/convert/batch worker'lar (EasyOCR stubbed), batch pipeline (load_job/save_view/load_distribution), sync convert (Excel/Word/JPG renderers), preview classifier, mobile-auth middleware, PDF safety gate
- Güvenlik: SSRF, XFF spoof, symlink escape, danger PDF reject, error sanitization
- Sürdürülebilirlik: router registration drift, paketleme drift (`scripts/check_packaging.py`)

CI gate'leri: ruff lint+format · mypy (strict-not-yet, ama errors fail) · pytest cov-fail-under=62 · packaging drift gate · Docker build · CodeQL.

### Geliştirme kurulumu

PDF editör asset'leri (pdf.js + fontlar) git'te tutulmaz; ilk klon sonrası bir kez çalıştır:

```bash
python scripts/setup_editor_assets.py
```

Portable build (`Portable Paket.bat` veya `python build_portable.py`) bunu otomatik tetikler.

### Windows servisi

```cmd
Servis Yoneticisi.bat       REM Yönetici olarak: kur · başlat · durdur · durum · kaldır
```

### Lisans

**GNU AGPL-3.0** — kaynak açık, ücretsiz, değiştirilebilir. Türetilmiş yazılım da AGPL-3.0 altında paylaşılmak zorundadır; ağ üzerinden hizmet sunulduğunda kaynak erişimi sağlanmalıdır. Tam metin: [LICENSE](LICENSE) · Üçüncü taraf: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

### Code Signing

Yayınlanan binary'ler [SignPath Foundation](https://signpath.org/) tarafından
ücretsiz olarak imzalanmaktadır (sertifika SignPath Foundation, imzalama
hizmeti [SignPath.io](https://about.signpath.io/)). Politika ayrıntıları:
[CODE_SIGNING.md](CODE_SIGNING.md).

### Sorumluluk reddi

Yazılım **"OLDUĞU GİBİ"** sunulur. Veri işleme/aktarma/kayıp riskleri tamamen kullanıcının sorumluluğundadır; önemli verilerden önceden yedek alınmalıdır.

### Katkı

PR'lar memnuniyetle — önce [CONTRIBUTING.md](CONTRIBUTING.md). Katılarak [Davranış Kuralları](CODE_OF_CONDUCT.md)'nı kabul etmiş olursunuz. Hata/özellik için [issue şablonları](.github/ISSUE_TEMPLATE/), güvenlik açığı için [SECURITY.md](SECURITY.md) (public issue **açmayın**).

---

## English

**LAN-first, offline, open-source PDF processing pipeline.**
Designed for in-house corporate use: uploaded files never leave the
machine, the server is reachable from phones / desktops on the local
network, no third-party service dependencies.

### Quick start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python app.py                       # http://127.0.0.1:8000
```

Docker:
```bash
docker compose up -d
```

Portable Windows build (no install / Python / internet required on the
target machine):
```cmd
Portable Paket.bat        REM single menu: build · update · 7z · SFX-EXE
```

### Security

This is the project's primary design priority — built for compliance-
sensitive in-house deployments:

- **Runs offline.** Uploaded files never leave the machine; the OCR
  model is downloaded on first use, after that no internet is required.
- **Multi-layered PDF safety scanner.** Structural scanner (`/JavaScript`,
  `/OpenAction`, `/Launch` markers) plus optional ClamAV and Windows
  Defender (`MpCmdRun.exe`). Policy via `HT_SAFETY_POLICY=off|warn|block_danger`,
  default **block_danger**.
- **SSRF guard:** URL→PDF refuses private/loopback/link-local targets.
- **XFF guard:** `X-Forwarded-For` is honoured only from trusted proxies
  (`HT_TRUSTED_PROXIES`); empty by default → header always ignored.
- **Symlink defense:** Every job directory is opened through a single
  `make_job_dir` gate; symlinks escaping the work directory are refused.
- **Mobile-auth middleware:** Non-loopback clients pass with a
  one-shot token; comparison is constant-time (`hmac.compare_digest`).
- **Output sanitisation:** Error messages strip absolute paths and user
  directories before leaving the server.

#### Independent Security Verification

Released packages are checked against independent multi-engine scanners.
Latest `main` scan — **66+ antivirus engines, none flagged it**:

[![VirusTotal](https://img.shields.io/badge/VirusTotal-clean-success?logo=virustotal&logoColor=white)](https://www.virustotal.com/gui/file/40e7d5ff7210b1de389496274d915a82708ad2123ede82bed20a9a93804ea538)
[![Hybrid Analysis](https://img.shields.io/badge/Hybrid_Analysis-clean-success?logo=crowdstrike&logoColor=white)](https://hybrid-analysis.com/sample/40e7d5ff7210b1de389496274d915a82708ad2123ede82bed20a9a93804ea538)
&nbsp; ClamAV · Microsoft · Kaspersky · Bitdefender · ESET · Sophos · Symantec · McAfee · Trellix · Avira · Emsisoft · Sangfor · CrowdStrike Falcon · Fortinet · GData · TrendMicro · WithSecure · ZoneAlarm + others

Every **GitHub Release** page lists that release's SHA-256 + verification
links ([Releases](https://github.com/AmrasElessar/adminpdftoolkit/releases)). You can hash your downloaded ZIP and look it up
on any scanner yourself (PowerShell: `Get-FileHash adminpdftoolkit-main.zip -Algorithm SHA256`).

> **Note:** Some sandboxes may heuristically flag the bundled ClamAV
> binaries (Cisco-Talos signed) and PowerShell `Unblock-File` calls; all
> static AV scans come back **clean**.

### Features

**Conversion**
- PDF → Excel/Word/JPG (specialised parser for call-log PDFs, generic
  table parser as fallback)
- OCR (EasyOCR · Turkish + English), models pulled to local cache on
  first use

**PDF tools (33+ endpoints)**
Merge, split, compress, AES-256 encrypt/decrypt, text/image watermark,
page numbers, header/footer, crop, rotate, reorder, delete pages,
image→PDF, docx/xlsx/html/url→PDF, PDF→Markdown, PDF→CSV, find,
outline, metadata read/write, extract images, thumbnail, deep-analyze,
extractability, blank detect/remove, signature detect, automatic
category (invoice/receipt/contract/…), batch dispatcher.

**PDF Editor**
- Viewer: pdf.js, page nav, zoom, font picker (Noto/DejaVu bundled)
- Annotation: highlight / underline / strike / sticky / freehand /
  image-as-signature
- Overlay: text (full Turkish support), rect / ellipse / line
- Smart replace: click existing text → edit → write back preserving
  the original font, size and colour
- Per-page undo / clear-page operation stack

**Batch & distribution**
- N PDFs → one merged Excel
- Phone-number deduplication (first occurrence wins)
- Multi-column AND filtering
- Team distribution: sequential / round-robin / custom ratio

**Platform**
- PWA (Add to Home Screen on mobile), responsive UI
- Live progress (polling + SSE)
- SQLite-backed action history
- Runtime TR/EN UI switch

### Project layout

```
app.py             # FastAPI bootstrap (lifespan + middleware + /, /health)
app_http.py        # HTTP helpers shared by routers
core/              # Pure-helper package (logging, errors, jobs, files, cleanup,
                   #   history_db, network, security, distribution, ocr_preload,
                   #   batch, pdf_tools, converters, analysis, editor, fonts, metadata)
state.py           # Shared state + JobStore wrapper
settings.py        # pydantic-settings (HT_* env vars, dev/prod profile)
routers/           # FastAPI routers (convert, batch, ocr, pdf_tools, editor, history, admin)
pipelines/         # Background workers (convert, batch_convert, ocr)
parsers/           # PDF parser registry (call-log, scanned, generic)
pdf_converter.py   # Core conversion functions
pdf_safety.py     # Structural + ClamAV + Defender PDF safety scanner
templates/         # index.html (vanilla, i18n)
static/            # PWA manifest, icons, fonts, pdf.js, sw.js
tests/             # 394 tests, ~66% coverage
scripts/           # setup_editor_assets.py, check_packaging.py
build_portable.py  # Portable build script
Dockerfile         # Multi-stage production image
```

### Tests

```bash
pip install -r requirements-dev.txt
pytest --cov=. --cov-fail-under=62
```

Suite: 394 tests, **65%+ branch coverage**. Coverage:
- Unit: parser registry, distribution algorithms, app_http helpers,
  JobStore, sanitize_error, token validation, persistent state recovery
- Integration: every endpoint contract, OCR / convert / batch workers
  (EasyOCR stubbed), batch pipeline (load_job / save_view /
  load_distribution), sync convert (Excel/Word/JPG renderers), preview
  classifier, mobile-auth middleware, PDF safety gate
- Security: SSRF, XFF spoof, symlink escape, danger-PDF reject, error
  sanitisation
- Maintainability: router registration drift, packaging drift
  (`scripts/check_packaging.py`)

CI gates: ruff lint+format · mypy (strict-not-yet, but errors fail) ·
pytest cov-fail-under=62 · packaging drift gate · Docker build · CodeQL.

### Development setup

PDF editor assets (pdf.js + fonts) are not committed to git; run once
after a fresh clone:

```bash
python scripts/setup_editor_assets.py
```

The portable build (`Portable Paket.bat` or `python build_portable.py`)
runs this automatically.

### Run as a Windows service

```cmd
Servis Yoneticisi.bat       REM as Administrator: install · start · stop · status · remove
```

### License

**GNU AGPL-3.0** — open source, free, modifiable. Derivative work must
also ship under AGPL-3.0; serving over a network requires offering the
source. Full text: [LICENSE](LICENSE) · Third-party:
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

### Code Signing

Released binaries are signed for free by the
[SignPath Foundation](https://signpath.org/) (certificate by SignPath
Foundation, signing service by [SignPath.io](https://about.signpath.io/)).
Policy details: [CODE_SIGNING.md](CODE_SIGNING.md).

### Disclaimer

Software is provided **"AS IS"**. All data-processing, transmission and
loss risks are the user's sole responsibility; back up important data
before use.

### Contributing

PRs welcome — please read [CONTRIBUTING.md](CONTRIBUTING.md) first. By
participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
For bugs / feature requests use the [issue templates](.github/ISSUE_TEMPLATE/);
for security vulnerabilities see [SECURITY.md](SECURITY.md) (do **not**
open a public issue).

---

**by Orhan Engin Okay** · 2026
