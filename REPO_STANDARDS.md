# AdminPDFToolkit · Repo Standards

> **Hedef konum:** `C:\Projeler\pdfconverter\REPO_STANDARDS.md` (lokal klasör adı `pdfconverter`, remote `adminpdftoolkit`)
> Reponun köğüne kopyalayıp commit'leyin. Sonraki düzenlemeler bu dosyaya bağlı kalmalı — değişiklik gerekirse burayı da güncelleyin.
>
> **Snapshot:** 2026-05-14 (D Brand README + about/topics align sonrası — `gpdr → gdpr` typo düzeltildi, homepage eklendi)

---

## 1. Locked GitHub metadata

| Alan | Değer |
|---|---|
| **Owner/Repo** | `AmrasElessar/adminpdftoolkit` |
| **Visibility** | public |
| **Default branch** | `main` |
| **License (SPDX)** | `AGPL-3.0` (network-use clause nedeniyle GPL değil AGPL — self-hosted web service olduğundan) |
| **Description** | `Open-source, offline PDF toolkit by Engin — convert (Excel/Word/JPG/OCR), edit (annotation/overlay/replace), 35+ tools, web UI + PWA + Windows service.` |
| **Homepage** | `https://github.com/AmrasElessar/adminpdftoolkit/releases` |
| **Topics (11)** | `gdpr, kvkk, ocr, offline, pdf, pdf-converter, pdf-editor, pdf-toolkit, pwa, self-hosted, stirling-pdf-alternative` |

Değişiklik yaparsanız bu tabloyu güncelleyin + remote'a yansıtın.

---

## 2. README iskeleti (D Brand template — kaynak: d-terminal)

### 2.1 Bölüm sırası (kanonik)

1. **Header** — center-aligned, başlık + tagline + TR/EN bilingual notice
2. **🎬 Demo** — screenshot grid (Stirling-PDF tarzı tool gallery uygun düşer)
3. **Badge row** — License (AGPL-3.0) → Status → Platform (Web + PWA + Windows service) → Tech → D Brand
4. **📌 Kısaca** (TR) + collapsible `🇬🇧 At a glance` (EN)
5. **🆕 Yenilikler / What's done so far** — 35+ tool, OCR, batch
6. **🎯 Vizyon / Vision** — "Offline, KVKK/GDPR-uyumlu, Stirling-PDF alternatifi"
7. **✨ Öne Çıkan Özellikler** — Convert (Excel/Word/JPG/OCR) · Edit (annotation/overlay/replace) · 35+ tools · Batch
8. **🛠️ Teknoloji / Tech Stack**
9. **🗺️ Yol Haritası / Roadmap**
10. **📥 Kurulum / Installation** — Docker compose + Windows service installer
11. **🚀 İlk Adımlar / Quick Start**
12. **🛡️ Güvenlik Tarama / Security Scan Results** (release varsa)
13. **🤝 Katkı / Contributing**
14. **🎨 D Brand Ailesi / D Brand Family**
15. **💖 Sponsorlar / Sponsors**
16. **❤️ Destekle / Support**
17. **📜 Lisans / License** — AGPL-3.0 açıklaması ("network use = source share" özel notu)

### 2.2 Header pattern

```markdown
<div align="center">

# AdminPDFToolkit

**Open-source, offline PDF toolkit — 35+ tools, KVKK/GDPR uyumlu**

*Excel/Word/JPG/OCR dönüşümü · annotation/overlay/replace · web UI + PWA + Windows servis*
*Excel/Word/JPG/OCR conversion · annotation/overlay/replace · web UI + PWA + Windows service*

🌐 **TR · EN** — ...

</div>
```

### 2.3 Badge row

```
[License: AGPL-3.0]   (mavi)
[Status: stable / beta]
[Platform: Web · PWA · Windows service]
[Python] [FastAPI/Flask — gerçek framework'e göre]
[KVKK] [GDPR]
[D Brand]
```

### 2.4 Bilingual yapı

- Ana akış TR + `<details><summary>🇬🇧 ...</summary>` ile EN
- Tool listesi (35+) — kategorilere bölünmüş tablo veya bullet grupları

---

## 3. Tech stack & status

- **Status:** README badge ile senkron (en güncel sürüm rozeti)
- **Language:** Python
- **Framework:** Flask veya FastAPI (kod tarafına bakarak doğrula, README'de gözüken adı kullan)
- **Frontend:** Web UI + PWA (manifest + service worker)
- **Distribution:** Self-hosted (Docker / Windows service installer)
- **OCR:** Tesseract veya muadili (README'de belirtilen)
- **Offline first:** İnternet bağlantısı zorunlu değil (KVKK/GDPR claim'inin altı bu)

---

## 4. Lisans

- **AGPL-3.0-or-later** (SPDX: `AGPL-3.0`). README badge'i ve `LICENSE` dosyası tutarlı.
- **Neden AGPL (GPL değil):** Self-hosted web service olduğu için ağ üzerinden kullanımda kaynak paylaşım zorunluluğunu korur. GPL'ye downgrade etmek **major** karar — Stirling-PDF alternatifi pozisyonunu etkiler.

---

## 5. Commit mesaj stili

Conventional commits:

- `feat(readme): ...`, `fix(readme): ...`, `docs(readme): ...`
- `chore: ...` — config / dependency bump / FUNDING
- `feat(<area>): ...` — kod (convert, edit, ocr, router, pipeline, ...)
- `fix(<area>): ...` — bug
- `test(<area>): ...` — test eklemeleri (`tests/test_pipeline_workers.py` gibi)

Dil: TR veya EN.

---

## 6. Dosya hijyeni

- Adı `:` veya `\` içeren dosyalar **commit'lenmez**.
- **Zorunlu:** `README.md`, `LICENSE`, `.github/FUNDING.yml`
- **Önemli kod dosyaları:** `app.py`, `pdf_converter.py`, `pdf_safety.py`, `pipelines/`, `routers/`, `templates/index.html`, `tests/`
- **Tercih edilen:** `.gitignore` (Python: `__pycache__/`, `.pytest_cache/`, `.venv/`, `*.pyc`)
- Push öncesi `git status` kontrol — Python repo'larda `.idea/`, `.venv/`, `__pycache__/` sızması yaygın.

---

## 7. Repo-spesifik notlar

- **"Stirling-PDF alternatifi" pozisyonu** — README'de niche pozisyon, topic'lerde de mevcut. Marka dili korunmalı; "PDF tool" gibi geniş pozisyondan kaçınılır.
- **KVKK + GDPR claim'i** — offline + self-hosted olduğu için yapılır. Cloud bileşeni eklenirse bu claim **major** revizyon ister.
- **35+ tools listesi** — README'deki sayım kodla senkron tutulmalı. Tool eklenince README'deki sayı da güncellenir.
- **Lokal klasör adı `pdfconverter`** — remote `adminpdftoolkit`. Yeni clone'larda doğru klasör adıyla almak için: `git clone https://github.com/AmrasElessar/adminpdftoolkit.git`. Mevcut `pdfconverter/` klasörü tarihi sebeplerle korunuyor.
- **Description'da çift boşluk yasağı** — daha önce `"Windows   service"` olarak gelmişti, düzeltildi. Description güncellemelerinde tek boşluk kontrolü yap.
