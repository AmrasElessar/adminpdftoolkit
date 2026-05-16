<div align="center">

<img src="static/icon-192.svg" width="128" alt="Admin PDF Toolkit logo" />

# Admin PDF Toolkit

**LAN-first, çevrimdışı, kurumsal PDF işlem hattı**

*KVKK uyumlu, açık kaynak — dosyalar makineden çıkmaz*
*Compliance-first offline PDF pipeline — uploaded files never leave the machine*

🌐 **TR · EN** — Bu README iki dillidir / This README is bilingual (English collapsibles below each section)

</div>

## 🎬 Demo

<div align="center">

<!-- TODO: docs/media/adminpdftoolkit-showcase.mp4 eklendiğinde aşağıdaki satırı aç -->
<!-- https://github.com/AmrasElessar/adminpdftoolkit/raw/main/docs/media/adminpdftoolkit-showcase.mp4 -->

📸 *Ekran görüntüleri ve tanıtım videosu yakında / Screenshots & showcase video coming soon*

</div>

| | |
|---|---|
| 🖥️ **Masaüstü / Desktop** | Tarayıcıdan ana ekran — PDF sürükle-bırak, 35+ araç, canlı ilerleme / browser dashboard — drag-and-drop, 35+ tools, live progress |
| 📱 **Mobil / Mobile** | PWA olarak yüklenir; aynı LAN'da telefondan / Installable PWA; reachable from a phone on the same LAN |
| ✏️ **Editör / Editor** | pdf.js + smart-replace + serbest çizim / freehand + görsel imza / image signature |
| 📦 **Toplu / Batch** | N PDF → tek Excel → ekip dağıtımı / N PDFs → one Excel → team distribution |

<div align="center">

> 🔗 Canlı kurulum / Live deployment: kurum içi LAN — telefondan veya masaüstünden, harici servis bağımlılığı yok.
> *In-house LAN deployment — reachable from phones and desktops, zero third-party dependencies.*

</div>

<div align="center">

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v1.13.2-success)](https://github.com/AmrasElessar/adminpdftoolkit/releases)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PyMuPDF](https://img.shields.io/badge/PyMuPDF-EB5424)](https://pymupdf.readthedocs.io/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%C2%B7%20LAN%20%2F%20Docker-blue?logo=windows)](https://github.com/AmrasElessar/adminpdftoolkit/releases)
[![PWA](https://img.shields.io/badge/PWA-installable-5A0FC8?logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)
[![CI](https://github.com/AmrasElessar/adminpdftoolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/AmrasElessar/adminpdftoolkit/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AmrasElessar/adminpdftoolkit/actions/workflows/codeql.yml/badge.svg)](https://github.com/AmrasElessar/adminpdftoolkit/actions/workflows/codeql.yml)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**🛡 Güvenlik / Security**

[![SignPath](https://img.shields.io/badge/code_signing-SignPath_Foundation-success?logo=windows)](https://signpath.org/)
[![VirusTotal](https://img.shields.io/badge/VirusTotal-clean-success?logo=virustotal&logoColor=white)](https://www.virustotal.com/gui/file/40e7d5ff7210b1de389496274d915a82708ad2123ede82bed20a9a93804ea538)
[![Hybrid Analysis](https://img.shields.io/badge/Hybrid_Analysis-clean-success?logo=crowdstrike&logoColor=white)](https://hybrid-analysis.com/sample/40e7d5ff7210b1de389496274d915a82708ad2123ede82bed20a9a93804ea538)
[![MetaDefender](https://img.shields.io/badge/MetaDefender-clean-success?logo=opswat&logoColor=white)](https://metadefender.com/results/file/bzI2MDQzMER2M1FwRjl5NjJfVEU5enBMbjN4_mdaas)
[![Kaspersky](https://img.shields.io/badge/Kaspersky-clean-success?logoColor=white)](#bağımsız-güvenlik-doğrulaması--independent-security-verification)
[![ClamAV bundled](https://img.shields.io/badge/ClamAV-bundled-blueviolet)](#güvenlik--security)
[![KVKK](https://img.shields.io/badge/KVKK-uyumlu_%2F_compliant-success)](#-vizyon--vision)
[![D Brand](https://img.shields.io/badge/D_Brand-family-purple)](#-d-brand-ailesi--d-brand-family)

</div>

---

## 📌 Kısaca

**Admin PDF Toolkit**, KVKK'lı kurumsal ortamlar için tasarlanmış **LAN-first, çevrimdışı, açık kaynak bir PDF işlem hattıdır**. Yüklenen dosyalar makineyi terk etmez; sunucu kurumsal ağda telefondan ve masaüstünden erişilebilir; **hiçbir harici servis bağımlılığı yoktur**.

Tek bir Python 3.11 + FastAPI servisi içinde **35+ PDF aracı**, **OCR (TR + EN)**, **PDF editörü**, **toplu işlem & ekip dağıtımı** ve **çok katmanlı güvenlik tarayıcısı** bir araya gelir. Çıktı için tek pencere — telefondan da masaüstünden de aynı PWA.

**Kişisel proje** olarak başlamış, **AGPL-3.0** lisanslı bir **D Brand** repo'sudur. Yayınlanan binary'ler **SignPath Foundation** tarafından ücretsiz imzalanır ve her sürüm **bağımsız 66+ antivirüs motoru** taramasından geçer.

<details>
<summary>🇬🇧 At a glance (English)</summary>

**Admin PDF Toolkit** is a **LAN-first, offline, open-source PDF processing pipeline** built for KVKK-compliant in-house deployments. Uploaded files never leave the machine; the server is reachable from phones and desktops across the local network; **there are zero third-party service dependencies**.

A single Python 3.11 + FastAPI service bundles **35+ PDF tools**, **OCR (Turkish + English)**, a **PDF editor**, **batch processing & team distribution**, and a **multi-layered safety scanner**. One window for the operator — the same PWA on phone and desktop.

It started as a personal project and is shipped as an **AGPL-3.0** licensed **D Brand** repository. Released binaries are signed for free by the **SignPath Foundation** and every release is scanned by **66+ independent antivirus engines**.

</details>

---

## 🆕 Yenilikler — v1.13.x

> v1.13.x serisinde Admin PDF Toolkit, toplu Excel akışını yeniden tasarladı, PDF editör font kütüphanesini genişletti, güvenlik tarama hattını paralelleştirdi ve dağıtım için 3 ayrı kurulum varyantı çıkardı. Aşağıda öne çıkanlar.

- 📊 **Çok formatlı toplu birleştirme (multi-group merge)** — Bir batch'te birden fazla PDF formatı algılanırsa (ör. 6 çağrı kaydı + 4 farklı tablo), her format **kendi birleşik Excel'ine** ve **kendi sonuç sekmesine** otomatik dönüştürülür. Manuel "şu grubu birleştir" tuşu yok — analiz tamamlanır tamamlanmaz akış kendiliğinden tetiklenir. Çağrı kayıtlarında Telefon mükerreri otomatik; diğer tablolarda kullanıcı **hangi sütunların mükerrer sayılacağını** kendisi seçer.
- 🖥 **PDF Editör'de sistem fontları** — `static/fonts/` altındaki 6 bundled aile (Noto/DejaVu) artık Windows'taki TTF/OTF fontlarıyla birleşiyor; ~148 ek aile dropdown'da "🖥 Bu bilgisayar" optgroup'unda görünür. Microsoft fontları (Tahoma/Calibri/Times New Roman) EULA gereği bundle EDİLMEZ ama runtime'da kullanıcının makinesinden okunur. `fsType=Restricted Embedding` bayrağı taşıyan fontlar otomatik filtrelenir — gömülemeyecek fontlar listelenmez.
- 🛡️ **Paralel safety scan + "Yine de Dönüştür" akışı** — ClamAV / pdfid / Defender taramaları artık paralel; 16 dosyalık batch ~15 s yerine ~1-2 s. Tarama sırasında bir PDF tehlikeli işaretlenirse worker **durdurulur**, kullanıcıya **modal** sunulur (Yine de Dönüştür / İptal). Onaylanan tehlikeli dosyalar `_GUVENSIZ` suffix'i + Excel'de "⚠ UYARI" sayfası / Word'de kırmızı uyarı paragrafı ile damgalanır.
- 📦 **3 varyantlı kurulum dağıtımı** —
  - `AdminPDFToolkit_Setup.exe` (~33 MB) — online installer, gerekli bileşenleri kurulum sırasında indirir
  - `AdminPDFToolkit_Setup_Offline.exe` (~525 MB) — firewall'lu iş PC'leri için her şey içeride
  - `Admin_PDF_Toolkit_Portable_v1.13.x.zip` (~750 MB) — kurulum yok, ZIP açıp `.bat`'a tıkla
  Üç EXE de **D Brand** publisher metadata + v1.13.x version info ile imzalanır (Windows Explorer Properties → Details).
- ⚡ **ClamAV daemon blocking startup + chunked safety scan** — `clamd` lifespan'da garanti hale getirildi (25 sn timeout); ilk tarama artık half-warm daemon'a düşmez. Yapısal scanner artık 4 MB'lık chunked read kullanır (200 MB PDF için RSS delta ~0.8 MB; öncesi ~400 MB).
- 🧰 **JobStore deepcopy + single-worker enforcement** — `snapshot()` artık `copy.deepcopy(job)` döner, worker mid-update mutation yarışına karşı tam izolasyon. `WEB_CONCURRENCY > 1` ile başlatma reddedilir (kasıtlı single-process tasarımı; JobStore RAM'de).
- 🧪 **400 test, %63 branch coverage** — 5 yeni HTTP-level test eklendi (`/batch-deduplicate match_columns` validation + `other_table` worker shape). CI matrix Python 3.11/3.12/3.13 × Linux/Windows/macOS = 9 leg, hepsi yeşil.

<details>
<summary>🇬🇧 What's new — v1.13.x (English)</summary>

> The v1.13.x line redesigns the batch-Excel pipeline, expands the PDF editor font catalogue to the host OS, parallelises the safety-scan path, and ships three separate installer flavours. Headlines below.

- 📊 **Multi-format batch merge (multi-group)** — When a batch contains more than one PDF format (e.g. 6 call logs + 4 same-format tabular PDFs), each format becomes **its own merged Excel** + **its own result tab** automatically. No manual "merge this group" button — the flow runs the moment analyze completes. Call logs dedup on phone number out of the box; for other-table groups the user **picks which columns count as duplicates**.
- 🖥 **System fonts in the PDF editor** — The 6 bundled families (Noto/DejaVu) are now joined by the host machine's TTF/OTF fonts; ~148 extras appear in the dropdown under "🖥 This computer". Microsoft fonts (Tahoma/Calibri/Times New Roman) are NOT bundled (their EULA forbids redistribution) but ARE read from the user's machine at runtime. `fsType=Restricted` fonts are filtered out — anything that can't be legally embedded never shows up.
- 🛡️ **Parallel safety scan + "Convert Anyway" flow** — ClamAV / pdfid / Defender scans now run in parallel; a 16-file batch drops from ~15 s to ~1-2 s. When a scan flags a file, the worker **pauses** and presents a modal (Convert Anyway / Cancel). Accepted-unsafe files are stamped with a `_GUVENSIZ` filename suffix + an in-file warning (Excel "⚠ WARNING" sheet, Word red banner paragraph).
- 📦 **3 installer variants** —
  - `AdminPDFToolkit_Setup.exe` (~33 MB) — online installer, downloads components during install
  - `AdminPDFToolkit_Setup_Offline.exe` (~525 MB) — everything bundled for firewalled corporate PCs
  - `Admin_PDF_Toolkit_Portable_v1.13.x.zip` (~750 MB) — no install, unzip + click `.bat`
  All three EXEs carry **D Brand** publisher metadata + v1.13.x version info (visible in Windows Explorer Properties → Details).
- ⚡ **clamd blocking startup + chunked safety scan** — `clamd` is now guaranteed during lifespan (25 s timeout); the first scan never falls to a half-warm daemon. The structural scanner reads in 4 MB chunks now (200 MB PDF: ~0.8 MB RSS delta vs. previously ~400 MB).
- 🧰 **JobStore deepcopy + single-worker enforcement** — `snapshot()` returns `copy.deepcopy(job)`; workers can no longer race with readers on nested lists. Startup refuses `WEB_CONCURRENCY > 1` (single-process design is intentional — JobStore is in-process RAM).
- 🧪 **400 tests, ~63% branch coverage** — 5 new HTTP-level tests cover `/batch-deduplicate match_columns` validation + the `other_table` worker shape. CI matrix is Python 3.11/3.12/3.13 × Linux/Windows/macOS = 9 legs, all green.

</details>

---

## 🎯 Vizyon / Vision

Admin PDF Toolkit, **KVKK'lı ortamlarda çalışan kurumlar** için tasarlandı: devlet daireleri, eğitim kurumları, sağlık birimleri, hukuk büroları, kurumsal IT operasyonları. Bu ortamlarda PDF işleme **harici buluta gönderilemez** — ama operatörlerin günlük ihtiyaçları (birleştir, böl, şifrele, OCR, dönüştür, filigran...) yine de karşılanmalı.

Mevcut ticari PDF araçları genellikle ya çevrimiçi servistir (KVKK riski), ya per-seat lisansla pahalıdır, ya da telefon erişimi sunmaz. Admin PDF Toolkit bu boşluğu doldurur:

- **Dosyalar makineden çıkmaz.** OCR modeli ilk kullanımda yerele indirilir, sonra internet bile gerekmez.
- **Kurumsal LAN'da tek nokta.** Sunucu LAN'da çalışır; operatör telefonundan da masaüstünden de aynı PWA üzerinden erişir.
- **Açık kaynak, AGPL-3.0.** Kurum kendi kopyasını alır, değiştirir, denetler — kaynak görünür, değişiklik zorunluluğu AGPL ile korunur (network use = türetilmiş yazılım da AGPL).
- **Bağımsız güvenlik doğrulamalı.** SignPath imzalı binary, 66+ AV motoru, ClamAV bundled, çoklu tarayıcı raporları her release'de.

Hedef: tek bir kurulumda **35+ PDF aracı + OCR + editör + toplu işlem + ekip dağıtımı**. Kurum ağında bir kez deploy edilir, telefonlardan da erişilir.

<details>
<summary>🇬🇧 Vision (English)</summary>

Admin PDF Toolkit is designed for **organisations operating under KVKK / GDPR-style data residency rules**: government offices, schools, healthcare units, law firms, corporate IT teams. In these environments PDF processing **cannot be shipped to a third-party cloud** — yet operators still need the daily essentials (merge, split, encrypt, OCR, convert, watermark, …).

Existing commercial PDF tooling is either an online service (compliance risk), expensive per-seat, or offers no phone access. Admin PDF Toolkit fills that gap:

- **Files never leave the machine.** The OCR model is pulled to local cache on first use; after that no internet is required.
- **One spot on the corporate LAN.** The server runs in-house; operators reach the same PWA from phone and desktop.
- **Open source, AGPL-3.0.** Organisations take their own copy, modify it, audit it — source is visible, derivative obligations are protected by AGPL (network use = derivative also AGPL).
- **Independently verified security.** SignPath-signed binaries, 66+ AV engines, bundled ClamAV, multi-scanner reports on every release.

Goal: a single deployment that delivers **35+ PDF tools + OCR + editor + batch + team distribution**. Deploy once on the corporate LAN, reach it from phones too.

</details>

---

## ✨ Öne Çıkan Özellikler / Key Features

### 🔁 Dönüştürme / Conversion

- **PDF → Excel / Word / JPG** — call-log için özel parser, jenerik tablo için fallback parser
- **OCR (EasyOCR · TR + EN)** — modeller ilk kullanımda yerele indirilir, sonra **internet gerekmez**
- **Çok formatlı giriş** — image, docx, xlsx, html, url → PDF; PDF → Markdown, PDF → CSV

<details>
<summary>🇬🇧 Conversion (English)</summary>

- **PDF → Excel / Word / JPG** — specialised parser for call-log PDFs, generic table parser as fallback
- **OCR (EasyOCR · Turkish + English)** — models cached on first use; **no internet** required afterwards
- **Multi-format input** — image, docx, xlsx, html, url → PDF; PDF → Markdown, PDF → CSV

</details>

### 🧰 PDF Araçları / PDF Tools (35+ endpoint)

Birleştir, böl, sıkıştır, **AES-256 şifrele / kaldır**, metin / görsel filigran, sayfa numarası, header / footer, kırp, döndür, sırala, sil, image → PDF, docx / xlsx / html / url → PDF, PDF → Markdown, PDF → CSV, find, outline, metadata read / write, extract images, thumbnail, deep-analyze, extractability, blank detect / remove, signature detect, otomatik kategori (fatura / dekont / sözleşme / …), batch dispatcher.

<details>
<summary>🇬🇧 PDF tools (English)</summary>

Merge, split, compress, **AES-256 encrypt / decrypt**, text / image watermark, page numbers, header / footer, crop, rotate, reorder, delete pages, image → PDF, docx / xlsx / html / url → PDF, PDF → Markdown, PDF → CSV, find, outline, metadata read / write, extract images, thumbnail, deep-analyze, extractability, blank detect / remove, signature detect, automatic category (invoice / receipt / contract / …), batch dispatcher.

</details>

### ✏️ PDF Editör / PDF Editor

- **Görüntüleyici** — pdf.js, sayfa nav, zoom, font seçici (Noto / DejaVu gömülü **+ Windows sistem fontları otomatik algılanır**)
- **Annotation** — vurgu / altçizgi / üstçizgi / sticky / serbest çizim / görsel-imza
- **Overlay** — metin (Türkçe %100), dikdörtgen / elips / çizgi
- **Smart replace** — mevcut metni tıkla → düzenle → orijinal font + boyut + renk korunarak yaz
- **Per-page undo / clear-page** — her sayfa için ayrı operasyon yığını
- **EULA-uyumlu font seçimi** — Microsoft fontları (Tahoma/Calibri/Times New Roman) bundle EDİLMEZ ama makinende yüklüyse listede görünürler. `fsType=Restricted` bayrağı taşıyan fontlar otomatik filtrelenir.

<details>
<summary>🇬🇧 PDF editor (English)</summary>

- **Viewer** — pdf.js, page nav, zoom, font picker (Noto / DejaVu bundled **+ host OS fonts auto-discovered**)
- **Annotation** — highlight / underline / strike / sticky / freehand / image-as-signature
- **Overlay** — text (full Turkish support), rectangle / ellipse / line
- **Smart replace** — click existing text → edit → write back preserving the original font, size, and colour
- **Per-page undo / clear-page** — operation stack per page
- **EULA-compliant font picking** — Microsoft fonts (Tahoma/Calibri/Times New Roman) are NOT bundled but DO show up if installed on the host. `fsType=Restricted` fonts are auto-filtered.

</details>

### 📦 Toplu İşlem & Dağıtım / Batch & Distribution

- **N PDF → format başına birleşik Excel** — analiz otomatik gruplar (çağrı kayıtları + farklı tablolar ayrı sekmelere)
- **Otomatik mükerrer silme** — çağrı kaydı grubu Telefon üzerinden, diğer tablo grupları için kullanıcı sütun seçer (çoklu sütun composite key)
- **Sütun bazlı çoklu filtre** — AND mantığı, her grup için ayrı
- **3 kademeli ekip dağıtımı** — sıralı / round-robin / özel oran; her grup ayrı dağıtım yapabilir
- **Sekmeli sonuç paneli** — grup başına ayrı önizleme + dedup + filtre + dağıtım UI

<details>
<summary>🇬🇧 Batch & distribution (English)</summary>

- **N PDFs → one merged Excel per format** — analyze auto-groups by detected format (call logs + other tabular PDFs land in separate result tabs)
- **Automatic dedup** — call-log group dedups on phone number; for other-table groups the user picks one or more columns (composite key)
- **Multi-column filtering** — AND logic, per-group
- **3-tier team distribution** — sequential / round-robin / custom ratio; each group distributes independently
- **Tabbed result panel** — separate preview + dedup + filter + distribute UI per group

</details>

### 📱 Platform & UX

- **PWA** — telefonda Ana Ekrana Ekle / Add to Home Screen, responsive UI
- **Canlı ilerleme** — polling + SSE
- **İşlem geçmişi** — SQLite tabanlı, kalıcı
- **Runtime TR / EN UI** — dil değiştirme tek tık
- **Windows servisi** — `Servis Yoneticisi.bat` ile kur · başlat · durdur · durum · kaldır

<details>
<summary>🇬🇧 Platform & UX (English)</summary>

- **PWA** — Add to Home Screen on mobile, responsive UI
- **Live progress** — polling + SSE
- **Action history** — SQLite-backed, persistent
- **Runtime TR / EN UI** — language toggle in one click
- **Windows service** — `Servis Yoneticisi.bat`: install · start · stop · status · remove

</details>

---

## ❓ Neden Admin PDF Toolkit? / Why Admin PDF Toolkit?

| Senaryo / Scenario | Bulut çözümü / Cloud tool | Admin PDF Toolkit |
|---|---|---|
| KVKK / GDPR uyumu / compliance | ⚠️ Veri 3. tarafa gider / data leaves to 3rd party | ✅ Dosya makineden çıkmaz / never leaves the machine |
| Lisans modeli / License model | 💸 Aylık per-seat / monthly per-seat | ✅ AGPL-3.0 (free, mod, audit) |
| Telefon erişimi / Mobile access | ⚠️ Genelde sadece web / web-only typically | ✅ PWA, LAN üzerinden / over LAN |
| Çoklu motor AV taraması / Multi-engine AV scan | ❌ Genelde yok / typically none | ✅ ClamAV + Defender bundled |
| OCR (TR + EN) | 💸 Ek lisans / extra license | ✅ EasyOCR, offline model |
| Bağımsız doğrulama / Independent verification | ❌ Vendor-locked | ✅ VirusTotal + Hybrid Analysis + MetaDefender + Kaspersky her release / per release |
| İmzalı binary / Signed binary | ⚠️ Vendor sertifika / vendor cert | ✅ SignPath Foundation (free, transparent) |

---

## 🏢 Kullanım Senaryoları / Use Cases

Admin PDF Toolkit aşağıdaki kurumsal senaryolar için tasarlandı:

### 🏛️ Devlet / Government

- **Evrak dönüştürme** — taranmış PDF'ler → OCR'lı aranabilir PDF veya Word; veriler kurum dışına çıkmaz.
- **Toplu işlem** — N belge → tek Excel; özetler ve dağıtım tabloları.
- **AES-256 şifreleme** — gizli belgeler için yerinde şifreleme.

### 🎓 Eğitim / Education

- **Sınav kâğıdı OCR** — el yazısı + matbu metin tanıma (TR + EN).
- **Öğrenci listesi dağıtımı** — sınıflara round-robin / oran bazlı dağıtım.
- **Filigran** — telif notu / kurumsal logo otomatik eklenir.

### 🏥 Sağlık / Healthcare

- **Hasta dosyaları** — KVKK'lı ortamda offline işlenir, üçüncü tarafa gitmez.
- **Çoklu PDF birleştirme** — anamnez + tetkik + reçete tek dosyada.
- **Metadata strip** — paylaşım öncesi kişisel veriler temizlenir.

### ⚖️ Hukuk / Legal

- **Sözleşme şablon** — HTML → PDF (LFI-guard'lı), filigran + sayfa numarası.
- **Akıllı düzenleme / Smart replace** — orijinal font/boyut/renk korunarak düzeltme.
- **İmza tespiti** — `signature detect` endpoint'i ile dijital imza varlığı.

### 💼 Kurumsal IT / Enterprise IT

- **Tek deploy, LAN'a aç** — Docker compose veya Windows servisi; PWA telefonlara dağılır.
- **Aktif Dizin entegrasyonu** *(yol haritası / roadmap v1.14)*.
- **Audit log** — `core/history_db` ile her işlem SQLite'a kaydedilir.

<details>
<summary>🇬🇧 Use cases (English)</summary>

Admin PDF Toolkit is built for the corporate scenarios above: government document conversion (offline OCR), education exam-paper scanning + student-list distribution, healthcare patient-file workflows (KVKK-compliant), legal contract templating with smart-replace + signature detection, and enterprise IT one-shot LAN deployment with PWA reach to phones. AD/LDAP integration is on the roadmap for v1.14; every operation is already audited into the SQLite history DB.

</details>

---

## 🛠️ Teknoloji / Tech Stack

| | |
|---|---|
| **Python 3.11+** | Core runtime |
| **FastAPI** | Async web framework, OpenAPI auto-docs |
| **PyMuPDF (fitz)** | PDF core library — okuma / yazma / render |
| **EasyOCR** | TR + EN OCR engine (yerel model / local model) |
| **xhtml2pdf** | HTML → PDF (LFI-guarded link callback) |
| **pdf.js** | Tarayıcı içi PDF görüntüleyici / in-browser viewer |
| **SQLite** | Job & history persistence |
| **pydantic-settings** | `HT_*` env config (dev / prod profile) |
| **ClamAV (bundled)** | İmza tabanlı AV / signature-based AV |
| **Windows Defender** | `MpCmdRun.exe` opsiyonel ek katman / optional extra layer |
| **Docker** | Multi-stage prod image |
| **PWA / Service Worker** | Offline-capable web app |

### 📐 Mimari / Architecture

- **FastAPI bootstrap** — `app.py` (lifespan + middleware + `/`, `/health`)
- **Router'lar / Routers** — convert · batch · ocr · pdf_tools · editor · history · admin
- **Background workers** — `pipelines/` (convert, batch_convert, ocr)
- **Parser registry** — `parsers/` (call-log, scanned, generic)
- **Pure helpers** — `core/` (logging, errors, jobs, files, cleanup, history_db, network, security, distribution, ocr_preload, batch, pdf_tools, converters, analysis, editor, fonts, metadata)

---

## 🔌 Endpoint Kataloğu / Endpoint Catalogue

Hızlı referans — tam liste için Swagger UI (`/docs`):

### 🔁 Convert

| Method | Path | Açıklama / Description |
|---|---|---|
| `POST` | `/convert/pdf-to-excel` | call-log + jenerik parser fallback |
| `POST` | `/convert/pdf-to-word` | PDF → DOCX (font + layout korunur / preserved) |
| `POST` | `/convert/pdf-to-jpg` | PDF sayfa → JPG (per-page) |
| `POST` | `/convert/docx-to-pdf` | DOCX → PDF |
| `POST` | `/convert/xlsx-to-pdf` | XLSX → PDF |
| `POST` | `/convert/html-to-pdf` | HTML → PDF (xhtml2pdf, LFI-guarded) |
| `POST` | `/convert/url-to-pdf` | URL → PDF (SSRF-guarded, redirect re-validated) |
| `POST` | `/convert/image-to-pdf` | image → PDF |

### 🧰 PDF Tools

| Method | Path | Açıklama / Description |
|---|---|---|
| `POST` | `/pdf/merge` | N PDF → 1 PDF |
| `POST` | `/pdf/split` | sayfa aralığı / page range bazlı |
| `POST` | `/pdf/compress` | PyMuPDF compression |
| `POST` | `/pdf/encrypt` | AES-256 + password |
| `POST` | `/pdf/decrypt` | password ile şifre kaldır / remove with password |
| `POST` | `/pdf/watermark/text` | metin filigran / text watermark |
| `POST` | `/pdf/watermark/image` | görsel filigran / image watermark |
| `POST` | `/pdf/page-numbers` | sayfa numarası / page numbers |
| `POST` | `/pdf/header-footer` | üstbilgi / altbilgi |
| `POST` | `/pdf/crop` | sayfa kırp / crop |
| `POST` | `/pdf/rotate` | döndür / rotate |
| `POST` | `/pdf/reorder` | sayfa sırala / reorder |
| `POST` | `/pdf/delete-pages` | sayfa sil / delete |
| `POST` | `/pdf/extract-images` | gömülü görselleri çıkar / extract embedded images |
| `POST` | `/pdf/thumbnail` | thumbnail üret / generate |
| `POST` | `/pdf/find` | metin ara / text search |
| `POST` | `/pdf/outline` | TOC / outline çıkar / extract |
| `GET\|POST` | `/pdf/metadata` | metadata read / write |
| `POST` | `/pdf/deep-analyze` | derin analiz / deep analysis |
| `POST` | `/pdf/extractability` | metin çıkarılabilirliği / text extractability |
| `POST` | `/pdf/blank-detect` | boş sayfa tespit / detect |
| `POST` | `/pdf/blank-remove` | boş sayfa kaldır / remove |
| `POST` | `/pdf/signature-detect` | imza tespit / signature detect |
| `POST` | `/pdf/categorize` | otomatik kategori / auto-category |

### 🔢 OCR & Batch

| Method | Path | Açıklama / Description |
|---|---|---|
| `POST` | `/ocr/run` | EasyOCR (TR + EN) |
| `POST` | `/batch/convert` | toplu dönüştürme / bulk convert |
| `POST` | `/batch/dispatch` | ekip dağıtımı / team distribution |

### ✏️ Editor

| Method | Path | Açıklama / Description |
|---|---|---|
| `POST` | `/editor/annotate` | annotation submit |
| `POST` | `/editor/overlay` | overlay submit |
| `POST` | `/editor/smart-replace` | metin değiştir, font koru / replace text, preserve font |

### 🗄️ History & Admin

| Method | Path | Açıklama / Description |
|---|---|---|
| `GET` | `/history` | son işlemler / recent jobs |
| `DELETE` | `/history` | temizle (CSRF-guarded) / purge (CSRF-guarded) |
| `POST` | `/admin/enable-mobile` | mobil erişimi aç / enable mobile (CSRF-guarded) |
| `POST` | `/admin/disable-mobile` | mobil erişimi kapat / disable mobile (CSRF-guarded) |
| `POST` | `/admin/clamav-update` | ClamAV sig güncelle / update sigs (CSRF-guarded) |
| `GET` | `/health` | sağlık kontrol / health check |
| `GET` | `/` | ana sayfa / dashboard |

> Tam OpenAPI 3.x dokümantasyonu: `http://127.0.0.1:8000/docs` (Swagger) ve `/redoc`.
> *Full OpenAPI 3.x documentation: `http://127.0.0.1:8000/docs` (Swagger) and `/redoc`.*

---

## 🗺️ Yol Haritası / Roadmap

| Sürüm / Version | Hedef / Target | İçerik / Content |
|---|---|---|
| **v1.13.2** | ✅ yayında / shipped | Polish — CI coverage fix, dead code temizliği, `.gitattributes`, SSRF risk-accept docs, +5 yeni test |
| **v1.13.1** | ✅ yayında / shipped | Hot-fix (external review): Defender fail-open kapatma, `JobStore.snapshot` deepcopy, chunked safety scan, single-worker enforcement |
| **v1.13.0** | ✅ yayında / shipped | Multi-group batch merge, PDF Editor system fonts (EULA-aware), parallel safety + danger modal + unsafe stamping, 3-variant installer (D Brand publisher) |
| **v1.12.0** | ✅ yayında / shipped | Convert Workspace 3-step UI, ClamAV daemon (300× faster scan), smart Excel batch |
| **v1.11.0** | ✅ yayında / shipped | Safety scanner hardening, SSRF redirect guard, CSRF guard, mobile-auth middleware, SignPath signed |
| **v1.14** | +1-2 ay / months | OCR pipeline hız iyileştirme / OCR pipeline speed-up, parser registry genişletme / extension (banka dekontu, e-fatura) |
| **v1.13** | +2-3 ay / months | PDF editör smart-replace çoklu font / multi-font, anotasyon export-import, batch dispatcher UI |
| **v1.14** | +3-4 ay / months | Aktif Dizin / LDAP entegrasyonu (opsiyonel, LAN için), audit log endpoint'i, role-based admin |
| **v2.0** | — | Çoklu makine cluster (LAN üzerinde paralel render), webhook'larla intranet entegrasyonu, ek dil paketleri (AR / DE / FR) |

> Detaylı plan ve günlük gelişme: [`SECURITY_AUDIT_2026_05_10.md`](SECURITY_AUDIT_2026_05_10.md) · [GitHub Issues](https://github.com/AmrasElessar/adminpdftoolkit/issues) · [Releases](https://github.com/AmrasElessar/adminpdftoolkit/releases)

---

## ⚡ Performans Notları / Performance Notes

| Metrik / Metric | Tipik / Typical | Konfig / Configurable |
|---|---|---|
| **Cold start** | ~2 sn (FastAPI + middleware) | — |
| **PDF birleştir / merge** | 100 sayfa / ~1 sn (PyMuPDF) | — |
| **PDF → Excel (call-log)** | 50 sayfa / ~3 sn (özel parser / specialised parser) | — |
| **OCR (TR + EN)** | 1 sayfa / ~1-2 sn (EasyOCR, ilk çağrıda model yüklenir / model load on first call) | `HT_OCR_LANGS` |
| **AES-256 encrypt** | 100 sayfa / ~500 ms (PyMuPDF) | — |
| **Safety scan (yapısal / structural)** | <50 MB PDF / ~50 ms full-file | `HT_SAFETY_POLICY` |
| **Safety scan (ClamAV)** | <50 MB PDF / ~200 ms | `HT_CLAMAV_ENABLED` |
| **Bellek / Memory (idle)** | ~120 MB (FastAPI + worker pool) | — |
| **Bellek / Memory (peak OCR)** | ~600 MB (EasyOCR model load + render) | — |
| **Maks. eşzamanlı / Max concurrent** | 4 ağır iş + N hafif / 4 heavy + N light | `HT_MAX_INFLIGHT_JOBS` |

> Rakamlar **referans niteliğindedir**; donanım, PDF karmaşıklığı ve OCR dil sayısına göre değişir.
> *Numbers are **indicative only**; they depend on hardware, PDF complexity, and the number of OCR languages.*

<details>
<summary>🇬🇧 Performance notes (English)</summary>

The table above gives indicative typical timings on a modest workstation (Windows 11, Python 3.11). PyMuPDF dominates the fast paths (merge / split / encrypt); EasyOCR dominates the slow path (model load + render). The first OCR request after process start pays a one-time model-load cost (~1-2 GB pulled to the local cache on the very first run, then ~600 MB resident); subsequent OCR requests reuse the loaded model. The bounded-concurrency setting (`HT_MAX_INFLIGHT_JOBS=4`) is a deliberate guard against memory blow-up on multi-page OCR batches.

</details>

---

## 📥 Kurulum / Installation

### Geliştirme / Development

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python app.py                       # http://127.0.0.1:8000
```

### Docker

```bash
docker compose up -d
```

### Windows kurulumu — 3 varyant / Windows install — 3 variants

[GitHub Releases](https://github.com/AmrasElessar/adminpdftoolkit/releases/latest) sayfasından senaryona uyanı indir:

| Senaryo / Use case | Dosya / File | Boyut / Size |
|---|---|---|
| Sıradan ev/ofis PC'si — kurulum sihirbazı | `AdminPDFToolkit_Setup.exe` | ~33 MB |
| Firewall'lu kurumsal PC — internet yok | `AdminPDFToolkit_Setup_Offline.exe` | ~525 MB |
| Kurulum yapmadan dene — ZIP + .bat | `Admin_PDF_Toolkit_Portable_v1.13.x.zip` | ~750 MB |

- **Online installer** Inno Setup wizard'ı; gerekli bileşenleri (Python embedded + ClamAV + EasyOCR modelleri) kurulum sırasında ağdan indirir. Sıradan internet bağlantısı olan kullanıcılar için.
- **Offline installer** firewall'lu / pypi.org bloklu kurumsal makineler için. EXE'nin içinde her şey var — kurulum sırasında ağ gerekmez. USB / OneDrive üzerinden taşı, çift tıkla, bitsin.
- **Portable ZIP** kurulum yapmadan denemek isteyenler için. ZIP'i aç, `Admin PDF Toolkit Baslat.bat`'a (veya tray launcher `Admin PDF Toolkit.exe`'ye) tıkla; PC'de kalıcı bir değişiklik bırakmaz.

Üç EXE de **D Brand** publisher metadata ile imzalanır (Properties → Details: CompanyName = D Brand, ProductVersion = 1.13.x).

#### Geliştirici build pipeline'ı / Developer build pipeline

```cmd
python build_portable.py          REM dist/Admin_PDF_Toolkit_Portable/ üretir
python build_exe.py               REM PyInstaller ile launcher.exe ekler
python build_setup_inno.py        REM AdminPDFToolkit_Setup.exe (online)
python build_setup_offline.py     REM AdminPDFToolkit_Setup_Offline.exe (offline)
```

> 🇹🇷 Hedef makinede Python / internet **gerekmez** (offline veya portable variant'larda). ClamAV ve bundled fontlar paket içinde gelir.
> 🇬🇧 Target machine needs **no** Python / **no** internet (with the offline or portable variant). ClamAV and bundled fonts ship inside the bundle.

### 💻 Sistem Gereksinimleri / System Requirements

- Python 3.11+ (kaynak kurulumda / for source install)
- Windows 10 / 11 veya / or Linux (Docker)
- ~200 MB disk + OCR modelleri için ~100 MB (ilk indirme / first download)
- Modern tarayıcı (Chrome / Edge / Firefox) — PWA için

### ⚙️ Çevre Değişkenleri / Environment Variables

Tüm operasyonel ayarlar `HT_*` prefix'i ile `settings.py` (pydantic-settings) altında toplanır. Sık kullanılanlar:

| Değişken / Variable | Default | Açıklama / Description |
|---|---|---|
| `HT_SAFETY_POLICY` | `block_danger` | PDF safety politikası / policy: `off` · `warn` · `block_danger` |
| `HT_MAX_INFLIGHT_JOBS` | `4` | Eşzamanlı ağır iş limiti / heavy concurrent-job limit |
| `HT_MAX_UPLOAD_MB` | `200` | Maks. yükleme boyutu MB / max upload size MB |
| `HT_TRUSTED_PROXIES` | *(empty)* | Güvenilir proxy CIDR listesi / trusted proxy CIDR list (XFF gate) |
| `HT_LOOPBACK_BYPASS` | `true` | Loopback'ten gelen mobile-auth bypass / mobile-auth bypass from loopback |
| `HT_CLAMAV_ENABLED` | `auto` | ClamAV tarayıcısı / scanner toggle (`auto` · `true` · `false`) |
| `HT_DEFENDER_ENABLED` | `auto` | Windows Defender `MpCmdRun.exe` toggle |
| `HT_OCR_LANGS` | `tr,en` | EasyOCR dil paketleri / language packs |
| `HT_HOST` · `HT_PORT` | `127.0.0.1` · `8000` | Bind adresi / address |

> 💡 Tam liste için / Full list: [`settings.py`](./settings.py). Mobil erişim için `HT_HOST=0.0.0.0` + LAN firewall + token gerekir / required for mobile access.

<details>
<summary>🇬🇧 Environment variables (English)</summary>

All operational knobs live under the `HT_*` prefix in `settings.py` (pydantic-settings). Common ones are listed above. Setting `HT_HOST=0.0.0.0` plus the LAN firewall configuration and mobile token are required to expose the service to phones on the local network. See [`settings.py`](./settings.py) for the full list.

</details>

### 🔧 PDF Editör Asset'leri / PDF Editor Assets

`pdf.js` + fontlar git'te tutulmaz; ilk klon sonrası bir kez çalıştır:

```bash
python scripts/setup_editor_assets.py
```

Portable build (`Portable Paket.bat` veya `python build_portable.py`) bunu **otomatik** tetikler.

<details>
<summary>🇬🇧 PDF editor assets (English)</summary>

PDF editor assets (pdf.js + fonts) are not committed to git; run once after a fresh clone:

```bash
python scripts/setup_editor_assets.py
```

The portable build (`Portable Paket.bat` or `python build_portable.py`) runs this automatically.

</details>

---

## 🚀 İlk Adımlar / Quick Start

Kurulumdan sonra deneyebileceğin **5 hızlı şey**:

1. **`http://127.0.0.1:8000`** → tarayıcıdan ana sayfayı aç, **PWA olarak yükle** (telefonda "Ana Ekrana Ekle")
2. **Bir PDF sürükle-bırak** → otomatik kategori (fatura / dekont / sözleşme) tahmini gelir
3. **PDF → Excel** → call-log PDF'i sürükle, "Excel'e Dönüştür" → özel parser devreye girer
4. **PDF Editör** → bir PDF aç, **mevcut metni tıkla** → orijinal font + boyut + renk korunarak düzenle ("smart replace")
5. **Toplu işlem (Batch)** → N PDF yükle → tek birleşik Excel + ekip dağıtımı (sıralı / round-robin / özel oran)

> 💡 Servis olarak kurmak için (yönetici / Administrator): `Servis Yoneticisi.bat`
> 💡 Çevre değişkenleri (`HT_*`) tam listesi: `settings.py` içinde pydantic-settings tabanlı

<details>
<summary>🇬🇧 Quick Start (English)</summary>

After installing, **5 quick things** to try:

1. **`http://127.0.0.1:8000`** → open in browser, **install as PWA** ("Add to Home Screen" on mobile)
2. **Drag-and-drop a PDF** → automatic category guess (invoice / receipt / contract) appears
3. **PDF → Excel** → drop a call-log PDF, hit "Convert to Excel" → the specialised parser kicks in
4. **PDF Editor** → open a PDF, **click existing text** → edit preserving the original font, size and colour ("smart replace")
5. **Batch processing** → upload N PDFs → one merged Excel + team distribution (sequential / round-robin / custom ratio)

> 💡 Run as a Windows service (Administrator): `Servis Yoneticisi.bat`
> 💡 Full list of environment variables (`HT_*`): see `settings.py` (pydantic-settings based)

</details>

---

## 🛡️ Güvenlik / Security

Bu projenin **asıl tasarım önceliği** budur — KVKK'lı kurumsal ortamlara uygun:

- **Çevrimdışı çalışır.** Yüklenen dosya makineden çıkmaz; OCR modeli ilk kullanımda yerele indirilir, sonra internet bile gerekmez.
- **Çok katmanlı PDF güvenlik tarayıcısı.** Yapısal scanner (`/JavaScript`, `/OpenAction`, `/Launch` vb. işaretleri arar — büyük dosyalarda full-file taraması) + opsiyonel ClamAV + Windows Defender (`MpCmdRun.exe`). Politika `HT_SAFETY_POLICY=off|warn|block_danger` ile kontrol edilir, varsayılan **block_danger**. Tüm `/pdf/*` endpoint'leri varsayılan olarak güvenlik gate'inden geçer.
- **SSRF guard:** URL→PDF dönüşümünde private/loopback/link-local hedefler reddedilir; **her HTTP redirect ayrıca doğrulanır** (saldırgan domain → 127.0.0.1 redirect bypass'ı kapalı), yanıt gövdesi 50 MB ile sınırlı, URL içinde basic-auth kabul edilmez.
- **HTML→PDF LFI guard:** `xhtml2pdf` link callback yalnızca `ht-font://` ve `data:` şemalarını çözer; `file:///etc/passwd` / `http://internal/` gibi URI'ler reddedilir.
- **Cross-origin CSRF guard:** Mutating admin endpoint'lerinde (`/admin/enable-mobile`, `/admin/disable-mobile`, `/admin/clamav-update`, `DELETE /history`) Origin/Referer doğrulaması — operatörün tarayıcısındaki kötü niyetli sayfa loopback'e POST atamaz.
- **Path-traversal defense:** `make_job_dir` üç katmanlı (separator reddi → pre-mkdir resolve check → post-mkdir symlink check); user-controlled token'larla disk-fill DoS engellenir.
- **XFF guard:** `X-Forwarded-For` yalnızca güvenilir proxy'lerden (`HT_TRUSTED_PROXIES`) kabul edilir; default'ta header tamamen yok sayılır. Reverse-proxy senaryosu için `HT_LOOPBACK_BYPASS=false` ile loopback bypass'ı kapatılabilir.
- **Mobil-auth middleware:** Token URL fragment'ında (`#key=`) iletilir — server'a hiç ulaşmaz, log'lara/referer'a sızmaz; sonraki istekler `X-Mobile-Key` header'ı taşır. Sabit zamanlı (`hmac.compare_digest`) doğrulama.
- **Bounded concurrency:** Aynı anda en fazla `HT_MAX_INFLIGHT_JOBS` (default 4) ağır iş paralel çalışır; saturasyonda 503 döner. Default upload limiti 200 MB (`HT_MAX_UPLOAD_MB` ile arttırılabilir).
- **Browser hardening header'ları:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin` her cevapta.
- **Çıktı sanitization:** Hata mesajlarında mutlak path / kullanıcı dizini sızmaz.

> 2026-05 audit raporu: [`SECURITY_AUDIT_2026_05_10.md`](SECURITY_AUDIT_2026_05_10.md) — kapsamlı tarama + ayrıntılı bulgu listesi.

<details>
<summary>🇬🇧 Security (English)</summary>

This is the project's **primary design priority** — built for compliance-sensitive in-house deployments:

- **Runs offline.** Uploaded files never leave the machine; the OCR model is downloaded on first use, after that no internet is required.
- **Multi-layered PDF safety scanner.** Structural scanner (`/JavaScript`, `/OpenAction`, `/Launch` markers — full-file scan even on large PDFs) plus optional ClamAV and Windows Defender (`MpCmdRun.exe`). Policy via `HT_SAFETY_POLICY=off|warn|block_danger`, default **block_danger**. Every `/pdf/*` endpoint runs the safety gate by default.
- **SSRF guard:** URL→PDF refuses private/loopback/link-local targets; **every HTTP redirect is re-validated** (closes the attacker-domain → 127.0.0.1 redirect bypass), response body capped at 50 MB, basic-auth in URLs is rejected.
- **HTML→PDF LFI guard:** `xhtml2pdf` link callback resolves only `ht-font://` and `data:` schemes; `file:///etc/passwd` / `http://internal/` URIs are dropped.
- **Cross-origin CSRF guard:** Mutating admin endpoints (`/admin/enable-mobile`, `/admin/disable-mobile`, `/admin/clamav-update`, `DELETE /history`) require an Origin/Referer matching the server — a hostile page in the operator's own browser cannot drive them.
- **Path-traversal defense:** `make_job_dir` is three-layered (separator reject → pre-mkdir resolve → post-mkdir symlink check); user-supplied tokens cannot trigger disk-fill DoS via crafted directory names.
- **XFF guard:** `X-Forwarded-For` is honoured only from trusted proxies (`HT_TRUSTED_PROXIES`); empty by default → header always ignored. For reverse-proxy deployments, set `HT_LOOPBACK_BYPASS=false` to disable the loopback auth bypass.
- **Mobile-auth middleware:** Token is conveyed via URL fragment (`#key=`) — never reaches the server, never leaks via logs/referer; subsequent requests carry an `X-Mobile-Key` header. Comparison is constant-time (`hmac.compare_digest`).
- **Bounded concurrency:** At most `HT_MAX_INFLIGHT_JOBS` (default 4) heavy workers run in parallel; saturation returns 503. Upload cap defaults to 200 MB (raise via `HT_MAX_UPLOAD_MB`).
- **Baseline browser headers:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin` on every response.
- **Output sanitisation:** Error messages strip absolute paths and user directories before leaving the server.

> 2026-05 audit report: [`SECURITY_AUDIT_2026_05_10.md`](SECURITY_AUDIT_2026_05_10.md) — full scan + detailed findings.

</details>

### Güvenlik Katmanları Özeti / Security Layers at a Glance

| # | Katman / Layer | Ne yapar / What it does | Konfig / Config |
|---|---|---|---|
| 1 | **Yapısal scanner** | `/JavaScript`, `/OpenAction`, `/Launch` taraması (büyük dosyalarda da full-file) | `HT_SAFETY_POLICY` |
| 2 | **ClamAV** | Cisco-Talos imza tabanlı tarama / signature-based scan | `HT_CLAMAV_ENABLED` |
| 3 | **Windows Defender** | `MpCmdRun.exe` ile ek katman / extra layer via `MpCmdRun.exe` | `HT_DEFENDER_ENABLED` |
| 4 | **SSRF guard** | private/loopback/link-local + her redirect doğrulaması / per-redirect re-validation | `HT_*` (kapatma yok / no opt-out) |
| 5 | **LFI guard** | `xhtml2pdf` link callback yalnız `ht-font://` + `data:` | hardcoded |
| 6 | **CSRF guard** | Origin/Referer kontrolü mutating admin endpoint'lerinde | hardcoded |
| 7 | **Path-traversal guard** | 3 katmanlı `make_job_dir` / 3-layer | hardcoded |
| 8 | **XFF guard** | yalnız trusted proxy / trusted-proxy only | `HT_TRUSTED_PROXIES` |
| 9 | **Mobile-auth** | URL fragment token + sabit zamanlı `hmac.compare_digest` | `HT_LOOPBACK_BYPASS` |
| 10 | **Bounded concurrency** | `HT_MAX_INFLIGHT_JOBS` üzerinde 503 / 503 above limit | `HT_MAX_INFLIGHT_JOBS` |
| 11 | **Upload cap** | 200 MB default / default | `HT_MAX_UPLOAD_MB` |
| 12 | **Browser hardening** | nosniff + DENY + no-referrer + same-origin COOP | hardcoded |
| 13 | **Output sanitization** | path / kullanıcı dizini sızdırmaz / no absolute-path leakage | hardcoded |

<details>
<summary>🇬🇧 Security layers at a glance (English)</summary>

The 13-layer security model above is wired into the FastAPI middleware pipeline. Layers 1-3 (structural / ClamAV / Defender) compose the **safety gate** that every `/pdf/*` endpoint passes through; layers 4-9 protect specific attack classes (SSRF, LFI, CSRF, path-traversal, XFF spoofing, mobile-auth); layers 10-13 are baseline hardening (concurrency, upload size, browser headers, error output sanitisation). All policies are auditable in `core/security.py`, `pdf_safety.py`, and the relevant middleware.

</details>

### Bağımsız Güvenlik Doğrulaması / Independent Security Verification

Yayınlanan paketler bağımsız çoklu motor tarayıcılarda kontrol ediliyor. En son `main` taraması — **66+ antivirüs motoru + kurumsal Kaspersky, hiçbiri detection vermedi:**

[![VirusTotal](https://img.shields.io/badge/VirusTotal-clean-success?logo=virustotal&logoColor=white)](https://www.virustotal.com/gui/file/40e7d5ff7210b1de389496274d915a82708ad2123ede82bed20a9a93804ea538)
[![Hybrid Analysis](https://img.shields.io/badge/Hybrid_Analysis-clean-success?logo=crowdstrike&logoColor=white)](https://hybrid-analysis.com/sample/40e7d5ff7210b1de389496274d915a82708ad2123ede82bed20a9a93804ea538)
[![MetaDefender](https://img.shields.io/badge/MetaDefender-clean-success?logo=opswat&logoColor=white)](https://metadefender.com/results/file/bzI2MDQzMER2M1FwRjl5NjJfVEU5enBMbjN4_mdaas)
[![Kaspersky](https://img.shields.io/badge/Kaspersky-clean-success?logoColor=white)](#bağımsız-güvenlik-doğrulaması--independent-security-verification)
&nbsp; ClamAV · Microsoft · Kaspersky · Bitdefender · ESET · Sophos · Symantec · McAfee · Trellix · Avira · Emsisoft · Sangfor · CrowdStrike Falcon · Fortinet · GData · TrendMicro · WithSecure · ZoneAlarm + diğerleri / + others

Her **GitHub Release** sayfasında o sürüme ait SHA-256 + tarama bağlantıları listelenir ([Releases](https://github.com/AmrasElessar/adminpdftoolkit/releases)). Kendi indirdiğin ZIP'in hash'ini herhangi bir tarayıcıda sorgulayabilirsin (PowerShell: `Get-FileHash adminpdftoolkit-main.zip -Algorithm SHA256`).

> **Not / Note:** Bazı sandbox'lar paket içindeki ClamAV binary'lerini (Cisco-Talos imzalı) ve PowerShell `Unblock-File` çağrılarını sezgisel olarak işaretleyebilir; statik AV taramalarının **tamamı temizdir** / *Some sandboxes may heuristically flag the bundled ClamAV binaries (Cisco-Talos signed) and PowerShell `Unblock-File` calls; all static AV scans come back **clean***.

---

## ✍️ Code Signing

Yayınlanan binary'ler [**SignPath Foundation**](https://signpath.org/) tarafından **ücretsiz** olarak imzalanmaktadır (sertifika SignPath Foundation, imzalama hizmeti [SignPath.io](https://about.signpath.io/)). Politika ayrıntıları: [CODE_SIGNING.md](CODE_SIGNING.md).

<details>
<summary>🇬🇧 Code signing (English)</summary>

Released binaries are signed for **free** by the [**SignPath Foundation**](https://signpath.org/) (certificate by SignPath Foundation, signing service by [SignPath.io](https://about.signpath.io/)). Policy details: [CODE_SIGNING.md](CODE_SIGNING.md).

</details>

---

## 📚 Dokümantasyon / Documentation

| Belge / Doc | İçerik / Content |
|---|---|
| [`SECURITY.md`](./SECURITY.md) | Güvenlik açığı bildirimi / Vulnerability reporting |
| [`SECURITY_AUDIT_2026_05_10.md`](./SECURITY_AUDIT_2026_05_10.md) | 2026-05 kapsamlı denetim raporu / 2026-05 full audit |
| [`CODE_SIGNING.md`](./CODE_SIGNING.md) | SignPath imzalama politikası / signing policy |
| [`THIRD_PARTY_LICENSES.md`](./THIRD_PARTY_LICENSES.md) | Bağımlı kütüphane lisansları / 3rd-party licenses |
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) | Katkı rehberi / Contribution guide |
| [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) | Davranış kuralları / Code of Conduct |
| [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/) | Bug & feature şablonları / templates |
| [`settings.py`](./settings.py) | `HT_*` env değişkenleri (pydantic-settings) / env vars |

### 🌐 API Belgeleri / API Docs

FastAPI tabanlı her endpoint OpenAPI 3.x dokümanını otomatik üretir. Sunucu çalışırken:

- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`
- **OpenAPI JSON:** `http://127.0.0.1:8000/openapi.json`

> Üretim deploymant'larında bu route'lar `HT_DOCS_ENABLED=false` ile kapatılabilir.
> *In production deployments, these routes can be disabled via `HT_DOCS_ENABLED=false`.*

---

## 📂 Klasör Yapısı / Project Layout

```
app.py             # FastAPI bootstrap (lifespan + middleware + /, /health)
app_http.py        # Router'ların paylaştığı HTTP yardımcıları / HTTP helpers shared by routers
core/              # Pure helpers paketi / Pure-helper package
                   #   (logging, errors, jobs, files, cleanup, history_db,
                   #    network, security, distribution, ocr_preload, batch,
                   #    pdf_tools, converters, analysis, editor, fonts, metadata)
state.py           # Paylaşılan state + JobStore wrapper / Shared state + JobStore wrapper
settings.py        # pydantic-settings (HT_* env vars, dev/prod profile)
routers/           # FastAPI router'ları / routers
                   #   (convert, batch, ocr, pdf_tools, editor, history, admin)
pipelines/         # Arka plan worker'ları / Background workers
                   #   (convert, batch_convert, ocr)
parsers/           # PDF parser registry (call-log, scanned, generic)
pdf_converter.py   # Çekirdek dönüşüm fonksiyonları / Core conversion functions
pdf_safety.py      # Yapısal + ClamAV + Defender PDF güvenlik tarayıcısı
                   # / Structural + ClamAV + Defender PDF safety scanner
templates/         # index.html (vanilla TR/EN)
static/            # PWA manifest, ikonlar / icons, fonts, pdf.js, sw.js
tests/             # 400 test, ~%63 coverage / 400 tests, ~63% coverage
scripts/           # setup_editor_assets.py, check_packaging.py
build_portable.py  # Portable build script
Dockerfile         # Multi-stage prod image
```

---

## 🧪 Test

```bash
pip install -r requirements-dev.txt
pytest --cov=. --cov-fail-under=58
```

Test paketi: **400 test, %63 branch coverage** (Windows-local; Mac/Linux'ta `static/fonts/` boş olduğundan ~9 test skip, eşik 58'e indirilmiş margin için). Kapsam:

- **Birim / Unit:** parser registry, distribution algoritmaları, app_http helpers, JobStore, sanitize_error, token validation, persistent state recovery
- **Entegrasyon / Integration:** tüm endpoint kontratları, OCR/convert/batch worker'lar (EasyOCR stubbed), batch pipeline (load_job/save_view/load_distribution), sync convert (Excel/Word/JPG renderers), preview classifier, mobile-auth middleware, PDF safety gate
- **Güvenlik / Security:** SSRF, XFF spoof, symlink escape, danger PDF reject, error sanitization
- **Sürdürülebilirlik / Maintainability:** router registration drift, paketleme drift / packaging drift (`scripts/check_packaging.py`)

**CI gate'leri / CI gates:** ruff lint+format · mypy (strict-not-yet, ama errors fail) · pytest cov-fail-under=58 · packaging drift gate · Docker build · CodeQL.

---

## ❓ SSS / FAQ

**S: Bu yazılım gerçekten çevrimdışı mı çalışır? / Does it really run offline?**

E: Evet. İlk OCR kullanımında EasyOCR modeli yerele indirilir; sonrasında **hiçbir internet bağlantısı** gerekmez. URL → PDF özelliği opsiyoneldir ve `HT_*` env ile kapatılabilir.
*Yes. EasyOCR pulls its model to local cache on first OCR use; afterwards **no internet** is required. The URL → PDF feature is optional and can be disabled via `HT_*` envs.*

**S: Yüklediğim PDF'ler nereye gider? / Where do uploaded PDFs go?**

E: Sadece sunucunun job dizinine. Dış servise gönderilmez. `core/cleanup` periyodik temizlik yapar.
*Only into the server's job directory. They are never transmitted to a third party. `core/cleanup` runs periodic GC.*

**S: AGPL-3.0 bizi nasıl etkiler? / How does AGPL-3.0 affect us?**

E: Kurum içinde kullanmak serbest. Eğer **modifiye ettiyseniz ve ağ üzerinden hizmet sunuyorsanız** (intranet'te bile), kullanıcılara kaynak kodu erişimi sağlamak zorundasınız. Vendor-locked SaaS modeli AGPL ile uyumsuzdur.
*Internal use is free. If you **modify** the software **and serve it over a network** (even intranet), you must offer source access to the users. Vendor-locked SaaS is incompatible with AGPL.*

**S: ClamAV kullanmıyoruz, sorun olur mu? / We don't use ClamAV, is it a problem?**

E: Hayır. ClamAV opsiyoneldir (`HT_CLAMAV_ENABLED=false`). Yapısal scanner her zaman çalışır; Windows Defender de mevcutsa devreye girer. Üçü de bağımsız katmandır.
*No. ClamAV is optional (`HT_CLAMAV_ENABLED=false`). The structural scanner always runs; Windows Defender joins in if present. All three are independent layers.*

**S: Code signing neden SignPath Foundation? / Why SignPath Foundation for code signing?**

E: SignPath, OSS projeleri için **ücretsiz** sertifika sağlar. Bu projenin kurumsal hedef kitlesi için Windows SmartScreen'in "Bilinmeyen yayıncı" uyarısını ortadan kaldırır.
*SignPath provides **free** certificates for OSS projects. It eliminates the "Unknown publisher" SmartScreen warning, which matters for this project's enterprise audience.*

**S: Telefon erişimi nasıl güvende? / How is mobile access secured?**

E: Token URL **fragment** olarak iletilir (`#key=`) — server'a hiç ulaşmaz, log/referer'a sızmaz. Sonraki istekler `X-Mobile-Key` header'ı taşır; doğrulama `hmac.compare_digest` ile sabit zamanlıdır.
*The token rides in the URL **fragment** (`#key=`) — it never reaches the server, never leaks via logs/referer. Subsequent requests carry `X-Mobile-Key`; validation uses constant-time `hmac.compare_digest`.*

---

## 🪟 Windows Servisi / Windows Service

```cmd
Servis Yoneticisi.bat       REM Yönetici / Administrator: kur · başlat · durdur · durum · kaldır
                            REM                            install · start · stop · status · remove
```

---

## 🧑‍💻 Geliştirme Detayları / Development Deep-Dive

### Tipik geliştirme döngüsü / Typical dev loop

```bash
# 1. virtualenv + dev deps
python -m venv .venv
.venv\Scripts\activate              # Windows
pip install -r requirements-dev.txt

# 2. ilk klon assetleri / first-clone assets
python scripts/setup_editor_assets.py

# 3. çalıştır / run
python app.py                       # http://127.0.0.1:8000

# 4. test loop (watch mode için pytest-watch eklenebilir)
pytest -x --ff                      # fail-fast, run failed-first
pytest --cov=. --cov-fail-under=58  # CI gate

# 5. lint + format
ruff check . --fix
ruff format .
mypy .

# 6. paketleme doğrulama / packaging drift gate
python scripts/check_packaging.py
```

### Test paketinin kapsamı / Test suite scope

- **Birim / Unit** (`tests/test_unit_*.py`): parser registry, distribution algorithms, app_http helpers, JobStore, sanitize_error, token validation, persistent state recovery
- **Entegrasyon / Integration** (`tests/test_integration_*.py`): endpoint contracts, OCR/convert/batch workers (EasyOCR stubbed), batch pipeline (load_job/save_view/load_distribution), sync convert (Excel/Word/JPG renderers), preview classifier, mobile-auth middleware, PDF safety gate
- **Güvenlik / Security** (`tests/test_security_*.py`): SSRF, XFF spoof, symlink escape, danger-PDF reject, error sanitization
- **Drift gates** (`tests/test_*_drift.py`): router registration drift, packaging drift (`scripts/check_packaging.py`)

### CI hattı / CI pipeline

`.github/workflows/ci.yml` aşağıdaki adımları sırayla çalıştırır:

1. **Setup** — Python 3.11, pip cache, requirements-dev.txt
2. **Lint** — `ruff check .` + `ruff format --check .`
3. **Type** — `mypy .` (strict mode hedefte, şimdilik errors fail)
4. **Test** — `pytest --cov=. --cov-fail-under=58`
5. **Packaging** — `python scripts/check_packaging.py`
6. **Docker** — multi-stage build
7. **CodeQL** — ayrı workflow / separate workflow (`codeql.yml`)

<details>
<summary>🇬🇧 Development deep-dive (English)</summary>

The typical dev loop is: venv + dev deps → first-clone assets → run → pytest fail-fast → coverage gate → ruff lint + format → mypy → packaging drift gate. The test suite is split across unit / integration / security / drift gates as described in the bullet list above. CI runs lint → type → test (with `--cov-fail-under=58`) → packaging drift → Docker build → CodeQL on every push and PR.

</details>

---

## 🤝 Katkı / Contributing

PR'lar memnuniyetle — önce [CONTRIBUTING.md](CONTRIBUTING.md). Katılarak [Davranış Kuralları](CODE_OF_CONDUCT.md)'nı kabul etmiş olursunuz. Hata / özellik için [issue şablonları](.github/ISSUE_TEMPLATE/), güvenlik açığı için [SECURITY.md](SECURITY.md) (public issue **açmayın**).

| ✅ Kabul edilen / Accepted | 💡 Önce tartış / Discuss first |
|---|---|
| 🐛 Bug raporu / Bug reports | 🏗️ Mimari değişiklik / Architectural changes |
| 🧪 Test ekleme / Test additions | 🔌 Yeni endpoint kategorisi / New endpoint categories |
| 📝 Dokümantasyon / Documentation | ✨ Büyük özellik / Large features |
| 🌍 i18n (TR / EN dışı dil paketleri / language packs) | 🔐 Güvenlik değişikliği / Security-relevant changes (önce / first → [SECURITY.md](SECURITY.md)) |
| 🎨 UI / UX iyileştirme / improvements | |

<details>
<summary>🇬🇧 Contributing (English)</summary>

PRs welcome — please read [CONTRIBUTING.md](CONTRIBUTING.md) first. By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). For bugs / feature requests use the [issue templates](.github/ISSUE_TEMPLATE/); for security vulnerabilities see [SECURITY.md](SECURITY.md) (do **not** open a public issue).

The table above lists what is accepted vs. what is best discussed first.

</details>

---

## 🎨 D Brand Ailesi / D Brand Family

Admin PDF Toolkit, D Brand ailesinin **kurumsal Windows / LAN ayağıdır**. Aile üyeleri "Denizhan" adından ilham alır:

| Ürün / Product | Platform | Açıklama / Description |
|---|---|---|
| **Admin PDF Toolkit** | Windows / LAN / Docker | KVKK uyumlu offline PDF işlem hattı / KVKK-compliant offline PDF pipeline *(bu proje / this project, v1.13.x)* |
| **D-Terminal** | Windows | Agent-aware terminal, AI-yerli / AI-native *(pre-alpha)* |
| **D-Player** | Android | Kişisel müzik çalar, DSP motoru / personal music player with DSP engine *(in development)* |
| **DCar Launcher** | Android (Auto) | Head Unit araç içi OS katmanı / Head Unit in-car OS layer *(in development)* |
| **D-Watchtower** | — | Gözetim ve izleme platformu / surveillance & monitoring platform *(in development)* |
| **D-FTP Client** | Windows | FTP istemci uygulaması / FTP client app *(in development)* |

---

## 💖 Sponsorlar / Sponsors

Admin PDF Toolkit açık kaynak (**AGPL-3.0**) ve aktif geliştiriliyor. Sponsorluk doğrudan **yeni özellik ve güvenlik audit'lerine** dönüşür — yapılacaklar listesi `## 🗺️ Yol Haritası` bölümünde.

[![Sponsor on GitHub](https://img.shields.io/badge/Sponsor-AmrasElessar-db61a2?logo=githubsponsors)](https://github.com/sponsors/AmrasElessar)

<details>
<summary>🇬🇧 Sponsors (English)</summary>

Admin PDF Toolkit is open source (**AGPL-3.0**) and actively developed. Sponsorships translate directly into **new features and security audits** — backlog under the `## 🗺️ Roadmap` section.

</details>

<!-- SPONSORS:HERO -->
<!-- Hero tier ($25/ay · /mo) sponsorları buraya pinlenir / are pinned here -->
<!-- /SPONSORS:HERO -->

<!-- SPONSORS:LIST -->
<sub>Henüz sponsor yok / No sponsors yet. **İlk sponsor sen ol / Be the first →** [github.com/sponsors/AmrasElessar](https://github.com/sponsors/AmrasElessar)</sub>
<!-- /SPONSORS:LIST -->

---

## ❤️ Admin PDF Toolkit'i destekle / Support Admin PDF Toolkit

<table>
<tr>
<td align="center" width="33%">

### ⭐ Star at / Star it

GitHub'da **Star** projeyi başkalarına da görünür kılar.
Make the project visible to others.

[⭐ github.com/AmrasElessar/adminpdftoolkit](https://github.com/AmrasElessar/adminpdftoolkit)

</td>
<td align="center" width="33%">

### 💖 Sponsor ol / Sponsor

Aktif geliştirme; sponsorluk **yeni özellik ve güvenlik audit'i** demek.
Active development; sponsorship funds **new features and security audits**.

[💖 github.com/sponsors/AmrasElessar](https://github.com/sponsors/AmrasElessar)

</td>
<td align="center" width="33%">

### 🛡️ Güvenlik raporu / Security report

Açık bir güvenlik bulgusu varsa **public issue açmayın**.
If you find a vulnerability, **do not open a public issue**.

[🛡️ SECURITY.md](./SECURITY.md)

</td>
</tr>
</table>

---

## 📞 İletişim / Contact

| Kanal / Channel | Adres / Address |
|---|---|
| 🌐 GitHub | [github.com/AmrasElessar/adminpdftoolkit](https://github.com/AmrasElessar/adminpdftoolkit) |
| 🐛 Issues | [github.com/AmrasElessar/adminpdftoolkit/issues](https://github.com/AmrasElessar/adminpdftoolkit/issues) |
| 🔐 Güvenlik / Security | [SECURITY.md](./SECURITY.md) (public issue **açmayın / do not** open) |
| 💖 Sponsorlar / Sponsors | [github.com/sponsors/AmrasElessar](https://github.com/sponsors/AmrasElessar) |
| 📦 Releases | [github.com/AmrasElessar/adminpdftoolkit/releases](https://github.com/AmrasElessar/adminpdftoolkit/releases) |

---

## 🧭 Sürüm Geçmişi Özeti / Version History Summary

| Sürüm / Version | Tarih / Date | Öne çıkan / Highlights |
|---|---|---|
| **v1.13.2** | 2026-05-16 | Polish · CI coverage fix · dead code · `.gitattributes` · SSRF risk-accept docs · +5 test |
| v1.13.1 | 2026-05-16 | Hot-fix (external review): Defender fail-open · `JobStore.snapshot` deepcopy · chunked safety scan · workers=1 enforce |
| v1.13.0 | 2026-05-16 | Multi-group batch merge · system fonts (EULA-aware) · parallel safety + danger modal · 3-variant installer (D Brand) |
| v1.12.0 | 2026-04-30 | Convert Workspace 3-step UI · ClamAV daemon (300× faster scan) · smart Excel batch |
| v1.11.0 | 2026-05-10 | Safety scanner hardening · SSRF redirect guard · CSRF guard · mobile-auth · SignPath signed |
| v1.10.x | 2026-04 | Path-traversal 3-layer defense · XFF guard · bounded concurrency |
| v1.9.x | 2026-03 | PDF editor smart-replace · TR fonts embed · pdf.js viewer |
| v1.8.x | 2026-02 | Batch dispatcher + team distribution UI · history DB |
| v1.7.x | 2026-01 | PWA + mobile-auth + LAN-mode dashboard |
| v1.6.x | 2025-12 | OCR (TR + EN) integration · EasyOCR + offline model cache |
| v1.0 | 2025-09 | Initial AGPL-3.0 release — PDF tools + FastAPI service |

> Detaylı sürüm notları için / Detailed release notes: [Releases](https://github.com/AmrasElessar/adminpdftoolkit/releases).

<details>
<summary>🇬🇧 Version history (English)</summary>

A condensed view of the version timeline is in the table above; full release notes (per-version SHA-256, scanner links, breaking changes, migration notes) are on the [GitHub Releases](https://github.com/AmrasElessar/adminpdftoolkit/releases) page. The project moved from the initial AGPL-3.0 release in 2025-09 to the current v1.13.2 in 2026-05, with security hardening dominating the v1.10 / v1.11 line and product-feature breadth (batch multi-group, system fonts, 3-variant distribution) the v1.12 / v1.13 line.

</details>

---

## 🙏 Teşekkürler / Acknowledgements

Admin PDF Toolkit aşağıdaki açık kaynak projeler ve kuruluşların omzunda durur:

- **[PyMuPDF (fitz)](https://pymupdf.readthedocs.io/)** — PDF core (AGPL-3.0)
- **[FastAPI](https://fastapi.tiangolo.com/)** — async web framework (MIT)
- **[EasyOCR](https://github.com/JaidedAI/EasyOCR)** — TR + EN OCR (Apache-2.0)
- **[pdf.js](https://mozilla.github.io/pdf.js/)** — tarayıcı içi görüntüleyici / in-browser viewer (Apache-2.0)
- **[xhtml2pdf](https://github.com/xhtml2pdf/xhtml2pdf)** — HTML → PDF (Apache-2.0)
- **[ClamAV / Cisco Talos](https://www.clamav.net/)** — bundled AV
- **[SignPath Foundation](https://signpath.org/)** — ücretsiz code signing / free code signing for OSS
- **[VirusTotal](https://www.virustotal.com/), [Hybrid Analysis](https://hybrid-analysis.com/), [MetaDefender](https://metadefender.com/), [Kaspersky](https://www.kaspersky.com/)** — bağımsız doğrulama / independent verification
- **Noto + DejaVu fonts** — Türkçe gömülü font setleri / embedded Turkish font sets

Tam liste / Full list: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)

<details>
<summary>🇬🇧 Acknowledgements (English)</summary>

Admin PDF Toolkit stands on the shoulders of the open-source projects listed above: PyMuPDF for the PDF core, FastAPI for the async web layer, EasyOCR for Turkish + English OCR, pdf.js as the in-browser viewer, xhtml2pdf for HTML conversion, ClamAV / Cisco Talos for the bundled AV engine, the SignPath Foundation for free code signing, and the multi-engine scanners (VirusTotal, Hybrid Analysis, MetaDefender, Kaspersky) for independent verification. The Noto and DejaVu font families provide the embedded Turkish-capable typefaces. The full license inventory lives in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

</details>

---

## ⚠️ Sorumluluk Reddi / Disclaimer

Yazılım **"OLDUĞU GİBİ"** sunulur. Veri işleme / aktarma / kayıp riskleri tamamen kullanıcının sorumluluğundadır; önemli verilerden önceden yedek alınmalıdır.

<details>
<summary>🇬🇧 Disclaimer (English)</summary>

Software is provided **"AS IS"**. All data-processing, transmission and loss risks are the user's sole responsibility; back up important data before use.

</details>

---

## 📜 Lisans / License

**GNU AGPL-3.0** — kaynak açık, ücretsiz, değiştirilebilir. Türetilmiş yazılım da AGPL-3.0 altında paylaşılmak zorundadır; **ağ üzerinden hizmet sunulduğunda kaynak erişimi sağlanmalıdır**. Tam metin: [LICENSE](LICENSE) · Üçüncü taraf: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

> AGPL-3.0 · © 2026 Orhan Engin Okay

<details>
<summary>🇬🇧 License (English)</summary>

**GNU AGPL-3.0** — open source, free, modifiable. Derivative work must also ship under AGPL-3.0; **serving over a network requires offering the source**. Full text: [LICENSE](LICENSE) · Third-party: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

> AGPL-3.0 · © 2026 Orhan Engin Okay

</details>

---

<div align="center">

**Admin PDF Toolkit** — *by Orhan Engin Okay* · 2026 · part of the D Brand family

</div>
