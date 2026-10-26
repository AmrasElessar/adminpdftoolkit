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

- **HTTPS everywhere** — on by default with the server's own local CA, *name-constrained* to
  private addresses and local names (a leaked CA key cannot impersonate a real website); the server
  certificate follows LAN address changes; TLS 1.2+, ECDHE + AEAD only.
- **Local network only** — requests from public addresses are always refused, whatever the
  settings; trusted networks may only be local ranges; a loopback request carrying proxy forwarding
  headers counts as remote.
- **One security middleware for every request** — Host allow-list (DNS-rebinding defence), CSRF
  double-submit token plus exact `Origin` match on state-changing calls, LAN pairing sessions for
  non-local clients (key ≥ 12 characters, in the URL fragment, never logged, per-client and global
  rate limits; sessions expire after 30 days), strict CSP (`script-src 'self'`,
  `frame-ancestors 'none'`), `nosniff`, `no-referrer`, COOP/CORP, API responses `no-store`.
- **Per-device isolation** — every file and job belongs to this computer or to one paired device;
  other devices cannot see, download, use or cancel them.
- **Hostile documents** — LibreOffice runs with a throwaway hardened profile (no macros or active
  content, links never updated, no network: SSRF and local-file includes are tested); the optional
  *extra-secure PDF* rebuilds redacted output from page images only.
- **Verified bundled tools** — the Windows package's OCR and Ghostscript files are checked against
  SHA-256 hashes recorded at build time before every use; they are built from the newest upstream
  release, checked against the SHA-256 GitHub publishes for it.
- **Signed updates** — releases publish `SHA256SUMS` + an Ed25519 signature made in the release
  workflow; the app installs an update only if the signature verifies with the key built into
  `server/adminpdf/updater.py`, the zip matches its signed hash, it is newer than the running
  version and no entry escapes the folder. Unsigned releases are announced, never auto-installed.
- **Launcher** — plain .NET Framework code compiled from source in CI (no packer), with version
  info and an `asInvoker` manifest (never asks for administrator rights); Authenticode-signed
  when the maintainer provides a code-signing certificate.

#### Maintainer setup for signing

1. `python scripts/release_signing.py keygen` → put the private key into the repository secret
   `RELEASE_SIGNING_KEY` and the public key into `RELEASE_PUBLIC_KEY` in
   `server/adminpdf/updater.py`.
2. Optional, against SmartScreen / Defender warnings: a code-signing certificate (e.g. free for
   open source via SignPath Foundation, or Azure Trusted Signing / an OV/EV certificate) as
   secrets `WINDOWS_SIGN_PFX` (base64 `.pfx`) and `WINDOWS_SIGN_PASSWORD`.
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
- **Release scanning** — every published file (and the launcher exe on its own) is scanned on
  VirusTotal by the release workflow (`scripts/virustotal.py`, free API key as the secret
  `VIRUSTOTAL_API_KEY`); the results go into the release notes and the README badges
  (`virustotal.json`). Checksums are in `SHA256SUMS`, Ed25519-signed.

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

- **Her yerde HTTPS** — varsayılan olarak açık; sunucunun kendi yerel CA'sı yalnızca özel
  adresler ve yerel adlar için geçerli olacak şekilde *ad kısıtlıdır* (anahtarı sızsa bile gerçek
  bir siteyi taklit edemez). TLS 1.2+, yalnızca ECDHE + AEAD.
- **Yalnızca yerel ağ** — genel (internet) adreslerinden gelen istekler ayarlardan bağımsız olarak
  her zaman reddedilir; vekil sunucu başlığı taşıyan yerel istekler uzak sayılır.
- **Her isteğe tek güvenlik ara katmanı** — Host izin listesi (DNS rebinding savunması), durum
  değiştiren çağrılarda CSRF token + birebir `Origin` kontrolü, yerel olmayan istemciler için LAN
  eşleştirme (anahtar en az 12 karakter, URL parçasında, loglanmaz, istemci başına ve genel deneme
  sınırı; oturumlar 30 günde dolar), sıkı CSP, API yanıtları önbelleğe alınmaz.
- **Cihazlar arası yalıtım** — her dosya ve iş bu bilgisayara ya da tek bir eşleşmiş cihaza aittir;
  diğer cihazlar göremez, indiremez, kullanamaz.
- **Kötü niyetli belgeler** — LibreOffice makrosuz, aktif içeriksiz, bağlantı güncellemesiz ve
  ağsız bir profille çalışır; *ekstra güvenli PDF* karartılmış çıktıyı yalnızca sayfa
  görüntülerinden yeniden kurar.
- **Doğrulanan paket araçları** — Windows paketindeki OCR ve Ghostscript dosyaları her kullanımdan
  önce derleme sırasında kaydedilen SHA-256 özetleriyle karşılaştırılır.
- **İmzalı güncellemeler** — güncelleme yalnızca Ed25519 imzası, SHA-256 özeti doğrulanan ve
  mevcut sürümden yeni olan paketse kurulur; imzasız sürümler yalnızca bildirilir.
- **Başlatıcı** — kaynaktan derlenen sade .NET kodu (sıkıştırıcı yok), sürüm bilgili, yönetici
  izni istemez; kod imzalama sertifikası tanımlanınca Authenticode ile imzalanır.
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
- **Sürüm taraması** — yayımlanan her dosya (ve başlatıcı exe ayrıca) sürüm iş akışında
  VirusTotal'da taranır (`scripts/virustotal.py`, ücretsiz API anahtarı `VIRUSTOTAL_API_KEY`
  sırrı olarak); sonuçlar sürüm notlarına ve README rozetlerine (`virustotal.json`) yazılır.
  Sağlama toplamları `SHA256SUMS` dosyasında, Ed25519 ile imzalı.
