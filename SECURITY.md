# Security Policy

[🇬🇧 English](#english) · [🇹🇷 Türkçe](#türkçe)

---

## English

### Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |
| < 1.0   | :x:                |

### Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Email: **orhanenginokay@gmail.com**
Subject line: `[SECURITY] Admin PDF Toolkit — <short title>`

Please include:

- A description of the vulnerability and its impact
- Steps to reproduce (PoC if possible)
- Affected version / commit SHA
- Your environment (OS, Python version)
- Any suggested mitigation

### Response timeline

- **Acknowledgement:** within 7 days
- **Initial assessment:** within 14 days
- **Patch / mitigation:** target 30 days for high severity
- **Public disclosure:** coordinated, after a fix is available

### Scope

In scope:
- Code in this repository (`app.py`, `pdf_converter.py`, `pdf_safety.py`, templates, build scripts)
- Default deployment configuration

Out of scope:
- Vulnerabilities in third-party dependencies (please report upstream; we will track and bump)
- Issues that require physical access to the server
- Social engineering

### Security features in place

- PDF structural scan (`pdf_safety.py`) for `/JavaScript`, `/Launch`, `/EmbeddedFile`, etc.
- Optional ClamAV integration if `clamscan` is on PATH
- Per-job upload size limit (`MAX_UPLOAD_MB`, default 2048 MB)
- Token-scoped temp directories under `_work/`, periodic cleanup (TTL 30 min)
- No outbound network access during conversion
- Self-signed HTTPS certificate generated at startup when `HTTPS=1`

---

## Türkçe

### Desteklenen sürümler

| Sürüm   | Destekleniyor      |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |
| < 1.0   | :x:                |

### Güvenlik açığı bildirme

**Lütfen güvenlik açıkları için public GitHub issue açmayın.**

E-posta: **orhanenginokay@gmail.com**
Konu satırı: `[SECURITY] Admin PDF Toolkit — <kısa başlık>`

Lütfen şunları ekle:

- Açığın tanımı ve etkisi
- Reprodüksiyon adımları (mümkünse PoC)
- Etkilenen sürüm / commit SHA
- Ortam bilgisi (OS, Python sürümü)
- Önerilen mitigation (varsa)

### Yanıt süresi

- **Onay:** 7 gün içinde
- **İlk değerlendirme:** 14 gün içinde
- **Patch / azaltma:** yüksek öncelikli için hedef 30 gün
- **Public açıklama:** patch çıktıktan sonra koordineli

### Kapsam

Kapsam içi:
- Bu repodaki kod (`app.py`, `pdf_converter.py`, `pdf_safety.py`, template'ler, build script'leri)
- Varsayılan deployment konfigürasyonu

Kapsam dışı:
- Üçüncü taraf bağımlılıklarındaki açıklar (upstream'e bildirin; biz takip edip yükseltiriz)
- Sunucuya fiziksel erişim gerektiren açıklar
- Social engineering

### Mevcut güvenlik önlemleri

- PDF yapısal taraması (`pdf_safety.py`) — `/JavaScript`, `/Launch`, `/EmbeddedFile` vs.
- Opsiyonel ClamAV entegrasyonu (`clamscan` PATH'te ise)
- Job başına upload boyut limiti (`MAX_UPLOAD_MB`, varsayılan 2048 MB)
- `_work/` altında token-bazlı temp dizinleri, periyodik temizlik (TTL 30 dk)
- Dönüştürme sırasında dışa ağ trafiği yok
- `HTTPS=1` ile başlangıçta self-signed sertifika üretilir
