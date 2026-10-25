# Security Policy

[🇬🇧 English](#english) · [🇹🇷 Türkçe](#türkçe)

---

## English

### Supported versions

| Version | Supported |
| ------- | --------- |
| 2.x     | :white_check_mark: |
| 1.x     | :x: (archived in `archive/`) |

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
- Code in this repository (`server/`, `web/`, `scripts/`, Docker files)
- Default deployment configuration

Out of scope:
- Vulnerabilities in third-party dependencies (please report upstream; we track and bump them)
- Issues that require physical access to the server
- Social engineering

### Security features in place

- **One security middleware for every request** — Host allow-list (DNS-rebinding defence), CSRF
  double-submit token plus exact `Origin` match on state-changing calls, LAN pairing sessions for
  non-local clients (key in the URL fragment, never logged, rate-limited), strict CSP
  (`script-src 'self'`, `frame-ancestors 'none'`), `nosniff`, `no-referrer`, COOP.
- **Process isolation** — every job runs in its own spawned process with a timeout, real
  cancellation (process-group kill, including helper tools), and an address-space cap.
- **Bounded inputs** — streaming uploads with the size cap enforced while writing; page, pixel, DPI,
  regex, zip-bomb (OOXML ratio/size) and list-length limits in every tool's schema; no `str.format`
  on user templates.
- **Safe outputs** — Excel cells never become formulas; control characters stripped; generated file
  names sanitised (reserved names, traversal).
- **Real redaction** — KVKK/redact tools delete the covered text, image pixels and annotations, and
  strip metadata.
- **No outbound network** — no cloud APIs, no telemetry; OCR, conversion and signing run locally.
- **Supply chain** — Dependabot (pip, npm, actions, docker), CodeQL (Python + TypeScript), CI on
  Linux/Windows/macOS, WCAG audit.

---

## Türkçe

### Desteklenen sürümler

| Sürüm | Destekleniyor |
| ----- | ------------- |
| 2.x   | :white_check_mark: |
| 1.x   | :x: (`archive/` klasöründe) |

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
- Bu repodaki kod (`server/`, `web/`, `scripts/`, Docker dosyaları)
- Varsayılan kurulum yapılandırması

Kapsam dışı:
- Üçüncü taraf bağımlılıklarındaki açıklar (lütfen kaynağına bildirin; biz takip edip güncelleriz)
- Sunucuya fiziksel erişim gerektiren açıklar
- Sosyal mühendislik

### Mevcut güvenlik önlemleri

- **Her isteğe tek güvenlik ara katmanı** — Host izin listesi (DNS rebinding savunması), durum
  değiştiren çağrılarda CSRF token + birebir `Origin` kontrolü, yerel olmayan istemciler için LAN
  eşleştirme (anahtar URL parçasında, loglanmaz, deneme sınırlı), sıkı CSP.
- **Süreç izolasyonu** — her iş ayrı süreçte; zaman aşımı, gerçek iptal (yardımcı araçlar dahil
  süreç grubu sonlandırma) ve bellek sınırı.
- **Sınırlı girdiler** — yükleme boyutu yazılırken uygulanır; sayfa, piksel, DPI, düzenli ifade,
  zip bombası ve liste uzunluğu sınırları her aracın şemasında.
- **Güvenli çıktılar** — Excel hücreleri formüle dönüşmez; kontrol karakterleri temizlenir; dosya
  adları güvenli hale getirilir.
- **Gerçek karartma** — KVKK/karartma araçları metni, görsel piksellerini ve açıklamaları siler,
  meta veriyi temizler.
- **Dışa ağ trafiği yok** — bulut API'si ve telemetri yok.
- **Tedarik zinciri** — Dependabot, CodeQL, çoklu platform CI, WCAG denetimi.
