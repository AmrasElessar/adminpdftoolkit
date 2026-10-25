# Standartlara Uyum / Standards Compliance

Bu belge Admin PDF Toolkit'in hangi uluslararası standartları nasıl karşıladığını
ve bilinen sınırları listeler. *This document maps each relevant standard to the
implementation and states known limits.*

| Standart | Konu | Durum | Uygulama |
|---|---|---|---|
| **ISO 32000-1 / 32000-2** | PDF 1.7 / PDF 2.0 dosya biçimi | ✅ | Tüm çıktılar MuPDF (PyMuPDF) ile yazılır; nesne akışları, sıkıştırma ve çapraz başvuru tabloları standarda uygundur. Bozuk dosyalar `repair` (qpdf) ile yeniden kurulur. |
| **ISO 19005-1/2/3 (PDF/A)** | Uzun süreli arşivleme | ✅ | `pdfa` aracı PDF/A-1b, 2b, 3b üretir (OCRmyPDF + Ghostscript), XMP `pdfaid` kaydını doğrular. Biçimsel doğrulayıcı (veraPDF) paketlenmedi. |
| **ISO 14289-1 (PDF/UA-1)** | Erişilebilir PDF | 🟡 Denetim + kısmi düzeltme | `accessibility_check` maddeleri tek tek denetler (etiket, MarkInfo, /Lang, başlık, DisplayDocTitle, font gömme, gerçek metin, alternatif metin, sekme sırası, form açıklamaları, şifreleme izinleri). `accessibility_fix` otomatik düzeltilebilenleri düzeltir. Etiketsiz içeriği etiketlemek ve okuma sırası insan incelemesi gerektirir. |
| **ETSI EN 319 142 (PAdES) / ISO 32000-2 §12.8** | Dijital imza | ✅ (B-B) | `sign` pyHanko ile PAdES imza (görünür/görünmez) üretir; `verify_signatures` bütünlük, geçerlilik, güven zinciri, kapsama, sonradan değişiklik ve DocMDP raporlar. Zaman damgası (B-T) ve iptal kontrolü (B-LT) çevrimdışı tasarım nedeniyle yoktur. |
| **ISO/IEC 40500:2012 (WCAG 2.0) · WCAG 2.1 AA** | Web arayüzü erişilebilirliği | ✅ Otomatik denetimde ihlal yok | Tam klavye kullanımı ve kısayollar (`?`), görünür odak, "içeriğe atla" bağlantısı, ARIA rolleri/etiketleri, `aria-keyshortcuts`, canlı bölgeler, açık/koyu temada yeterli kontrast, `prefers-reduced-motion`. axe-core ile ana ekran, araç paneli, görüntüleyici, editör, KVKK modu ve kısayol penceresinde WCAG 2.1 A/AA ihlali sıfır (açık ve koyu tema). |
| **ISO 8601** | Tarih ve saat | ✅ | API ve JSON çıktılarındaki tarih/saatler ISO 8601 (`isoformat`). Damgalarda `{isodate}` (YYYY-AA-GG); `{date}` Türkçe görünüm (GG.AA.YYYY) içindir. |
| **BCP 47 / ISO 639** | Dil etiketleri | ✅ | Belge dili (`/Lang`) BCP 47 biçiminde doğrulanır (ör. `tr-TR`). Arayüz `lang` özniteliği seçili dile göre güncellenir. |
| **ISO 216 / ANSI** | Kâğıt boyutları | ✅ | A4, A3, Letter; görselden PDF'te sayfa yönü otomatik seçilir. |
| **KVKK (6698 sayılı Kanun) / GDPR** | Kişisel verilerin korunması | ✅ | Dosyalar sunucudan çıkmaz, buluta gönderilmez; yüklemeler süre sonunda silinir. `kvkk_scan` + `kvkk_apply` kişisel veriyi bulur ve kalıcı olarak kaldırır (karart / bulanıklaştır / maskele); md. 6 özel nitelikli veri ipuçları incelemeye sunulur; meta veri temizlenir. |
| **ISO/IEC 27001 (Ek A kontrolleriyle uyumlu uygulamalar)** | Bilgi güvenliği | 🟡 Uygulama düzeyi | Asgari yetki (iş başına ayrı süreç, bellek sınırı, zaman aşımı), girdi doğrulama ve boyut sınırları, sıkı CSP, Host izin listesi, CSRF, LAN eşleştirme, bağımlılık güncellemeleri (Dependabot) ve CodeQL taraması. Kurumsal sertifikasyon kurumun kendi süreçlerine bağlıdır. |
| **Unicode / ISO/IEC 10646** | Karakter kümesi | ✅ | Türkçe karakterler için gömülü DejaVu Sans; eklenen metin her platformda doğru kopyalanır/aranır. |

## Bilinen sınırlar / Known limits

- **PDF/UA:** Etiketlenmemiş belgeyi doğru şekilde etiketlemek (başlık hiyerarşisi, tablo yapısı, okuma sırası) otomatik yapılamaz; araç bunu raporlar.
- **PAdES B-T/B-LT:** Zaman damgası sunucusu ve OCSP/CRL ağ erişimi gerektirir; çevrimdışı ilke gereği kapalıdır.
- **PDF/A doğrulama:** Ghostscript bazı fontlarda metin kopyalamayı bozabilir; araç etkilenen sayfaları bildirir.

## Doğrulama / How this is verified

- Sunucu: `cd server && pytest` (PDF/A, PAdES, PDF/UA, KVKK ve ISO 8601 testleri dahil).
- Arayüz erişilebilirliği: Playwright + axe-core denetimi (WCAG 2.1 A/AA), açık ve koyu tema.
