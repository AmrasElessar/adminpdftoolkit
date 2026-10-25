# Admin PDF Toolkit v2

Çevrimdışı, LAN içi, ücretsiz ve açık kaynak PDF uygulaması. Dosyalar makineden çıkmaz.
Tasarım için [ARCHITECTURE.md](ARCHITECTURE.md).

## Neler yapabilir

| Grup | Araçlar |
|---|---|
| **Düzenle** | Mevcut metni değiştirme (orijinal font eşleştirme, sistem fontları), metin kutusu, görsel, el yazısı / yazılı / görsel imza, dikdörtgen, elips, çizgi, ok, serbest çizim, beyazla kapatma, bağlantı, vurgulama / altı çizili / üstü çizili, yapışkan not, form alanı; taşı, boyutlandır, geri al / yinele |
| **Görüntüle** | Küçük resimler, yakınlaştırma, Türkçe duyarlı arama, yazdırma, yer imi paneli (düzenlenebilir), şifreli PDF |
| **Sayfalar** | Sürükle-bırak düzenleme, döndür, sil, çoğalt, boş sayfa; birleştir (yer imli), böl, çıkar, sırala |
| **Dönüştür** | PDF ↔ Word, PDF → Excel, Word / Excel / PowerPoint → PDF, PDF ↔ JPG / PNG, PDF → metin, görsel çıkarma |
| **OCR** | Taranmış PDF'leri aranabilir yapma (Türkçe + İngilizce), eğim düzeltme, otomatik döndürme |
| **Formlar** | Alanları listele, doldur, düzleştir, yeni alan oluştur |
| **İmza** | PAdES dijital imza (görünür / görünmez), imza doğrulama, imza sertifikası oluşturma |
| **KVKK** | Kişisel veri bulma (TCKN, IBAN, telefon, e-posta, kart — sağlama doğrulamalı), kalıcı karartma, meta veri temizleme |
| **Karşılaştır** | İki sürüm arasında eklenen / silinen sözcükler, yan yana rapor |
| **Koruma & güvenlik** | AES-256 şifreleme ve izinler, şifre kaldırma, güvenlik taraması (JavaScript, gömülü dosya, ClamAV), güvenli temizleme |
| **Belge** | Meta veri, yer imleri (otomatik dahil), gömülü ekler, PDF/A, onarım, sıkıştırma, filigran, üst/alt bilgi, sayfa numarası, logo |
| **İş akışı** | Çağrı kaydı PDF'leri → birleşik Excel, mükerrer silme, filtreleme, ekiplere dağıtım |

## Çalıştırma

```bash
# sunucu (Python 3.11+)
cd v2/server
pip install -e ".[dev]"
python -m adminpdf --open           # http://127.0.0.1:8000
python -m adminpdf --lan            # ağda, tek kullanımlık eşleştirme bağlantısıyla

# arayüz (Node 20+) — bir kez derleyin, sunucu dosyaları kendisi sunar
cd v2/web
npm ci && npm run build             # server/adminpdf/web_dist içine
npm run dev                         # isteğe bağlı: :5173 üzerinde canlı geliştirme
```

Windows'ta `v2\scripts\start-windows.bat`, Linux/macOS'ta `v2/scripts/start.sh` ilk çalıştırmada
sanal ortamı kurar ve uygulamayı açar.

İsteğe bağlı sistem araçları: **Tesseract** (OCR, `tur` dil paketiyle), **Ghostscript** (PDF/A),
**LibreOffice** (Office → PDF yüksek doğruluk), **qpdf** (onarım), **ClamAV** (virüs taraması).
Yoksa ilgili araç açık bir hata mesajı verir; diğerleri çalışmaya devam eder.

### Docker

```bash
cd v2
docker compose up -d --build        # http://127.0.0.1:8000 — tüm araçlar dahil
```

## Ayarlar (`APT_*` ortam değişkenleri)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `APT_HOST` / `APT_PORT` | `127.0.0.1` / `8000` | Dinlenen adres |
| `APT_DATA_DIR` | `_data` | Yüklemeler ve iş klasörleri |
| `APT_MAX_UPLOAD_MB` | `200` | Dosya başına sınır |
| `APT_FILE_TTL_MINUTES` | `120` | Dosyalar bu süre sonunda silinir |
| `APT_MAX_WORKERS` | `2` | Eşzamanlı iş sayısı |
| `APT_JOB_TIMEOUT_SECONDS` | `600` | İş başına zaman sınırı |
| `APT_WORKER_MEMORY_MB` | `4096` | İş süreci bellek tavanı (POSIX) |
| `APT_LAN_ENABLED` / `APT_PAIRING_KEY` | kapalı | Ağdaki cihazlar eşleştirme anahtarıyla bağlanır |
| `APT_TRUSTED_NETWORKS` | — | Eşleştirme istemeyen ağlar (CIDR), ör. Docker köprüsü |
| `APT_ALLOWED_HOSTS` | — | Ek Host adları (ör. `pdf.kurum.local`) |

## Kontroller

```bash
cd v2/server && ruff check . && ruff format --check . && mypy adminpdf && pytest
cd v2/web && npm run check && npm run build
```
