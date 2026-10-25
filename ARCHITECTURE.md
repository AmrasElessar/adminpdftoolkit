# Admin PDF Toolkit — Mimari

Sürüm 2, v1'in yerine geçmek üzere sıfırdan tasarlandı. Hedef: çevrimdışı,
LAN-first, ücretsiz ve Acrobat seviyesinde bir PDF uygulaması. v1'in kaynak
kodu `archive/admin-pdf-toolkit-v1.13.2.zip` içinde ve git geçmişinde durur.

## Temel kararlar

| Konu | Karar |
|---|---|
| Çalışma modeli | LAN sunucusu + PWA (bir PC sunucu, ağdaki herkes tarayıcıdan) |
| Arka uç | Python 3.11+ · FastAPI · PyMuPDF · pikepdf |
| Ön yüz | Svelte 5 + TypeScript + Vite; derlenmiş statik dosyalar sunucuyla gelir |
| Kuruma özel akışlar | Çağrı kaydı → Excel, mükerrer, ekip dağıtımı: **eklenti** (çekirdek dışı) |
| Lisans kısıtı | Yalnızca ücretsiz / açık lisanslı kütüphaneler, bulut çağrısı yok |

## Katmanlar

```
.
├── server/adminpdf/
│   ├── config.py        Tek ayar kaynağı (APT_* ortam değişkenleri)
│   ├── app.py           create_app(): ara katmanlar + router'lar + statik ön yüz
│   ├── core/
│   │   ├── security.py  Host izin listesi, CSRF, boyut sınırı, güvenlik başlıkları, LAN erişimi
│   │   ├── files.py     Yükleme deposu (kimlik → dosya, TTL, boyut sınırı, tür tespiti)
│   │   └── pdf.py       PDF açma/kaydetme yardımcıları, sınırlar, Unicode font
│   ├── ops/             İşlem kayıt defteri — her araç tek sınıf
│   ├── jobs/            İş motoru — her iş ayrı süreçte, zaman aşımı + iptal + bellek sınırı
│   └── api/             /api/session, /api/files, /api/ops, /api/jobs
└── web/                 Svelte ön yüz
```

### İşlem kayıt defteri (`ops/`)

Her araç bir `Operation` alt sınıfıdır:

- `name`, `title`, `category`, `inputs` (kaç dosya, hangi tür)
- `Params`: Pydantic modeli — doğrulama **ve** arayüz formu buradan (JSON Schema) üretilir
- `run(ctx, params)`: girdileri okur, `ctx.output_dir` içine yazar, `ctx.progress()` ile ilerleme bildirir

Uç noktalar, arayüz formları ve toplu işlem tek tanımdan beslenir. Yeni araç =
tek dosya + test; router'a dokunmak gerekmez.

### İş motoru (`jobs/`)

- Her iş **ayrı bir süreçte** (spawn) çalışır: ana olay döngüsü hiçbir zaman PDF işiyle bloklanmaz.
- Eşzamanlılık semaforla sınırlı (`APT_MAX_WORKERS`).
- Zaman aşımı ve iptal süreci gerçekten sonlandırır (`terminate`); POSIX'te `RLIMIT_AS` ile bellek tavanı.
- İlerleme bir `Pipe` üzerinden gelir, istemciye SSE ile aktarılır.
- İş kayıtları bellekte + iş klasöründe; sonuç dosyası iş süresince korunur
  (temizlik iş kaydıyla birlikte yapılır — v1'deki TTL uyuşmazlığı yok).

### Güvenlik — tek yerde, ara katman olarak

v1'de kontroller her uca tek tek ekleniyordu ve bazı uçlarda eksik kaldı. v2'de:

1. **Host izin listesi** — DNS rebinding'e karşı (`localhost`, `127.0.0.1`, LAN IP'leri, `APT_ALLOWED_HOSTS`).
2. **CSRF** — durum değiştiren her istek `X-CSRF-Token` başlığı ister (çerezle eşleşmeli).
   Özel başlık çapraz-kaynak isteklerde preflight zorunlu kılar; CORS açık değildir.
   `Origin` varsa ayrıca birebir (port dahil) kontrol edilir.
3. **Boyut sınırı** — yüklemeler multipart değil ham gövde olarak akıtılır; sınır
   diske yazılırken uygulanır, aşıldığı anda kesilir.
4. **LAN erişimi** — loopback dışındaki istemciler eşleştirme anahtarıyla oturum çerezi alır.
5. **Güvenlik başlıkları** — sıkı CSP (satır içi script yok), `nosniff`, `frame-ancestors 'none'`.
6. **İşlem sınırları** — sayfa, piksel, DPI, biçim dizesi gibi girdiler `Params` modelinde sınırlıdır.

### API

| Yöntem | Yol | Açıklama |
|---|---|---|
| GET | `/api/session` | CSRF token + sürüm + oturum bilgisi |
| POST | `/api/session/pair` | LAN eşleştirme anahtarıyla oturum aç |
| PUT | `/api/files` | Dosya yükle (ham gövde, `X-Filename`) → `{id, name, size, kind, pages}` |
| GET / DELETE | `/api/files/{id}` | İndir / sil |
| GET | `/api/ops` | Araç kataloğu + her aracın JSON Schema'sı |
| POST | `/api/ops/{name}` | İş başlat `{inputs: [file_id...], params: {...}}` → `{job_id}` |
| GET | `/api/jobs/{id}` | İş durumu |
| GET | `/api/jobs/{id}/events` | SSE ilerleme akışı |
| POST | `/api/jobs/{id}/cancel` | İptal |
| GET | `/api/jobs/{id}/result` | Sonuç dosyası |

## Durum

| Aşama | Durum | İçerik |
|---|---|---|
| M1 — Temel | ✅ | Çekirdek, güvenlik ara katmanı, süreç izole iş motoru, sayfa araçları, sıkıştırma, şifreleme, damga |
| M2 — Görüntüleyici | ✅ | pdf.js görüntüleyici, küçük resimler, sürükle-bırak sayfa düzeni, Türkçe duyarlı arama, yazdırma, şifre sorma, yer imi paneli |
| M3 — Editör | ✅ | Belge modeli + geri al/yinele; metin değiştirme (font eşleştirme, sistem fontları), metin/şekil/görsel/imza/bağlantı, işaretleme, not, taşı/boyutlandır |
| M4 — Formlar & imza | ✅ | Form listele/doldur/düzleştir/oluştur (editörde alan aracı), pyHanko PAdES imza, doğrulama, kendinden imzalı sertifika |
| M5 — Dönüştürme & OCR | ✅ | OCRmyPDF/Tesseract (tr+en), PDF↔Word/Excel/Görsel, Office→PDF (LibreOffice / dahili), metin ve görsel çıkarma |
| M6 — Profesyonel | ✅ | KVKK karartma (TCKN/IBAN/telefon/e-posta/kart doğrulamalı), karşılaştırma raporu, PDF/A, meta veri, yer imleri, ekler, güvenlik taraması + temizleme, onarım |
| M7 — Eklentiler & dağıtım | ✅ / ⏳ | Çağrı kaydı eklentisi ✅, Docker + CI + PWA + başlatma betikleri ✅, v1 arşivlendi ✅; Windows kurulum paketi (installer) ⏳ |

### Bilinen sınırlamalar

- Zaman damgası (TSA) ve iptal (OCSP/CRL) kontrolü yok — uygulama çevrimdışı çalışacak şekilde tasarlandı.
- PDF/A çıktısı biçimsel olarak doğrulanmaz (veraPDF paketlenmedi); Ghostscript bazı fontlarda kopyalanan metni bozabilir, araç bunu raporlar.
- Dahili Office motoru basit belgeler içindir; PowerPoint ve yüksek doğruluk için LibreOffice gerekir.
- `scripts/fetch_fonts.py` font kilit dosyasının SHA-256 değerleri sürüm öncesi doldurulmalı.
