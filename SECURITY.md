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

- Multi-layered PDF safety gate on every `/pdf/*` endpoint by default
  (structural scan in `pdf_safety.py` for `/JavaScript`, `/Launch`,
  `/EmbeddedFile`, …; optional ClamAV + Windows Defender)
- SSRF guard with redirect re-validation + 50 MB response cap on
  `/pdf/from-url`; `xhtml2pdf` link-callback restricts asset fetching to
  `ht-font://` + `data:` schemes (no `file://` LFI)
- Cross-origin CSRF protection on mutating admin / history endpoints
  (Origin / Referer match required)
- Path-traversal defense: three-layer `make_job_dir` validation
  (separator reject → pre-mkdir resolve → post-mkdir symlink check)
- Mobile-auth middleware with URL-fragment token bootstrap (`#key=`,
  never reaches the server, never logs); `X-Mobile-Key` header on
  subsequent requests; constant-time comparison
- Bounded background-worker concurrency (`HT_MAX_INFLIGHT_JOBS=4`,
  503 on saturation)
- Per-job upload size limit (`MAX_UPLOAD_MB`, default 200 MB; raise via
  `HT_MAX_UPLOAD_MB` for huge-PDF workflows)
- Token-scoped temp directories under `_work/`, periodic cleanup
  (TTL 30 min)
- Baseline browser headers: `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
  `Cross-Origin-Opener-Policy: same-origin`
- No outbound network access during conversion
- Self-signed HTTPS certificate (auto-rotates <30 d before expiry,
  1-year validity) generated at startup when `HTTPS=1`
- Independent multi-engine scanner verification per release
  (VirusTotal, Hybrid Analysis, MetaDefender, Kaspersky)
- 2026-05 audit report: [`SECURITY_AUDIT_2026_05_10.md`](SECURITY_AUDIT_2026_05_10.md)

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

- Tüm `/pdf/*` endpoint'lerinde varsayılan PDF güvenlik gate'i
  (`pdf_safety.py` yapısal scanner + opsiyonel ClamAV + Windows Defender)
- URL→PDF'te SSRF guard'ı her redirect'i ayrıca doğrular + 50 MB yanıt
  cap'i; `xhtml2pdf` link-callback yalnızca `ht-font://` ve `data:`
  şemalarını çözer (`file://` LFI engellendi)
- Mutating admin / history endpoint'lerinde cross-origin CSRF koruması
  (Origin / Referer eşleşmesi zorunlu)
- Path-traversal savunması: `make_job_dir` 3 katmanlı doğrulama
  (separator reddi → pre-mkdir resolve → post-mkdir symlink check)
- Mobil-auth middleware URL fragment ile token bootstrap (`#key=`,
  server'a hiç ulaşmaz, log'lara sızmaz); sonraki istekler
  `X-Mobile-Key` header'ı kullanır; sabit zamanlı karşılaştırma
- Bounded worker concurrency (`HT_MAX_INFLIGHT_JOBS=4`, saturasyonda 503)
- Job başına upload boyut limiti (`MAX_UPLOAD_MB`, varsayılan 200 MB;
  büyük PDF için `HT_MAX_UPLOAD_MB` ile arttırılır)
- `_work/` altında token-bazlı temp dizinleri, periyodik temizlik
  (TTL 30 dk)
- Baseline browser header'ları: `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
  `Cross-Origin-Opener-Policy: same-origin`
- Dönüştürme sırasında dışa ağ trafiği yok
- `HTTPS=1` ile self-signed sertifika (sürelimi <30 gün kalınca otomatik
  yenilenir, 1 yıl geçerli) başlangıçta üretilir
- Her release için bağımsız multi-engine tarayıcı doğrulaması
  (VirusTotal, Hybrid Analysis, MetaDefender, Kaspersky)
- 2026-05 audit raporu: [`SECURITY_AUDIT_2026_05_10.md`](SECURITY_AUDIT_2026_05_10.md)
