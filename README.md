# Admin PDF Toolkit · _by Engin_

[🇬🇧 English](README.en.md) · [🇹🇷 Türkçe](README.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/orhanenginokay/pdfconverter/actions/workflows/ci.yml/badge.svg)](https://github.com/orhanenginokay/pdfconverter/actions/workflows/ci.yml)
[![CodeQL](https://github.com/orhanenginokay/pdfconverter/actions/workflows/codeql.yml/badge.svg)](https://github.com/orhanenginokay/pdfconverter/actions/workflows/codeql.yml)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**LAN-first, çevrimdışı, açık kaynak PDF işlem hattı.**
Şirket içi kullanım için: dosyalar makineyi terk etmez, kurumsal ağda telefondan/masaüstünden erişilir, harici servis bağımlılığı yoktur.

> AGPL-3.0 · © 2026 Orhan Engin Okay

---

## Hızlı başlangıç

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

## Güvenlik

Bu projenin asıl tasarım önceliği — KVKK'lı kurumsal ortamlara uygun:

- **Çevrimdışı çalışır.** Yüklenen dosya makineden çıkmaz; OCR modeli ilk kullanımda yerele indirilir, sonra internet bile gerekmez.
- **Çok katmanlı PDF güvenlik tarayıcısı.** Yapısal scanner (`/JavaScript`, `/OpenAction`, `/Launch` vb. işaretleri arar) + opsiyonel ClamAV + Windows Defender (`MpCmdRun.exe`). Politika `HT_SAFETY_POLICY=off|warn|block_danger` ile kontrol edilir, varsayılan **block_danger**.
- **SSRF guard:** URL→PDF dönüşümünde private/loopback/link-local hedefler reddedilir.
- **XFF guard:** `X-Forwarded-For` yalnızca güvenilir proxy'lerden (`HT_TRUSTED_PROXIES`) kabul edilir; default'ta header tamamen yok sayılır.
- **Symlink defense:** Tüm iş klasörleri tek bir `make_job_dir` kapısından açılır, work-dir'in dışına çıkmaya çalışan symlink'ler reddedilir.
- **Mobil-auth middleware:** Loopback dışındaki istemciler tek seferlik token ile geçer; token sabit zamanlı (`hmac.compare_digest`) doğrulanır.
- **Çıktı sanitization:** Hata mesajlarında mutlak path / kullanıcı dizini sızmaz.

Doğrulama: VirusTotal 0/72, MetaDefender 0/21, kurumsal Kaspersky temiz raporlu.

## Özellikler

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

## Klasör yapısı

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

## Test

```bash
pip install -r requirements-dev.txt
pytest --cov=. --cov-fail-under=62
```

Test paketi: 372 test, **%65+ branch coverage**. Kapsam:
- Birim: parser registry, distribution algoritmaları, app_http helpers, JobStore, sanitize_error, token validation, persistent state recovery
- Entegrasyon: tüm endpoint kontratları, OCR/convert/batch worker'lar (EasyOCR stubbed), batch pipeline (load_job/save_view/load_distribution), sync convert (Excel/Word/JPG renderers), preview classifier, mobile-auth middleware, PDF safety gate
- Güvenlik: SSRF, XFF spoof, symlink escape, danger PDF reject, error sanitization
- Sürdürülebilirlik: router registration drift, paketleme drift (`scripts/check_packaging.py`)

CI gate'leri: ruff lint+format · mypy (strict-not-yet, ama errors fail) · pytest cov-fail-under=62 · packaging drift gate · Docker build · CodeQL.

## Geliştirme kurulumu

PDF editör asset'leri (pdf.js + fontlar) git'te tutulmaz; ilk klon sonrası bir kez çalıştır:

```bash
python scripts/setup_editor_assets.py
```

Portable build (`Portable Paket.bat` veya `python build_portable.py`) bunu otomatik tetikler.

## Windows servisi

```cmd
Servis Yoneticisi.bat       REM Yönetici olarak: kur · başlat · durdur · durum · kaldır
```

## Lisans

**GNU AGPL-3.0** — kaynak açık, ücretsiz, değiştirilebilir. Türetilmiş yazılım da AGPL-3.0 altında paylaşılmak zorundadır; ağ üzerinden hizmet sunulduğunda kaynak erişimi sağlanmalıdır. Tam metin: [LICENSE](LICENSE) · Üçüncü taraf: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## Sorumluluk reddi

Yazılım **"OLDUĞU GİBİ"** sunulur. Veri işleme/aktarma/kayıp riskleri tamamen kullanıcının sorumluluğundadır; önemli verilerden önceden yedek alınmalıdır.

## Katkı

PR'lar memnuniyetle — önce [CONTRIBUTING.md](CONTRIBUTING.md). Katılarak [Davranış Kuralları](CODE_OF_CONDUCT.md)'nı kabul etmiş olursunuz. Hata/özellik için [issue şablonları](.github/ISSUE_TEMPLATE/), güvenlik açığı için [SECURITY.md](SECURITY.md) (public issue **açmayın**).

---

**by Orhan Engin Okay** · 2026
