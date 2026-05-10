# Chrome Eklentisi — Yol Haritası

> **Durum:** Beklemede / Future Work
> **Oluşturma:** 2026-05-10
> **Versiyon hedefi:** v1.12+ (mevcut: v1.11.0)
> **Lisans:** AGPL-3.0-or-later (eklenti de aynı lisans altında)

## Amaç

Kullanıcı PDF Converter masaüstü uygulamasını kurduktan sonra, tarayıcıdan **tek tıkla** uygulamaya iş yollayabilsin. Eklenti app'in yerine geçmez — app kapalıysa eklenti hiçbir şey yapmaz, sadece "uygulamayı başlat" der. Eklenti, ince bir UI köprüsüdür.

**Önemli kısıtlar (proje DNA'sı):**
- Tüm veri kullanıcının makinesinde kalır — hiçbir uzak sunucuya gitmez
- Ücretsiz, AGPL uyumlu (paralı SDK / cloud API yok)
- Mevcut all-in-one mimariyi bozmaz

---

## 1. Tehdit Modeli

| # | Saldırı | Etki | Önem | Mevcut durumda var mı? |
|---|---------|------|------|------------------------|
| 1 | **DNS rebinding** — kötü site önce kendi IP'si gibi yanıtlar, sonra `127.0.0.1`'e rebind eder; tarayıcı same-origin sanır, kullanıcının PDF'lerini exfil eder | KRİTİK | Evet, eklenti olmadan bile delik |
| 2 | **Cross-origin CSRF** — herhangi bir site `fetch("http://localhost:8000/convert")` atar | YÜKSEK | Evet, mobile-auth middleware loopback'i unconditional kabul ediyor |
| 3 | **Yetkisiz extension** — başka bir eklenti localhost'a fetch atar | ORTA | Eklenti olunca yüzey artar |
| 4 | **Eklenti compromise** — Web Store hesabı çalınması veya XSS | YÜKSEK | MV3 + sıkı CSP zorunlu |
| 5 | **Path / command injection** — eklenti üstünden malicious payload | DÜŞÜK | Backend zaten temizliyor |

**Kritik tespit:** Tehdit #1 ve #2 zaten mevcut sistemde var — eklenti vesilesiyle bu açıklar da kapanır. Yani bu iş **eklentiden bağımsız güvenlik kazandırır.**

---

## 2. Mimari Kararlar

### HTTP fetch (Native Messaging Host değil)
- Native Messaging Windows'ta registry, macOS/Linux'ta manifest dosyası gerektirir → kurulum zor
- Tek avantajı app'i otomatik başlatması; "App kapalı, başlat" UI ile çözülebilir
- HTTP rotası mevcut backend'e oturuyor, ek bağımlılık yok

### Pairing token (rotating değil, persistent)
- App her başladığında token rotate ederse, eklentiyi her seferinde tekrar bağlamak gerekir → kullanılmaz
- **Persistent token:** ilk pairing'de oluşur, `_work/extension_token.json` (perms 0600) saklanır
- Kullanıcı "Eşleştirmeyi sıfırla" diyebilir

### Manifest V3
- Chrome Jan 2024'ten beri MV2 deprecate, MV3 zorunlu
- Service worker tabanlı, kısıtlı CSP, `eval` yasak

---

## 3. Faz Faz Plan

### Faz 0 — Backend güvenlik sertleştirme (eklenti ÖNCESİ)

> Bu adımlar eklenti olmadan da yapılmalı — eklenti onları gerektirir.

#### 0.1 — Host header doğrulama middleware'i (DNS rebinding'e karşı)
- Yeni middleware `app.py` içinde, mobile-auth'tan **önce** çalışsın
- Kabul edilen `Host` değerleri:
  - `127.0.0.1[:port]`, `localhost[:port]`
  - `mobile_token` aktifse `lan_ip()[:port]`
- Bunun dışında her şey `421 Misdirected Request` ile reddedilsin
- **Test:** `curl -H "Host: evil.com" http://127.0.0.1:8000/health` → 421

#### 0.2 — Origin/Referer kontrolü (cross-origin CSRF'e karşı)
- POST/PUT/DELETE isteklerinde `Origin` header whitelist kontrolü
- Whitelist:
  - `http://127.0.0.1:PORT`, `http://localhost:PORT`
  - `chrome-extension://<EXTENSION_ID>` (eşleştirilmiş ise)
  - `moz-extension://<UUID>` (Firefox eşleştirilmiş ise)
- GET isteklerinde state-changing değilse skip
- Mevcut web UI'si zaten same-origin, kırılmaz

#### 0.3 — Content Security Policy header'ları
- Templates'e `Content-Security-Policy: default-src 'self'; script-src 'self'; ...` eklenecek
- Mevcut UI'de inline script var mı? grep gerekir; varsa nonce'lu yapılmalı

#### 0.4 — Rate limiting (genel iyileştirme)
- `/convert`, `/batch` endpoint'lerine basit token-bucket (per-IP, ~10 req/min)
- Eklenti üzerinden flood'a karşı koruma

---

### Faz 1 — Pairing altyapısı (backend)

#### 1.1 — `core/extension_token.py` yeni modül
- `get_or_create_token()` → `_work/extension_token.json`'dan okur, yoksa `secrets.token_urlsafe(32)` üretir
- File perms 0600 (Windows: NTFS ACL — sadece mevcut kullanıcı)
- `revoke_token()` → dosyayı siler
- Token formatı: regex `^[A-Za-z0-9_-]{43}$` (urlsafe base64, 32 byte)

#### 1.2 — `routers/extension.py` yeni router
- `GET /admin/extension/pairing` — kullanıcı web UI'den girer; sayfa QR kod + manuel kod gösterir (60sn TTL)
- `POST /admin/extension/pair` — eklentiden gelir, body'de pairing kodu (one-time); doğruysa kalıcı token döner
- `POST /admin/extension/revoke` — eklenti token'larını iptal
- `GET /admin/extension/status` — eşleştirilmiş mi, son ne zaman kullandı

#### 1.3 — Mobile-auth middleware'inin sertleştirilmesi
- Şu an: `core.is_local_request(request)` → unconditional pass
- Yeni: loopback bile gelse, eklenti origin'i ise `X-Extension-Token` header zorunlu
- `hmac.compare_digest` constant-time karşılaştırma
- Tarayıcıdan `/`, `/static/` zaten public paths'tan geçiyor — UI etkilenmez

---

### Faz 2 — Minimum eklenti (MVP)

```
extension/
├── manifest.json         # MV3, minimum permissions
├── background.js         # service worker, fetch logic
├── popup.html            # toolbar tıklayınca açılan UI
├── popup.js              # popup logic
├── popup.css
├── content-script.js     # PDF link tespiti (opsiyonel)
├── icons/                # 16/32/48/128 px
└── README.md             # geliştirici yükleme talimatı
```

**`manifest.json` permissions — minimum prensibi:**
- `host_permissions`: SADECE `http://127.0.0.1/*` ve `http://localhost/*`. Public site YOK.
- `permissions`: `storage` (token), `contextMenus` (sağ tık), `downloads` (sonucu kaydet)
- `<all_urls>` İSTENMEYECEK — Web Store onayını zorlaştırır, gereksiz
- CSP: `script-src 'self'; object-src 'none'`

**Akış:**
1. Eklenti yüklenince popup → "App'e bağlan" butonu
2. Kullanıcı app web UI'de pairing kodunu görür, eklentiye yapıştırır
3. Eklenti `POST /admin/extension/pair` ile kalıcı token alır → `chrome.storage.local`
4. Sonraki tüm isteklerde `X-Extension-Token` header
5. App kapalıysa popup "App çalışmıyor — başlat" mesajı

**MVP özellikleri:**
- Toolbar popup → dosya seç → dönüştür (Excel/Word/JPG seçenekleri)
- Sağ tık (PDF link üstünde) → "PDF Converter ile aç"
- Sonuç indirme klasörüne otomatik

---

### Faz 3 — Gelişmiş özellikler
- OCR moduna toggle
- Batch (birden çok PDF aynı anda)
- "Bu sekmeyi PDF yap" — opsiyonel, tarayıcının yerleşik print fonksiyonu yeter
- Geçmiş paneli (`/history` endpoint'inden)

---

### Faz 4 — Dağıtım

**Chrome Web Store**
- $5 tek seferlik developer fee
- AGPL ile uyumlu — kaynak public
- Privacy practices: "Tüm veriler local, hiçbir veri toplanmaz" → büyük artı
- Review süreci: 1-7 gün
- Code signing yok — Store kendi imzalar

**Edge Add-ons:** Aynı paket çalışır, ek başvuru
**Firefox Add-ons (AMO):** `browser_specific_settings` farkı, aynı kod

---

## 4. Güvenlik Checklist'i

### Faz 0 (mevcut delikleri patch'le):
- [ ] Host header validation
- [ ] Origin/Referer enforcement on state-changing requests
- [ ] CSP headers
- [ ] Rate limiting

### Faz 1 (pairing):
- [ ] Token: 32 byte cryptographic random
- [ ] Storage: file perms 0600 (Windows NTFS ACL)
- [ ] Pairing kodu: 60sn TTL, tek kullanımlık
- [ ] `hmac.compare_digest` constant-time karşılaştırma
- [ ] Token'ı asla log'a yazma — `sanitize_error` kontrolü

### Faz 2 (eklenti):
- [ ] `host_permissions` sadece localhost
- [ ] CSP: `script-src 'self'; object-src 'none'`
- [ ] Token `chrome.storage.local`'da, **`chrome.storage.sync` DEĞİL** (sync = Google sunucularına gider)
- [ ] Hiçbir telemetry/analytics — privacy policy ile uyum
- [ ] MV3 (eval yok, remote code yok)
- [ ] `content-script` minimum DOM erişimi
- [ ] Subresource Integrity gerekmez (kendi paketimiz)

### Web Store başvurusu:
- [ ] Privacy practices: tüm veri local, hiç toplanmıyor
- [ ] Permission justification: her permission için 1 cümle açıklama
- [ ] Screenshots, açıklama AGPL referansıyla

---

## 5. Tahmini Süre

| Faz | İş | Süre |
|-----|------|------|
| 0 | Backend sertleştirme | 4-6 saat |
| 1 | Pairing endpoints + token store | 3-4 saat |
| 2 | MVP eklenti | 6-8 saat |
| 3 | Gelişmiş özellikler | 4-6 saat |
| 4 | Web Store başvurusu + assets | 2-3 saat (+ 1-7 gün bekleme) |

**Toplam aktif iş:** ~20-25 saat. Üç günlük disiplinli sprint veya bir hafta yarı zamanlı.

---

## 6. Önerilen Başlangıç Sırası

1. **İlk PR:** Faz 0.1 + 0.2 (host validation + origin enforcement). Eklenti olmadan da production değerinde güvenlik artışı.
2. **İkinci PR:** Faz 0.3 + 0.4 (CSP + rate limiting).
3. **Üçüncü PR:** Faz 1 (pairing endpoints + token store) + Faz 2 (MVP eklenti).
4. **Sonra:** Faz 3 (gelişmiş özellikler).
5. **En son:** Web Store başvurusu.

---

## 7. Açık Sorular / Karar Bekleyenler

- [ ] Eklenti adı — "PDF Converter Bridge"? "Admin PDF Toolkit Connector"?
- [ ] Eklenti ikon tasarımı — mevcut app ikonundan türetilmeli
- [ ] Firefox desteği MVP'de olsun mu yoksa Chrome/Edge sonrası mı?
- [ ] Eklenti versiyonlama — app version'a bağlı mı, ayrı mı?
- [ ] Pairing UI'si Türkçe + İngilizce mi yoksa sadece Türkçe mi? (App genel olarak Türkçe ağırlıklı)

---

## 8. İlgili Dosyalar (mevcut)

- `app.py:241-268` — mevcut mobile-auth middleware (genişletilecek)
- `core/security.py` — token validation primitives (örnek olarak referans)
- `state.py` — `mobile_token` global state (extension_token paralel olacak)
- `settings.py` — yeni env var'lar buraya: `extension_enabled`, vs.
- `routers/admin.py` — pairing endpoints'in komşusu olabilir
