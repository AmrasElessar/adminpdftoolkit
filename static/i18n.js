/* ===========================================================================
 * Admin PDF Toolkit — i18n engine (TR ⇄ EN)
 * ---------------------------------------------------------------------------
 * Strategy
 *   - HTML defaults to Turkish.
 *   - When EN is active, every text node + selected attributes are walked
 *     and translated via three layered dictionaries:
 *       1. exact-match string dictionary  (STRINGS)
 *       2. regex pattern dictionary       (PATTERNS) — for dynamic text
 *                                                    with numbers / vars
 *       3. modal-block HTML replacement   (HTML_BLOCKS) — for the big
 *                                                        Help / Legal /
 *                                                        Security modals
 *   - A MutationObserver re-applies translation whenever the page mutates,
 *     so JS-generated runtime strings (button.textContent = "Dönüştür", etc.)
 *     are caught automatically.
 *   - TR snapshot is preserved per-node, so switching back to TR restores
 *     the original Turkish content losslessly.
 *
 * Public API
 *   window.HTI18N.lang      → "tr" | "en"
 *   window.HTI18N.set(lang) → switch language
 *   window.HTI18N.t(text)   → translate a single string (for JS callers)
 *   window.HTI18N.addStrings({...})  → extend the exact-string dictionary
 *   window.HTI18N.addPatterns([{re, en}, ...])  → extend regex dictionary
 *
 * To add a new translation:
 *   - Static UI text     → add to STRINGS
 *   - Dynamic JS text    → add to STRINGS or PATTERNS (regex with $1, $2)
 *   - Big modal section  → edit HTML_BLOCKS
 * =========================================================================== */

(function () {
  "use strict";

  // ========================================================================
  // 1. Exact-match string dictionary (TR → EN)
  // ========================================================================
  const STRINGS = {
    // ---- Header / navigation ----
    "📖 Yardım": "📖 Help",
    "🛡 Güvenlik": "🛡 Security",
    "⚖️ Yasal": "⚖️ Legal",
    "🛠 PDF Araçları": "🛠 PDF Tools",
    "PDF araçları: birleştir, böl, sıkıştır, şifrele, watermark, sayfa numarası, kırp, döndür, sırala, sil":
      "PDF tools: merge, split, compress, encrypt, watermark, page numbers, crop, rotate, reorder, delete pages",
    "📜 Geçmiş": "📜 History",
    "🔄 Sıfırla": "🔄 Reset",
    "Yardım / Kullanım Kılavuzu": "Help / User guide",
    "VirusTotal taraması ve güvenlik bilgileri": "VirusTotal scan & security info",
    "Lisans ve Yasal Bilgiler": "License & legal information",
    "Geçmiş işlemler": "History",
    "Tüm seçimleri ve sonuçları temizle": "Clear all selections and results",
    "Dil / Language": "Dil / Language",
    "Dil seçimi": "Language",
    "Ayarlar": "Settings",
    "Admin PDF Toolkit": "Admin PDF Toolkit",
    "Offline çalışır, dosyalar dışarı çıkmaz · Çıkarsa kullanıcı sorumluluğundadır":
      "Runs offline, files do not leave the machine · Otherwise it is the user's responsibility",
    "by Engin": "by Engin",

    // ---- Connect info ----
    "Adrese tıklayarak panoya kopyalayabilirsiniz": "Click the address to copy to clipboard",
    "📍 Bu makineden:": "📍 From this machine:",
    "🌐 Ağdan (LAN):": "🌐 From the network (LAN):",
    "📱 Telefondan aynı Wi-Fi ağındaysanız LAN adresine girin.":
      "📱 From a phone on the same Wi-Fi, open the LAN address.",

    // ---- Drop zone / file ----
    "PDF seçmek için dokun": "Tap to choose a PDF",
    "veya sürükle bırak": "or drag and drop",
    "× kaldır": "× remove",
    "⏳ Analiz ediliyor...": "⏳ Analysing...",
    "Analiz": "Analysis",

    // ---- Target format card ----
    "Hedef Format": "Target format",
    "Excel (.xlsx)": "Excel (.xlsx)",
    "Word (.docx)": "Word (.docx)",
    "JPG (ZIP)": "JPG (ZIP)",
    "Tablo olarak — çağrı kayıtlarını otomatik ayrıştırır":
      "As a table — auto-parses call logs",
    "Düzenlenebilir metin": "Editable text",
    "Her sayfa ayrı resim, ZIP içinde": "Each page as a separate image, in a ZIP",

    // ---- Main / convert button ----
    "Dönüştür": "Convert",
    "Dönüştürülüyor, lütfen bekleyin...": "Converting, please wait...",
    "Mükerrerler temizleniyor...": "Removing duplicates...",
    "Mükerrer silme geri alınıyor...": "Undoing duplicate removal...",
    "Filtre uygulanıyor...": "Applying filter...",
    "Önce bir PDF seçin.": "Please select a PDF first.",
    "Hiç dosya seçilmemiş.": "No file selected.",
    "Yükleniyor...": "Loading...",
    "yükleniyor...": "loading...",
    "yüklenemedi": "failed to load",
    "Hazırlanıyor": "Preparing",
    "İlerleme alınamadı.": "Progress unavailable.",
    "İndirme başarısız.": "Download failed.",
    "Önizleme alınamadı:": "Preview failed:",
    "Analiz hatası:": "Analysis error:",
    "Taranmış PDF — yukarıdaki kırmızı butonu kullanın ↑":
      "Scanned PDF — use the red button above ↑",
    "📥 Excel İndir": "📥 Download Excel",
    "📥 Word İndir": "📥 Download Word",
    "📥 ZIP İndir": "📥 Download ZIP",
    "👥 Ekiplere Dağıt": "👥 Distribute to teams",
    "🔍 Filtrele": "🔍 Filter",
    "🔍 Seçili Formata Dönüştür": "🔍 Convert to selected format",
    "📸 Görselden (taranmış) PDF algılandı": "📸 Scanned (image-based) PDF detected",
    "Tüm Kayıtlar": "All records",
    "Aktif filtre:": "Active filter:",
    "Tümünü Temizle": "Clear all",
    "Teke Düşür": "Deduplicate",
    "Geri Al": "Undo",
    "Dağıtım Sonucu": "Distribution result",
    "📦 Tümünü ZIP İndir": "📦 Download all as ZIP",
    "✓ Birleştirme tamamlandı": "✓ Merge complete",
    "✓ Tamamlandı —": "✓ Complete —",
    "✓ Kopyalandı": "✓ Copied",
    "✓ kopyalandı": "✓ copied",
    "Kopyala": "Copy",
    "orijinal": "original",
    "kopya": "duplicate",

    // ---- Status messages ----
    "Ayarlar kaydedildi.": "Settings saved.",

    // ---- Column mapping modal ----
    "Sütunları Eşle": "Map columns",
    "Eşlendi ·": "Mapped ·",
    "Bu PDF'i Atla": "Skip this PDF",
    "Vazgeç": "Cancel",
    "Eşlemeyi Kaydet": "Save mapping",

    // ---- Legal acceptance gate ----
    "⚖️ Lisans ve Kullanım Şartları": "⚖️ License & terms of use",
    "Bu yazılımı kullanmadan önce aşağıdaki şartları okumanız ve kabul etmeniz gereklidir.":
      "You must read and accept the following terms before using this software.",
    "Kabul Etmiyorum": "I do not accept",
    "Kabul Et ve Devam Et": "Accept and continue",
    "Şartlar Kabul Edilmedi": "Terms not accepted",
    "↺ Tekrar Dene": "↺ Try again",

    // ---- Legal modal (full) ----
    "⚖️ Lisans & Yasal Bilgiler": "⚖️ License & legal information",
    "Bu yazılımı kullanmadan önce aşağıdaki şartları okuyup kabul ettiğiniz varsayılır.":
      "By using this software you are deemed to have read and accepted these terms.",
    "Anladım, Kabul Ediyorum": "Understood, I accept",
    "Kapat": "Close",
    "📜 Lisans": "📜 License",
    "📜 Telif Hakkı": "📜 Copyright",
    "❌ Garanti Reddi": "❌ Disclaimer of warranty",
    "⚠️ Sorumluluk Sınırlaması": "⚠️ Limitation of liability",
    "🔒 Veri Gizliliği": "🔒 Data privacy",
    "🛡 Veri Gizliliği & KVKK": "🛡 Data privacy & GDPR",
    "🚫 Kısıtlamalar": "🚫 Restrictions",
    "⚖️ Uygulanacak Hukuk": "⚖️ Governing law",
    "🔒 Kullanım Hakkı": "🔒 Usage rights",
    "📦 Üçüncü Taraf Kütüphaneler": "📦 Third-party libraries",
    "✅ Yürürlük & Kabul": "✅ Effect & acceptance",
    "Önemli:": "Important:",
    "Veri sorumluluğu:": "Data responsibility:",

    // ---- Security modal ----
    "🛡 Güvenlik & Doğrulama": "🛡 Security & verification",
    "✓ Üçlü Doğrulama: VirusTotal + MetaDefender + Kaspersky":
      "✓ Triple verification: VirusTotal + MetaDefender + Kaspersky",
    "94+ Antivirüs Motoru — 0 Tehdit": "94+ antivirus engines — 0 threats",
    "Bağımsız Tarama": "Independent scans",
    "Taranan Dosya": "Files scanned",
    "Tehdit": "Threats",
    "Zafiyet": "Vulnerabilities",
    "📋 Tarama Bilgileri": "📋 Scan details",
    "Tarama tarihi:": "Scan date:",
    "VirusTotal (online):": "VirusTotal (online):",
    "MetaDefender / OPSWAT (online):": "MetaDefender / OPSWAT (online):",
    "Kaspersky (lokal kurumsal):": "Kaspersky (local enterprise):",
    "Zafiyet (CVE) taraması:": "Vulnerability (CVE) scan:",
    "Dosya:": "File:",
    "Boyut:": "Size:",
    "VirusTotal'da Görüntüle ↗": "View on VirusTotal ↗",
    "MetaDefender'da Görüntüle ↗": "View on MetaDefender ↗",
    "🟡 1 Dosya Hakkında (False Positive Açıklaması)":
      "🟡 About 1 file (false-positive explanation)",
    "🔒 Bu Uygulamanın Güvenlik Tasarımı": "🔒 Security design of this application",
    "✅ Kendi Doğrulamanız": "✅ Verify it yourself",
    "Tamamen offline çalışır.": "Runs fully offline.",
    "Yönetici izni gerekmez.": "No admin rights required.",
    "Açık kaynak kütüphaneler:": "Open-source libraries:",
    "Geçmiş kaydı:": "History log:",
    "Üretici:": "Author:",
    "BT departmanına bildirim:": "Note for IT department:",

    // ---- History modal ----
    "📜 Geçmiş — Son İşlemler": "📜 History — Recent operations",
    "Yapılan dönüşümler ve dağıtımlar burada listelenir.":
      "Conversions and distributions performed are listed here.",
    "Tüm geçmiş kayıtları silinecek. Devam edilsin mi?":
      "All history records will be deleted. Continue?",

    // ---- Help modal ----
    "📖 Kullanım Kılavuzu": "📖 User guide",
    "Başlangıç": "Getting started",
    "Tek PDF": "Single PDF",
    "Çoklu PDF": "Multiple PDFs",
    "Mükerrer": "Duplicates",
    "Filtre": "Filter",
    "Ekip Dağıtımı": "Team distribution",
    "Mobil": "Mobile",
    "Güvenlik Uyarıları": "Security warnings",
    "SSS": "FAQ",
    "🚀 Başlangıç": "🚀 Getting started",
    "📄 Tek PDF Dönüşümü": "📄 Single PDF conversion",
    "📂 Çoklu PDF (Birleştirme)": "📂 Multiple PDFs (merge)",
    "🟧 Mükerrer Telefon Silme": "🟧 Duplicate phone removal",
    "🔍 Sütun Bazlı Filtreleme": "🔍 Column-based filtering",
    "👥 Ekip Dağıtımı": "👥 Team distribution",
    "📸 Taranmış (Görsel) PDF — OCR": "📸 Scanned (image) PDF — OCR",
    "📱 Mobil / Tablet Kullanımı": "📱 Mobile / Tablet usage",
    "🔐 Güvenlik Uyarıları (HTTPS / Sertifika / İndirme)":
      "🔐 Security warnings (HTTPS / Certificate / Download)",
    "❓ Sık Sorulanlar": "❓ Frequently asked questions",
    "Sol panel:": "Left panel:",
    "Sağ panel:": "Right panel:",
    "Üstte:": "Top:",

    // ---- Filter modal ----
    "← Sütunlar": "← Columns",
    "Hangi sütuna göre filtrelemek istiyorsunuz?": "Which column do you want to filter by?",
    "Filtrelemek istediğiniz sütunu seçin:": "Select the column to filter by:",
    "Bu sütunda hangi değerleri göstermek istersiniz?":
      "Which values from this column should be shown?",
    "Değerlerde ara...": "Search values...",
    "Tümünü seç": "Select all",
    "Tümünü kaldır": "Deselect all",
    "Uygula": "Apply",
    "Bu filtreyi kaldır": "Remove this filter",

    // ---- Name modal ----
    "Word Dosya Adı": "Word file name",
    "Çıktı Adı —": "Output name —",
    "Her dosya için Word çıktısının adını belirleyin (uzantı eklenecek):":
      "Set the Word output name for each file (extension will be appended):",
    "Devam Et": "Continue",

    // ---- Settings modal ----
    "⚙ Ayarlar · Özel Oran": "⚙ Settings · Custom weights",
    "Dağıtımda \"Özel oran\" seçtiğinizde hangi yöntem kullanılacak?":
      "When \"Custom weights\" is selected for distribution, which method is used?",
    "Doğrudan Oran": "Direct ratio",
    "Puanlama Bazlı": "Score-based",
    "Puanlama Faktörleri": "Scoring factors",
    "+ Faktör Ekle": "+ Add factor",
    "Toplam:": "Total:",
    "Kaydet": "Save",
    "Faktör adı": "Factor name",
    "Sil": "Delete",

    // ---- Distribute modal ----
    "Ekiplere Dağıt": "Distribute to teams",
    "+ Ekip Ekle": "+ Add team",
    "Ekip adı": "Team name",
    "Oran": "Ratio",
    "Dağıtım Türü": "Distribution type",
    "Sıralı": "Sequential",
    "Rastgele (döngüsel)": "Round-robin",
    "Özel oran": "Custom weights",
    "Dağıt ve İndir": "Distribute and download",

    // ---- Misc tooltips ----
    "Bu telefon birden fazla kayıtta var (orijinal)":
      "This phone appears in multiple records (original)",
    "Aynı telefonun kopyası — 'Teke Düşür' ile silinebilir":
      "Duplicate of the same phone — can be removed with 'Deduplicate'",
    "Aynı telefon numarasına sahip kayıtların 2. ve sonraki satırları silinecek (ilk geçen kalır). Devam edilsin mi?":
      "Rows 2+ with the same phone number will be removed (the first occurrence is kept). Continue?",
    "Tüm yüklemeyi, önizlemeyi ve sonuçları temizleyip sayfayı baştan yüklemek istediğinize emin misiniz?":
      "Are you sure you want to clear all uploads, previews and results and reload the page?",
    "Tüm yüklemeyi, önizlemeyi ve sonuçları temizleyip sayfayı baştan yüklemek istediğinize emin misiniz?\n\n":
      "Are you sure you want to clear all uploads, previews and results and reload the page?\n\n",
    "Boş ad olamaz. Lütfen tüm satırları doldurun.":
      "Name cannot be empty. Please fill in all rows.",

    // ---- Distribution result strategies ----
    "Sıralı dağıtım": "Sequential distribution",
    "Rastgele dağıtım": "Round-robin distribution",
    "Özel oran dağıtımı": "Custom-weight distribution",

    // ---- Stat cards ----
    "Toplam kayıt": "Total records",
    "uyumlulardan": "from compatible",

    // ---- Generic words ----
    "kayıt": "records",
    "sayfa": "pages",
    "dosya": "files",
    "telefon": "phone numbers",
    "satır": "rows",
    "ekip": "team",
    "ekibe": "teams",

    // ---- Progress / completion ----
    "Tamamlandı": "Complete",
    "İşleniyor": "Processing",
    "Yükleniyor": "Loading",

    // ---- History (empty state, footer) ----
    "Henüz işlem yok.": "No operations yet.",
    "Geçmiş yüklenemedi.": "Failed to load history.",

    // ---- Distribute modal — strategy long descriptions ----
    "Sıralı — art arda blok halinde (ör: 1-100 Ekip1, 101-200 Ekip2)":
      "Sequential — contiguous blocks (e.g. 1–100 → Team 1, 101–200 → Team 2)",
    "Rastgele (döngüsel) — 1→E1, 2→E2, 3→E3, 4→E1... sırasıyla pay":
      "Round-robin — 1→T1, 2→T2, 3→T3, 4→T1… distributed in turn",
    "Özel oran — Ayarlar'dan mod seçimli (doğrudan % veya puanlama)":
      "Custom weights — pick a mode from Settings (direct % or score-based)",
    "Ekip ekleyin.": "Add a team.",
    "En az iki ekip ekleyin.": "Add at least two teams.",

    // ---- Settings modal — long radio descriptions ----
    "Doğrudan Oran — her ekibin yüzdesini yazarsınız (toplamı %100)":
      "Direct ratio — enter each team's percentage (must total 100%)",
    "Puanlama Bazlı — faktörler × ağırlık ile ekip puanı hesaplanır":
      "Score-based — team score = factors × weights",

    // ---- Result panel ----
    "Birleştirme tamamlandı": "Merge complete",
    "Dağıtım tamamlandı": "Distribution complete",

    // ---- Filter — empty cell label ----
    "(boş)": "(empty)",

    // ---- OCR / scanned hint ----
    "Bu PDF metin katmanı içermiyor. Seçili formata göre (Word/Excel için OCR, JPG için direkt) dönüştür:":
      "This PDF has no text layer. Convert based on selected format (OCR for Word/Excel, direct for JPG):",

    // ---- Footer ----
    "Local server · yüklenen dosyalar dönüşüm biter bitmez silinir":
      "Local server · uploaded files are deleted as soon as conversion finishes",
    "Yerel sunucu · yüklenen dosyalar dönüşüm biter bitmez silinir":
      "Local server · uploaded files are deleted as soon as conversion finishes",

    // ---- Misc inline strings inside modals ----
    "Henüz hiçbir dönüşüm yapılmadı.": "No conversions performed yet.",
    "Dönüşüm geçmişi yok.": "No conversion history.",

    // ---- Filter modal — chip "remove this filter" tooltip ----
    "Bu filtreyi temizle": "Clear this filter",

    // ---- PDF Tools modal (v1.1 — Section A) ----
    "🛠 PDF Araçları": "🛠 PDF Tools",
    "İhtiyacınız olan aracı seçin · Tüm işlemler bilgisayarınızda yapılır, dosya dışarı çıkmaz.":
      "Pick the tool you need · Everything runs on your machine, files do not leave it.",
    "← Araçlar": "← Tools",
    "Kapat": "Close",
    "Dönüştür": "Run",
    "İşleniyor…": "Processing…",
    "PDF Birleştir": "Merge PDFs",
    "Birden fazla PDF'i tek dosyada": "Combine multiple PDFs into one",
    "PDF Böl": "Split PDF",
    "Sayfa aralıklarına ayır (ZIP)": "Split into ranges (ZIP)",
    "Sıkıştır": "Compress",
    "Dosya boyutunu küçült": "Reduce file size",
    "Şifre Ekle": "Encrypt",
    "AES-256 ile koru": "Protect with AES-256",
    "Şifre Kaldır": "Decrypt",
    "Mevcut şifreyi sök": "Remove existing password",
    "Metin Damga": "Text watermark",
    "Yazı filigranı ekle": "Add a text watermark",
    "Görsel Damga": "Image watermark",
    "Logo / görsel filigran": "Logo / image watermark",
    "Sayfa Numarası": "Page numbers",
    "Otomatik numaralandır": "Auto-number pages",
    "Header / Footer": "Header / Footer",
    "Üst-alt yazı ekle": "Add top / bottom text",
    "Kenar Kırp": "Crop margins",
    "Kenar boşluklarını kes": "Trim page edges",
    "Döndür": "Rotate",
    "Sayfaları çevir": "Rotate pages",
    "Sayfa Sırala": "Reorder pages",
    "Sayfa düzenini değiştir": "Change page order",
    "Sayfa Sil": "Delete pages",
    "İstenmeyen sayfaları çıkar": "Drop unwanted pages",
    "Görselden PDF": "Images → PDF",
    "JPG/PNG/WebP → PDF": "JPG/PNG/WebP → PDF",
    "Word'den PDF": "Word → PDF",
    ".docx → PDF": ".docx → PDF",
    "Excel'den PDF": "Excel → PDF",
    ".xlsx → PDF": ".xlsx → PDF",
    "HTML'den PDF": "HTML → PDF",
    "HTML metnini PDF yap": "Render HTML to PDF",
    "URL'den PDF": "URL → PDF",
    "Web sayfasını yakala": "Snapshot a web page",
    "PDF'ten Markdown": "PDF → Markdown",
    ".md olarak indir": "Download as .md",
    "PDF'ten CSV": "PDF → CSV",
    "Tabloları CSV olarak çıkar": "Export tables as CSV",
    "Boş Sayfa Bul": "Find blank pages",
    "Hangi sayfalar boş, listele": "List which pages are blank",
    "Boş Sayfa Sil": "Remove blank pages",
    "Boş sayfaları otomatik çıkar": "Auto-drop blank pages",
    "İmza Tespiti": "Signature detection",
    "PDF imzalı mı, kontrol et": "Check whether the PDF is signed",
    "Kategorize Et": "Classify",
    "Fatura / dekont / sözleşme / …": "Invoice / receipt / contract / …",

    // ---- PDF Editor modal (v1.4 — Phase 4a) ----
    "🖊 PDF Düzenle": "🖊 Edit PDF",
    "PDF düzenleyici: vurgu / not / metin / şekil / mevcut metni değiştir":
      "PDF editor: highlight / note / text / shapes / replace existing text",
    "Vurgu / not / metin / şekil ekle veya mevcut metni değiştir · Tüm işlemler bilgisayarınızda yapılır.":
      "Highlight / note / add text / shapes, or replace existing text · Everything runs on your machine.",
    "📂 PDF Aç": "📂 Open PDF",
    "💾 Kaydet": "💾 Save",
    "Düzenleme Modu": "Edit mode",
    "Vurgu / Not": "Highlight / Note",
    "Metin / Şekil Ekle": "Add text / shape",
    "Mevcut Metni Değiştir": "Replace existing text",
    "Yazı Tipi": "Font",
    "Aile": "Family",
    "Boyut": "Size",
    "Renk": "Color",
    "Kalın": "Bold",
    "Italik": "Italic",
    "Belge": "Document",
    "Yakınlaştırma": "Zoom",
    "— PDF açılmadı —": "— No PDF opened —",
    "Önceki sayfa": "Previous page",
    "Sonraki sayfa": "Next page",
    "Uzaklaştır": "Zoom out",
    "Yakınlaştır": "Zoom in",
    "Mod: Vurgu / Not": "Mode: Highlight / Note",
    "Mod: Metin / Şekil Ekle": "Mode: Add text / shape",
    "Mod: Mevcut Metni Değiştir": "Mode: Replace existing text",
    "Düzenlemek için bir PDF açın": "Open a PDF to start editing",
    "📂 PDF Seç": "📂 Pick PDF",
    "Düzenleme modları (vurgu, metin ekle, mevcut metni değiştir) sonraki sürümlerde devreye giriyor. Şu an PDF görüntüleyici aktif: sayfaları gezebilir, yakınlaştırabilirsiniz.":
      "Edit modes (highlight, add text, replace) light up in upcoming releases. The viewer is live now: paginate and zoom freely.",
    "Yükleniyor…": "Loading…",
    "Hazır.": "Ready.",
    "Kaydediliyor…": "Saving…",
    "İndirildi.": "Downloaded.",
    "Yazı tipi listesi alınamadı — varsayılan kullanılacak.":
      "Could not load the font list — falling back to defaults.",

    // ---- PDF Editor — Phase 4b additions ----
    "Vurgula": "Highlight",
    "Altçizgi": "Underline",
    "Üstçizgi": "Strikeout",
    "Sticky": "Sticky",
    "Çizim": "Draw",
    "Görsel": "Image",
    "Metni vurgula": "Highlight text",
    "Metnin altını çiz": "Underline text",
    "Metnin üstünü çiz": "Strike through text",
    "Sticky not bırak": "Drop sticky note",
    "Serbest çizim": "Free draw",
    "Görsel / imza ekle": "Add image / signature",
    "Sayfa İşlemleri": "Page actions",
    "↶ Geri Al": "↶ Undo",
    "✕ Sayfayı Temizle": "✕ Clear page",
    "Bu sayfada son işlemi geri al": "Undo the last operation on this page",
    "Bu sayfanın tüm işlemlerini sil": "Clear all operations on this page",
    "Yazı Tipi / Renk": "Font / Color",
    "Yeni metin / şekil ekle (Faz 4c'de aktif)":
      "Add new text / shapes (active in Phase 4c)",
    "Mevcut metni değiştir (Faz 4d'de aktif)":
      "Replace existing text (active in Phase 4d)",
    "Vurgu / altçizgi / üstçizgi / sticky not / serbest çizim / görsel-imza ekleme aktif. \"Yeni metin ekle\" ve \"mevcut metni değiştir\" sonraki sürümlerde geliyor.":
      "Highlight / underline / strikeout / sticky note / free draw / image-signature are live. \"Add new text\" and \"replace existing text\" come in upcoming releases.",
    "Not içeriği:": "Note content:",
    "Bu sayfada geri alınacak işlem yok.": "No operations to undo on this page.",
    "Bu sayfanın tüm işlemleri silindi.": "All operations on this page were cleared.",
    "Görsel hazır — yerleştirmek için canvas'a sürükleyin.":
      "Image staged — drag a rectangle on the canvas to place it.",

    // ---- PDF Editor — Phase 4c additions ----
    "Metin": "Text",
    "Dikdörtgen": "Rectangle",
    "Elips": "Ellipse",
    "Çizgi": "Line",
    "Yeni metin ekle": "Add new text",
    "Dikdörtgen çiz": "Draw rectangle",
    "Elips / daire çiz": "Draw ellipse / circle",
    "Düz çizgi çiz": "Draw straight line",
    "Yeni metin / şekil ekle": "Add new text / shape",
    "Metin yazın · Enter ile onayla, Esc ile iptal":
      "Type text · Enter to commit, Esc to cancel",

    // ---- PDF Editor — Phase 4d (replace mode) ----
    "Mevcut metni tıkla, düzenle, kaydet":
      "Click existing text, edit, save",
    "Sayfadaki metin parçalarına tıklayın · Açılan kutuya yeni metni yazıp Enter'a basın · Boş bırakırsanız orijinal silinir.":
      "Click on text spans · Type the new text and press Enter · Leave empty to delete the original.",
    "Yeni metin · boş bırakılırsa silinir": "New text · empty = delete original",
    "Metin parçaları taranıyor…": "Scanning text spans…",
    "Bu PDF metin değiştirmeye uygun değil.": "This PDF can't be edited as text.",

    // ---- Dashboard hub (v1.10+) ----
    "Tek pencerede 35+ PDF aracı": "35+ PDF tools in a single window",
    "%100 offline · KVKK uyumlu · Veri makineyi terk etmez.":
      "100% offline · GDPR-style data protection · Files never leave the machine.",
    "🔒 Offline": "🔒 Offline",
    "📐 153 font ailesi": "📐 153 font families",
    "🌐 TR · EN": "🌐 TR · EN",
    "PDF dosyanı sürükle-bırak veya seç": "Drag & drop a PDF or pick one",
    "PDF sürükle-bırak veya seç": "Drag & drop or pick a PDF",
    "Akıllı yönlendirme": "Smart routing",
    "Aşağıda kategoriden ihtiyacın olan akışa geç":
      "Pick a category below to jump into the right flow",
    "Ne yapmak istiyorsun?": "What do you want to do?",
    "Kategori seç veya yukarıya PDF bırak": "Pick a category or drop a PDF above",
    "4 İŞLEM": "4 OPS",
    "13 İŞLEM": "13 OPS",
    "11 OP": "11 OPS",
    "5 İŞLEM": "5 OPS",
    "3 İŞLEM": "3 OPS",
    "YENİ": "NEW",
    "Dönüştür": "Convert",
    "PDF'i Excel, Word veya JPG'ye çevir. Taranmış belgeler için OCR otomatik devreye girer.":
      "Convert PDF to Excel, Word or JPG. OCR kicks in automatically for scanned documents.",
    "Düzenle (sayfa)": "Edit (page-level)",
    "Sayfa seviyesinde işlemler: birleştir, böl, sıkıştır, şifrele, watermark, sayfa numarası, kırp, döndür, sırala, sil.":
      "Page-level operations: merge, split, compress, encrypt, watermark, page numbers, crop, rotate, reorder, delete.",
    "Editör (içerik)": "Editor (content)",
    "İçerik seviyesinde tam editör: vurgu, sticky, çizim, metin/şekil ekleme, mevcut metni akıllı font matching ile değiştir.":
      "Full content-level editor: highlight, sticky note, free draw, add text/shapes, replace existing text with smart font matching.",
    "Analiz": "Analyze",
    "Boş sayfa tespiti, dijital imza algılama, otomatik kategori (fatura/dekont/sözleşme/…), deep-analyze raporu.":
      "Blank-page detection, digital signature check, auto-classify (invoice/receipt/contract/…), deep-analyze report.",
    "Oluştur (→ PDF)": "Generate (→ PDF)",
    "Diğer formatlardan PDF üret: görsel, Word, Excel, HTML, doğrudan URL'den web sayfası.":
      "Make PDFs from other formats: images, Word, Excel, HTML, or directly from a URL.",
    "Çıkar (PDF →)": "Extract (PDF →)",
    "PDF içeriğini parçala: tabloları CSV'ye, metni Markdown'a, görselleri ZIP'e, içindekiler ve metadata'yı dışa al.":
      "Pull data out: tables to CSV, text to Markdown, images to ZIP, outline + metadata export.",
    "Bul / Vurgula": "Find / Highlight",
    "PDF içinde metin ara, eşleşmeleri bbox + bağlamla listele, doğrudan editöre gönder ya da topluca vurgula.":
      "Search text inside the PDF, list matches with bbox + context, jump to editor or bulk-highlight.",
    "Toplu İşlem": "Batch operations",
    "Birden fazla PDF'i aynı anda işle: birleştirilmiş Excel, ekiplere dağıtım, mükerrer telefon temizliği.":
      "Process many PDFs at once: merged Excel, team distribution, duplicate-phone cleanup.",
    "🔎 Bul / Vurgula yakında — şu an PDF Düzenle modu içinde \"Mevcut Metni Değiştir\" üzerinden span araması yapabilirsin.":
      "🔎 Find / Highlight is coming soon — for now, span search lives inside Edit PDF → \"Replace existing text\".",

    // ---- LAN access bar (v1.10.x) ----
    "LAN erişimi açık": "LAN access on",
    "LAN erişimi açık · ": "LAN access on · ",
    "LAN erişimi kapalı": "LAN access off",
    "LAN erişimini kapat": "Disable LAN access",
    "LAN / uzaktan erişimi aç-kapa": "Toggle LAN / remote access",
    "LAN açma başarısız oldu.": "Couldn't enable LAN access.",
    "LAN kapatma başarısız oldu.": "Couldn't disable LAN access.",
    "📋 Kopyala": "📋 Copy",
    "📡 LAN": "📡 LAN",
    "Tıklayıp kopyalayın": "Click to copy",
    "Seçim granüleritesi": "Selection granularity",
    "Kelime": "Word",
    "Satır": "Line",
    "Paragraf": "Paragraph",
    "Vektör (metin)": "Vector (text)",
    "Görsel/Taranmış": "Image / Scanned",
    "Karışık": "Mixed",
    "Boş": "Empty",
    "Bu PDF görsel/taranmış — metin katmanı yok. Mevcut metni değiştir modu çalışmaz; OCR ile metin çıkarın veya overlay modunda yeni metin/şekil ekleyin.":
      "This PDF is image-based / scanned — no text layer. Replace mode won't work; extract text via OCR or use overlay mode to add new text / shapes.",
    "PDF'te ne metin ne de görsel bulunamadı.":
      "Found neither text nor images in this PDF.",

    // ---- Mobile / LAN access (v1.0) ----
    "📱 Mobil": "📱 Mobile",
    "📱 Mobil Erişim": "📱 Mobile Access",
    "Mobil Erişim Kapalı": "Mobile Access Disabled",
    "Mobil Erişim Açık": "Mobile Access Enabled",
    "Mobil erişim kapalı.": "Mobile access disabled.",
    "Mobil erişim açık.": "Mobile access enabled.",
    "Mobil Aç": "Open mobile access",
    "Mobil Kapat": "Close mobile access",
    "Mobil cihazınızda açmak için bu adresi kullanın:":
      "Open this URL on your mobile device:",
    "Bu adresi sadece güvendiğin cihazlarla paylaş.":
      "Only share this URL with devices you trust.",
    "Adresi Kopyala": "Copy URL",
    "Kopyalandı!": "Copied!",
    "Yetkisiz erişim": "Unauthorized",
    "Bu sayfaya erişmek için geçerli bir mobil erişim anahtarı gerekiyor. Sunucu makinesinden \"📱 Mobil Aç\" ile yeni bir bağlantı oluşturabilirsiniz.":
      "A valid mobile access key is required to view this page. Use \"📱 Open mobile access\" on the host computer to generate a new link.",
    "Bu işlem yalnızca sunucu makinesinden yapılabilir.":
      "This action can only be performed from the host computer.",
    "Mobil aç işlemi başarısız oldu.":
      "Failed to enable mobile access.",
    "Mobil kapatma işlemi başarısız oldu.":
      "Failed to disable mobile access.",
    "Sunucuyu çalıştıran bilgisayardan açmalısın.":
      "You must enable this from the host computer.",
    "Mobil erişim açıldı. Telefondan yukarıdaki adresi kullanabilirsin.":
      "Mobile access enabled. You can now open the URL above on your phone.",
    "Mobil erişim kapatıldı. Tüm mobil cihazların oturumu sonlandı.":
      "Mobile access disabled. All mobile sessions are now revoked.",
    "Bağlantıyı sıfırla (yeni anahtar üret)":
      "Rotate link (issue a new key)",
    "Geçersiz veya eksik mobil erişim anahtarı.":
      "Invalid or missing mobile access key.",
    "Mobil erişim kapalı. Sunucu makinesinden açılmalı.":
      "Mobile access disabled. Must be enabled from the host computer.",

    // Inline checkbox UI on the connect-info bar
    "Mobil/LAN kapalı": "Mobile/LAN disabled",
    "Açık · adresi yenilemek için kapat ve tekrar aç":
      "Enabled · close and re-open to refresh the URL",

    // ---- Safety badge (kindBadge sibling) — verdict text + tooltip ----
    "✓ Güvenli": "✓ Safe",
    "ℹ Bilgi": "ℹ Info",
    "⚠ Dikkat": "⚠ Caution",
    "🚫 Tehdit": "🚫 Threat",
    "Şüpheli içerik bulunmadı.": "No suspicious content found.",
    "Düşük seviyeli bilgilendirme — risk yok.": "Low-level notice — no risk.",
    "Şüpheli yapısal unsur bulundu.": "Suspicious structural element detected.",
    "Tehlikeli içerik veya tehdit tespit edildi.": "Dangerous content or threat detected.",

    // ---- Safety detail box: antivirus row fragments ----
    "🛡 Antivirüs taraması (ClamAV):": "🛡 Antivirus scan (ClamAV):",
    "🛡 Antivirüs taraması (ClamAV): tarama hatası —":
      "🛡 Antivirus scan (ClamAV): scan error —",
    "🚫 Tehdit:": "🚫 Threat:",
    "Temiz": "Clean",
    "— bu PDF işlenmemelidir.": "— this PDF should not be processed.",
    "ClamAV kurulu değil — yalnızca yapısal kontrol yapıldı.":
      "ClamAV not installed — only structural check was performed.",
    "tarama hatası —": "scan error —",
    "tarama hatası": "scan error",

    // ---- Finding descriptions (from pdf_safety.py _SUSPICIOUS_PATTERNS) ----
    "JavaScript çalıştırılabilir kodu": "Executable JavaScript code",
    "JavaScript referansı": "JavaScript reference",
    "Dosya açılınca otomatik tetiklenen aksiyon":
      "Action triggered automatically when file opens",
    "Additional Actions (sayfa olayları)": "Additional Actions (page events)",
    "Komut/uygulama başlatma": "Command / application launch",
    "Gömülü dosya (gizli ek)": "Embedded file (hidden attachment)",
    "Flash/multimedya gömme": "Flash / multimedia embed",
    "Form gönderme aksiyonu": "Form submission action",
    "Dış dosyaya bağlantı": "Link to external file",
    "Dış URL bağlantısı": "External URL link",
    "XFA form (eski/karmaşık)": "XFA form (legacy / complex)",

    // ---- PDF kind labels (kindBadge / batch list `kind_label` from backend) ----
    "Görselden PDF": "Image-based PDF",
    "📸 Görselden PDF": "📸 Image-based PDF",
    "Görselden (taranmış) PDF algılandı": "Image-based (scanned) PDF detected",
    "Çağrı kayıtları": "Call logs",
    "Çağrı Kaydı": "Call log",
    "Metin belgesi": "Text document",
    "PDF değil": "Not a PDF",
    "Farklı tablo yapısı": "Different table structure",
    "Tablo yok": "No table",
    "Şifreli PDF": "Encrypted PDF",
    "Bozuk PDF": "Corrupt PDF",
    "Boş PDF": "Empty PDF",
    "uyumlu": "compatible",
    "uyumsuz": "incompatible",

    // ---- Progress / phase labels (batch + single + OCR) ----
    "Dosyalar yükleniyor...": "Uploading files...",
    "Dosya yükleniyor...": "Uploading file...",
    "Başlatılıyor": "Starting",
    "İşleniyor": "Processing",
    "Excel yazılıyor": "Writing Excel",
    "Word'e dönüştürülüyor": "Converting to Word",
    "Sayfalar render ediliyor": "Rendering pages",
    "Çıktı yazılıyor": "Writing output",
    "OCR okunuyor": "Running OCR",
    "OCR motoru yükleniyor (ilk seferde 1-2 dk)":
      "Loading OCR engine (1–2 min on first run)",
    "Tamamlandı · indiriliyor...": "Complete · downloading...",
    "Hata:": "Error:",

    // ---- Inline fragments around <strong> bits in dynamic result text ----
    // For "⚠ <strong>5 telefon</strong> mükerrer · <strong>5 satır</strong> teke düşürülebilir."
    "mükerrer ·": "duplicate ·",
    "teke düşürülebilir.": "can be deduplicated.",
    "teke düşürülebilir": "can be deduplicated",

    // For "Eşlendi · 5 sütun" if walked piecewise
    "sütun": "columns",

    // ---- Settings radio long descriptions (text node AFTER <strong>) ----
    // <strong>Doğrudan Oran</strong> — her ekibin yüzdesini yazarsınız (toplamı %100)
    "— her ekibin yüzdesini yazarsınız (toplamı %100)":
      "— enter each team's percentage (must total 100%)",
    "— faktörler × ağırlık ile ekip puanı hesaplanır":
      "— team score = factors × weights",

    // ---- Distribute strategy long descriptions (also <strong>X</strong> — Y) ----
    "— art arda blok halinde (ör: 1-100 Ekip1, 101-200 Ekip2)":
      "— contiguous blocks (e.g. 1–100 → Team 1, 101–200 → Team 2)",
    "— 1→E1, 2→E2, 3→E3, 4→E1... sırasıyla pay":
      "— 1→T1, 2→T2, 3→T3, 4→T1… distributed in turn",
    "— Ayarlar'dan mod seçimli (doğrudan % veya puanlama)":
      "— pick a mode from Settings (direct % or score-based)",

    // ---- Distribute → Score table (custom-weights "Score-based" mode) ----
    // Headers
    "Ekip": "Team",
    "Toplam Puan": "Total Score",
    "Pay": "Share",
    "Toplam": "Total",

    // Distribution summary placeholders
    "Puanları girin.": "Enter scores.",
    "Oran/yüzde belirleyin.": "Set the ratio/percentage.",

    // Empty-factors warning (parts split around <strong>) :
    //   ⚠ Henüz faktör tanımlanmamış. Önce <strong>⚙ Ayarlar → Puanlama Bazlı</strong>
    //   sekmesinden faktörleri ekleyin (toplam %100 olmalı). Veya
    //   <strong>"Doğrudan Oran"</strong> moduna geçin.
    "⚠ Henüz faktör tanımlanmamış. Önce":
      "⚠ No factors defined yet. First open the",
    "⚙ Ayarlar → Puanlama Bazlı": "⚙ Settings → Score-based",
    "sekmesinden faktörleri ekleyin (toplam %100 olmalı). Veya":
      "tab and add factors (must total 100%). Or switch to",
    "\"Doğrudan Oran\"": "\"Direct Ratio\"",
    "moduna geçin.": "mode.",

    // Empty-teams hint (parts split around <strong>) :
    //   ℹ Yukarıdan <strong>+ Ekip Ekle</strong> ile ekip ekleyin; ...
    "ℹ Yukarıdan": "ℹ Above, click",
    "ile ekip ekleyin; her ekip için faktör puan girişi burada açılacak.":
      "to add a team; per-team factor score inputs will appear here.",

    // Weight-mismatch warning (parts split around <strong>) :
    //   ⚠ Faktör ağırlıklarının toplamı <strong>%85</strong> —
    //   <strong>%100 olmalı</strong>. ⚙ Ayarlar'dan düzeltin.
    "⚠ Faktör ağırlıklarının toplamı": "⚠ Total of factor weights is",
    "%100 olmalı": "must be 100%",
    ". ⚙ Ayarlar'dan düzeltin.": ". Fix it from ⚙ Settings.",

    // ---- Settings: empty factors hint (script-rendered) ----
    "ℹ Henüz faktör tanımlı değil. Aşağıdaki":
      "ℹ No factors defined yet. Start with",
    "ile başlayın. Toplam ağırlık":
      "below. Total weight must be",
    "olmalı.": "",  // standalone tail handled by surrounding fragments

    // ---- Confirmation prompts ----
    "Tüm sütun filtrelerini kaldırmak istediğinize emin misiniz?":
      "Are you sure you want to remove all column filters?",
    "Hiç değer seçmediniz. Bu sütun için filtre kaldırılsın mı?":
      "You haven't selected any values. Remove the filter for this column?",
    "Modal'ı kapatıp doğrudan 'Excel İndir' ile tek dosya almak ister misiniz?":
      "Close this dialog and download a single file via 'Download Excel'?",
    "(Ayarlar, yasal kabul ve geçmiş korunur.)":
      "(Settings, legal acceptance and history are preserved.)",

    // ---- Server / network errors ----
    "Sunucuya ulaşılamadı. Sunucu kapanmış olabilir; bağlantınızı kontrol edin.":
      "Server unreachable. The server may be down; check your connection.",
    "Sunucuda hata oluştu. Lütfen tekrar deneyin.":
      "Server error. Please try again.",
    "İş süresi dolmuş ya da bulunamadı. Lütfen baştan deneyin.":
      "Job timed out or was not found. Please start over.",
    "İşlem henüz tamamlanmadı. Birkaç saniye bekleyip tekrar deneyin.":
      "Operation not yet finished. Wait a few seconds and try again.",
    "İşlem çok uzun sürdü. Daha küçük bir dosya deneyin.":
      "Operation took too long. Try a smaller file.",
    "Dosya boyutu çok büyük.": "File too large.",

    // ---- Distribute validation ----
    "Dağıtım yapabilmek için en az bir ekip gerekli.":
      "At least one team is required to distribute.",
    "Henüz ekip eklemediniz.": "You haven't added any teams yet.",
    "En az bir faktör tanımlayın.": "Define at least one factor.",
    "Ekip adları benzersiz olmalı.": "Team names must be unique.",
    "Oranlar/yüzdeler pozitif olmalı.": "Ratios/percentages must be positive.",
    "Her ekip için en az bir faktöre puan girin.":
      "Enter a score for at least one factor per team.",
    "\n\n⚙ Ayarlar'dan faktör ağırlıklarını düzeltin.":
      "\n\nFix the factor weights from ⚙ Settings.",

    // ---- Column-mapping modal ----
    "En az bir sütun eşleyin veya 'Atla' seçin.":
      "Map at least one column or pick 'Skip'.",
    "PDF farklı yapıda. Her biri için sütunları eşleyin veya atlayın.":
      "PDFs have different structures. Map columns for each one or skip them.",
    "eşleme gerekir": "mapping required",

    // ---- Preview ----
    "Önizleme — ": "Preview — ",
    "Önizlemede": "In preview",
    "ilk satırlar": "first rows",
    "başlık hariç": "header excluded",

    // ---- Distribution result strategy labels ----
    "Sıralı dağıtım": "Sequential distribution",
    "Rastgele (döngüsel) dağıtım": "Round-robin distribution",
    "Özel oranlı dağıtım": "Custom-weight distribution",

    // ---- Sheet names produced by backend (.xlsx tabs) ----
    "Birleşik Excel": "Merged Excel",
    "AI Özeti (Ham)": "AI Summary (Raw)",

    // ---- Result panel: "✓ <strong>Mükerrer telefonlar silindi</strong>" ----
    "✓": "✓",
    "Mükerrer telefonlar silindi": "Duplicate phones removed",
    " Uyarı: ": " Warning: ",
  };

  // ========================================================================
  // 2. Pattern (regex) dictionary — for dynamic strings with numbers / vars
  //    Use $1, $2, … to reference capture groups.
  //    Order matters; first match wins.
  // ========================================================================
  const PATTERNS = [
    // Drop hint — "en fazla 2048 MB/dosya"
    { re: /^Birden fazla PDF seçerseniz otomatik birleştirme — en fazla (\d+) MB\/dosya$/,
      en: "Pick multiple PDFs to auto-merge — max $1 MB/file" },

    // ---- PDF Editor (v1.4) — dynamic strings ----
    // "doc.pdf · 12 sayfa · 234 KB"
    { re: /^(.+) · (\d+) sayfa · (\d+) KB$/,
      en: "$1 · $2 pages · $3 KB" },
    // "PDF açılamadı: <reason>"
    { re: /^PDF açılamadı: (.+)$/,
      en: "Could not open PDF: $1" },
    // "pdf.js yüklenemedi: <reason>"
    { re: /^pdf\.js yüklenemedi: (.+)$/,
      en: "pdf.js failed to load: $1" },
    // "Kaydetme başarısız: <reason>"
    { re: /^Kaydetme başarısız: (.+)$/,
      en: "Save failed: $1" },
    // "Operasyon eklendi (toplam 5)."
    { re: /^Operasyon eklendi \(toplam (\d+)\)\.$/,
      en: "Operation added (total $1)." },
    // "Son işlem geri alındı (4 kaldı)."
    { re: /^Son işlem geri alındı \((\d+) kaldı\)\.$/,
      en: "Last operation undone ($1 remaining)." },
    // "12 metin parçası bulundu."
    { re: /^(\d+) metin parçası bulundu\.$/,
      en: "Found $1 text spans." },
    // "Metin parçaları alınamadı: <reason>"
    { re: /^Metin parçaları alınamadı: (.+)$/,
      en: "Failed to load text spans: $1" },
    // "5/13 sayfa görsel-tabanlı (metin değiştirme yalnızca metinli sayfalarda çalışır)."
    { re: /^(\d+)\/(\d+) sayfa görsel-tabanlı \(metin değiştirme yalnızca metinli sayfalarda çalışır\)\.$/,
      en: "$1/$2 pages are image-based (text replace works only on text pages)." },
    // "Tüm 13 sayfa metin içeriyor — replace modu kullanılabilir."
    { re: /^Tüm (\d+) sayfa metin içeriyor — replace modu kullanılabilir\.$/,
      en: "All $1 pages contain text — replace mode is available." },
    // "İndirildi · 8 uygulandı, 0 atlandı."
    { re: /^İndirildi · (\d+) uygulandı, (\d+) atlandı\.$/,
      en: "Downloaded · $1 applied, $2 skipped." },
    // Existing dynamic mode label updates
    { re: /^Mod: (.+) · (.+)$/,
      en: (m) => "Mode: " + (window.HTI18N?.t?.(m[1]) || m[1])
                  + " · " + (window.HTI18N?.t?.(m[2]) || m[2]) },

    // "✓ Birleştirme tamamlandı · 234 kayıt"
    { re: /^✓ Birleştirme tamamlandı · ([\d.,]+) kayıt$/,
      en: "✓ Merge complete · $1 records" },

    // "1 PDF işlendi" / "12 PDF işlendi."  (with optional warning suffix)
    { re: /^(\d+) PDF işlendi\.?(.*)$/,
      en: "$1 PDF processed.$2" },

    // "5 telefon mükerrer · 5 satır teke düşürülebilir."
    { re: /^⚠?\s*([\d.,]+) telefon mükerrer · ([\d.,]+) satır teke düşürülebilir\.?$/,
      en: "⚠ $1 duplicate phones · $2 rows can be deduplicated." },

    // "234 kayıt birleştirildi."
    { re: /^([\d.,]+) kayıt birleştirildi\.$/,
      en: "$1 records merged." },

    // "5 mükerrer satır silindi · 229 kayıt kaldı."
    { re: /^([\d.,]+) mükerrer satır silindi · ([\d.,]+) kayıt kaldı\.$/,
      en: "$1 duplicate rows removed · $2 records remaining." },

    // "Mükerrer silme geri alındı · 234 kayıt."
    { re: /^Mükerrer silme geri alındı · ([\d.,]+) kayıt\.$/,
      en: "Duplicate removal undone · $1 records." },

    // "Filtre uygulandı · 117 kayıt görüntüleniyor."
    { re: /^Filtre uygulandı · ([\d.,]+) kayıt görüntüleniyor\.$/,
      en: "Filter applied · $1 records shown." },

    // "234 kayıt · 3 PDF"
    { re: /^([\d.,]+) kayıt · ([\d.,]+) PDF$/,
      en: "$1 records · $2 PDFs" },

    // "234 kayıt · 12 sayfa · Çağrı Kaydı"
    { re: /^([\d.,]+) kayıt · ([\d.,]+) sayfa · (.+)$/,
      en: "$1 records · $2 pages · $3" },

    // "12 sayfa"
    { re: /^([\d.,]+) sayfa$/,
      en: "$1 pages" },

    // "Sıralı · 234 kayıt 4 ekibe bölündü."
    { re: /^(.+) · ([\d.,]+) kayıt (\d+) ekibe bölündü\.$/,
      en: "$1 · $2 records split across $3 teams." },

    // "İndirme başladı: foo.xlsx" / "İndirme başladı: foo · 3 dosya"
    { re: /^İndirme başladı: (.+?)( · ([\d.,]+) dosya)?$/,
      en: (m) => "Download started: " + m[1] + (m[3] ? " · " + m[3] + " files" : "") },

    // "İndirme başarısız (404)" / "ZIP indirilemedi (500)"
    { re: /^İndirme başarısız \((\d+)\)$/,
      en: "Download failed ($1)" },
    { re: /^ZIP indirilemedi \((\d+)\)$/,
      en: "ZIP download failed ($1)" },

    // "ZIP indirildi: x.zip"
    { re: /^ZIP indirildi: (.+)$/,
      en: "ZIP downloaded: $1" },

    // "(orijinal 1234) · kaydırarak tamamını görebilirsiniz"
    { re: /^\(orijinal ([\d.,]+)\) · kaydırarak tamamını görebilirsiniz$/,
      en: "(original $1) · scroll to see all" },

    // "Eşlendi · 5 sütun"
    { re: /^Eşlendi · ([\d.,]+) sütun$/,
      en: "Mapped · $1 columns" },

    // "234 kayıt"  (generic, must come last among "kayıt" patterns)
    { re: /^([\d.,]+) kayıt$/,
      en: "$1 records" },

    // ---- Output-name modal (Word / JPG) ----
    // "Çıktı Adı — Word"  /  "Çıktı Adı — JPG (ZIP)"
    { re: /^Çıktı Adı — (.+)$/,
      en: "Output name — $1" },
    // Single-file Word sub-label
    { re: /^Word çıktısının adını belirleyin \(uzantı (.+) otomatik eklenir\):$/,
      en: "Set the Word output name (extension $1 added automatically):" },
    // Single-file JPG sub-label
    { re: /^JPG arşivinin \(ZIP\) adını belirleyin \(uzantı (.+) otomatik eklenir\):$/,
      en: "Set the JPG archive (ZIP) name (extension $1 added automatically):" },
    // Multi-file sub-label
    { re: /^(\d+) dosya için çıktı adlarını belirleyin \(uzantı (.+) otomatik eklenir\):$/,
      en: "Set output names for $1 files (extension $2 added automatically):" },

    // ---- OCR / completion ----
    { re: /^✓ Tamamlandı — (.+)$/,
      en: "✓ Complete — $1" },

    // ---- Status: filter applied (alternate phrasing) ----
    { re: /^✓ Birleştirme tamamlandı · ([\d.,]+) kayıt$/,
      en: "✓ Merge complete · $1 records" },

    // ---- Team / factor placeholders ("Ekip 1", "Ekip 2", "Faktör 1") ----
    { re: /^Ekip (\d+)$/,
      en: "Team $1" },
    { re: /^Faktör (\d+)$/,
      en: "Factor $1" },

    // ---- Standalone "1 telefon" / "5 telefon" (used inside <strong>...</strong>) ----
    { re: /^([\d.,]+) telefon$/,
      en: function (m) { return m[1] + (m[1] === "1" ? " phone" : " phones"); } },

    // ---- Safety findings: text after <strong>/JavaScript</strong>
    //      Comes as "(3 adet) — JavaScript çalıştırılabilir kodu"
    { re: /^\((\d+) adet\) — (.+)$/,
      en: function (m) {
        // Try to translate the description via the static dictionary;
        // fall back to the original Turkish text if not registered.
        const desc = STRINGS[m[2]] !== undefined ? STRINGS[m[2]] : m[2];
        return "(" + m[1] + " found) — " + desc;
      } },

    // ---- Generic "X adet" if it ever appears standalone ----
    { re: /^([\d.,]+) adet$/,
      en: "$1 found" },

    // ---- HTTP error wrappers: "Filtre uygulanamadı (404)", "Dağıtım başarısız (500)" ----
    { re: /^Başlatma hatası \((\d+)\)$/,
      en: "Start failed ($1)" },
    { re: /^Analiz başarısız \((\d+)\)$/,
      en: "Analysis failed ($1)" },
    { re: /^Önizleme alınamadı \((\d+)\)$/,
      en: "Preview failed ($1)" },
    { re: /^Filtre uygulanamadı \((\d+)\)$/,
      en: "Filter failed ($1)" },
    { re: /^Dağıtım başarısız \((\d+)\)$/,
      en: "Distribution failed ($1)" },
    { re: /^İşlem başarısız \((\d+)\)$/,
      en: "Operation failed ($1)" },
    { re: /^İlerleme alınamadı \((\d+)\)$/,
      en: "Progress unavailable ($1)" },

    // ---- "X PDF seçildi" / "X PDF işlendi" (numeric prefixes) ----
    { re: /^([\d.,]+) PDF seçildi$/,
      en: function (m) { return m[1] + (m[1] === "1" ? " PDF selected" : " PDFs selected"); } },

    // ---- "Şu an: %85" — current value of percent total ----
    { re: /^.*Şu an: %([\d.,]+)$/,
      en: function (m) {
        const head = m[0].slice(0, m[0].lastIndexOf("Şu an:"));
        const enHead = STRINGS[head.trim()] !== undefined
          ? STRINGS[head.trim()]
          : head.trim();
        return enHead + " Currently: " + m[1] + "%";
      } },

    // ---- " ekibe bölündü" tail (split text node) ----
    { re: /^([\d.,]+) ekibe bölündü\.$/,
      en: function (m) { return "split across " + m[1] + " teams."; } },

    // ---- "Sütun A" / "Sütun B" placeholders ----
    { re: /^Sütun (.+)$/,
      en: "Column $1" },

    // ---- Phase label + filename ("Excel yazılıyor · foo.pdf") ----
    { re: /^(Başlatılıyor|İşleniyor|Excel yazılıyor|Word'e dönüştürülüyor|Sayfalar render ediliyor|Çıktı yazılıyor|OCR okunuyor|Tamamlandı|Hazırlanıyor) · (.+)$/,
      en: function (m) {
        const phaseMap = {
          "Başlatılıyor": "Starting",
          "İşleniyor": "Processing",
          "Excel yazılıyor": "Writing Excel",
          "Word'e dönüştürülüyor": "Converting to Word",
          "Sayfalar render ediliyor": "Rendering pages",
          "Çıktı yazılıyor": "Writing output",
          "OCR okunuyor": "Running OCR",
          "Tamamlandı": "Complete",
          "Hazırlanıyor": "Preparing",
        };
        return phaseMap[m[1]] + " · " + m[2];
      } },

    // ---- Phase label + counter ("Excel yazılıyor — 5/10 (%50)") ----
    { re: /^(Başlatılıyor|İşleniyor|Excel yazılıyor|Word'e dönüştürülüyor|Sayfalar render ediliyor|Çıktı yazılıyor|OCR okunuyor|Tamamlandı|Hazırlanıyor) — (\d+)\/(\d+) \(%(\d+)\)$/,
      en: function (m) {
        const phaseMap = {
          "Başlatılıyor": "Starting",
          "İşleniyor": "Processing",
          "Excel yazılıyor": "Writing Excel",
          "Word'e dönüştürülüyor": "Converting to Word",
          "Sayfalar render ediliyor": "Rendering pages",
          "Çıktı yazılıyor": "Writing output",
          "OCR okunuyor": "Running OCR",
          "Tamamlandı": "Complete",
          "Hazırlanıyor": "Preparing",
        };
        return phaseMap[m[1]] + " — " + m[2] + "/" + m[3] + " (" + m[4] + "%)";
      } },

    // ---- Phase label with trailing dots ("Excel yazılıyor...") ----
    { re: /^(Başlatılıyor|İşleniyor|Excel yazılıyor|Word'e dönüştürülüyor|Sayfalar render ediliyor|Çıktı yazılıyor|OCR okunuyor|Tamamlandı|Hazırlanıyor)\.\.\.$/,
      en: function (m) {
        const phaseMap = {
          "Başlatılıyor": "Starting",
          "İşleniyor": "Processing",
          "Excel yazılıyor": "Writing Excel",
          "Word'e dönüştürülüyor": "Converting to Word",
          "Sayfalar render ediliyor": "Rendering pages",
          "Çıktı yazılıyor": "Writing output",
          "OCR okunuyor": "Running OCR",
          "Tamamlandı": "Complete",
          "Hazırlanıyor": "Preparing",
        };
        return phaseMap[m[1]] + "...";
      } },

    // ---- Settings: total percentage indicator ("Toplam: 100 %", "Toplam: 0 %") ----
    { re: /^Toplam: (-?\d+(?:[.,]\d+)?) ?%$/,
      en: "Total: $1%" },
    { re: /^Toplam (-?\d+(?:[.,]\d+)?) ?%$/,
      en: "Total $1%" },

    // ---- Result: "487 satır · kaydırarak tamamını görebilirsiniz"
    { re: /^([\d.,]+) satır · kaydırarak tamamını görebilirsiniz$/,
      en: "$1 rows · scroll to see all" },

    // ---- Result: "487 satır" / "5 satır" generic ----
    { re: /^([\d.,]+) satır$/,
      en: "$1 rows" },

    // ---- Security modal: Turkish month names → English ----
    // "25 Nisan 2026"
    { re: /^(\d{1,2}) (Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık) (\d{4})$/,
      en: function (m) {
        const months = {
          "Ocak": "January", "Şubat": "February", "Mart": "March",
          "Nisan": "April", "Mayıs": "May", "Haziran": "June",
          "Temmuz": "July", "Ağustos": "August", "Eylül": "September",
          "Ekim": "October", "Kasım": "November", "Aralık": "December",
        };
        return months[m[2]] + " " + m[1] + ", " + m[3];
      } },

    // ---- Security: "31.248 dosya tarandı — Tehdit yok" ----
    { re: /^([\d.,]+) dosya tarandı — Tehdit yok$/,
      en: "$1 files scanned — no threats" },
    // "31.248 dosya temiz"
    { re: /^([\d.,]+) dosya temiz$/,
      en: "$1 files clean" },

    // ---- Security: "Size: 447.87 MB · 32.602 dosya" / standalone "32.602 dosya" ----
    { re: /^([\d.,]+) dosya$/,
      en: "$1 files" },

    // ---- VirusTotal banner: "VirusTotal: 0 detection · MetaDefender: 0 / 21 · Kaspersky (lokal): 31.248 dosya temiz · Hiçbir motor zararlı bulmadı." ----
    { re: /^VirusTotal: (\d+) detection · MetaDefender: (\d+) ?\/ ?(\d+) · Kaspersky \(lokal\): ([\d.,]+) dosya temiz · Hiçbir motor zararlı bulmadı\.$/,
      en: "VirusTotal: $1 detection · MetaDefender: $2 / $3 · Kaspersky (local): $4 files clean · No engine flagged anything." },
  ];

  // ========================================================================
  // 2b. Modal HTML blocks (full innerHTML replacement, EN only)
  // ------------------------------------------------------------------------
  // Selectors → { en: "<full HTML>" }. Original TR HTML is snapshotted at
  // first switch so TR restoration is lossless. Keep in sync with the
  // Turkish HTML in templates/index.html if you change either side.
  // ========================================================================
  const HTML_BLOCKS = {
    // -------------------- Help modal (📖 Kullanım Kılavuzu) --------------
    "#helpModalBack .help-content": {
      en: `
        <h4 id="h-baslangic">🚀 Getting started</h4>
        <p>This tool converts PDFs to <strong>Excel, Word or JPG</strong>. You can merge multiple PDFs into a single Excel, remove duplicate records, filter by column and distribute the result to teams. Everything runs in-house — files never leave the network.</p>
        <ul>
          <li><strong>Left panel:</strong> pick a file and choose the format.</li>
          <li><strong>Right panel:</strong> preview, results, full row table and distribution open here.</li>
          <li><strong>Top:</strong> 📖 Help, 📜 History, 🔄 Reset, ⚙ Settings.</li>
        </ul>

        <h4 id="h-tek">📄 Single PDF conversion</h4>
        <ul>
          <li>Drag a PDF onto the drop area or click to pick one.</li>
          <li>Pick the format: <code>Excel</code>, <code>Word</code> or <code>JPG</code>.</li>
          <li>For <strong>Word/JPG</strong> a name dialog appears for the output filename.</li>
          <li>Press <strong>Convert</strong> — a percentage progress bar appears, the file downloads when done.</li>
        </ul>

        <h4 id="h-coklu">📂 Multiple PDFs (merge)</h4>
        <ul>
          <li>Picking multiple PDFs auto-switches to <strong>multi mode</strong>.</li>
          <li>With <strong>Excel</strong> selected, all PDFs are merged into <strong>one Excel</strong>; the row number starts at 1 and continues across files.</li>
          <li>With <strong>Word</strong> or <strong>JPG</strong>, each PDF is converted separately and bundled into a <strong>single ZIP</strong>.</li>
          <li>If a PDF is not a call-log, it is marked "incompatible"; you can include it via <strong>Map columns</strong> or exclude it with <strong>Skip</strong>.</li>
        </ul>

        <h4 id="h-mukerrer">🟧 Duplicate phone removal</h4>
        <p>If "<strong>X duplicate phones</strong>" appears above the table after merge, press <strong>Deduplicate</strong>. Among rows sharing a phone number, the first occurrence is kept and the rest removed. Press <strong>Undo</strong> to reverse.</p>

        <h4 id="h-filtre">🔍 Column-based filtering</h4>
        <ul>
          <li>Press <strong>🔍 Filter</strong> above the table.</li>
          <li>Pick a column (e.g. <code>City</code>, <code>Status</code>, <code>Age</code>).</li>
          <li>The dropdown lists every distinct value in that column with its count; pick what you want and press <strong>Apply</strong>.</li>
          <li>Empty cells are listed as <code>(empty)</code>.</li>
          <li>Filters can be added on multiple columns (combined with AND).</li>
          <li>Use <strong>×</strong> on the blue chip to remove one, or <strong>Clear all</strong> to remove all.</li>
        </ul>

        <h4 id="h-dagitim">👥 Team distribution</h4>
        <p>Press <strong>Distribute to teams</strong> on the result card. Add teams and pick a distribution type:</p>
        <ul>
          <li><strong>Sequential:</strong> 1–100 → Team 1, 101–200 → Team 2 (contiguous blocks).</li>
          <li><strong>Round-robin:</strong> 1→T1, 2→T2, 3→T3, 4→T1… each team's rows are interleaved.</li>
          <li><strong>Custom weights:</strong> two modes from ⚙ Settings:
            <ul>
              <li><em>Direct ratio:</em> enter each team's percentage (must total 100%).</li>
              <li><em>Score-based:</em> with predefined factors (e.g. Sales 50%, Experience 30%, Volume 20%) you score each team; distribution follows the team's total score.</li>
            </ul>
          </li>
        </ul>
        <p>After distribution use the team tabs to review each team's rows and press <strong>Download all as ZIP</strong> to download every team's Excel as separate files inside one ZIP.</p>

        <h4 id="h-ocr">📸 Scanned (image) PDF — OCR</h4>
        <p>If the PDF has no text layer it is detected automatically and a red warning appears. Press <strong>🔍 Convert to selected format</strong>:</p>
        <ul>
          <li>With <strong>Word</strong> or <strong>Excel</strong> selected, OCR runs (reads text page by page).</li>
          <li>With <strong>JPG</strong> selected OCR is not needed — pages are saved as images directly.</li>
          <li>The first OCR call may take 1–2 minutes (the AI model loads). Subsequent calls are fast.</li>
        </ul>

        <h4 id="h-mobil">📱 Mobile / Tablet usage</h4>
        <p>Make sure the device is on the same Wi-Fi as the PC running the server. From the browser open <code>http://&lt;LAN-IP&gt;:8000</code> (the LAN address is shown in the server start screen).</p>
        <ul>
          <li><strong>Add to home screen:</strong> on iPhone Safari → Share → "Add to Home Screen". On Android Chrome → ⋮ → "Add to Home screen". The app opens with its own icon and no browser chrome.</li>
          <li><strong>Multiple selection:</strong> on mobile, to pick multiple PDFs first put them into a folder in the phone's "Files" app.</li>
        </ul>

        <h4 id="h-https">🔐 Security warnings (HTTPS / Certificate / Download)</h4>
        <p>The server uses a self-signed HTTPS certificate. Browsers may warn on first access — this is <strong>normal</strong>; traffic is still encrypted.</p>
        <ul>
          <li><strong>Chrome / Edge:</strong> "Your connection is not private" → <em>Advanced</em> → <em>Proceed anyway</em></li>
          <li><strong>Firefox:</strong> "Warning: Potential Security Risk" → <em>Advanced</em> → <em>Accept the risk and continue</em></li>
          <li><strong>Safari (iOS/Mac):</strong> "This Connection Is Not Private" → <em>Show Details</em> → <em>visit this website</em></li>
          <li><strong>Android Chrome:</strong> same — <em>Advanced</em> → <em>Proceed anyway</em></li>
        </ul>
        <p>Once accepted the browser remembers it — you won't see the warning again.</p>
        <p><strong>📥 Download warning:</strong> on mobile you may rarely see "couldn't be downloaded securely". Press <strong>"Keep / Download anyway"</strong> — the file comes from your own server, it's safe.</p>
        <p><strong>📱 Add to home screen (PWA):</strong></p>
        <ul>
          <li><strong>iOS Safari:</strong> Share ↗ → <em>Add to Home Screen</em></li>
          <li><strong>Android Chrome:</strong> ⋮ → <em>Add to Home Screen</em> or <em>Install app</em></li>
          <li>The app opens with its icon, no browser chrome visible</li>
        </ul>

        <h4 id="h-sss">❓ Frequently asked questions</h4>
        <p><strong>The page says "cannot be done".</strong> The PDF is scanned (image-based); use the OCR button.</p>
        <p><strong>Cells are misaligned in Excel.</strong> This tool recognises call-log PDFs and uses a dedicated parser — there is no drift. If you see issues with other PDF types, please report it via Help.</p>
        <p><strong>What happens if the server crashes?</strong> Ongoing jobs are lost (they live in RAM). Half-finished files are cleaned up automatically later.</p>
        <p><strong>Keyboard shortcuts:</strong> <kbd>Ctrl</kbd>+<kbd>F5</kbd> reloads the page (bypasses cache).</p>
        <p><strong>File size limit:</strong> default 2 GB. The server admin can change it via the <code>MAX_UPLOAD_MB</code> environment variable.</p>
      `,
    },

    // -------------------- Legal acceptance gate (first launch) -----------
    "#firstLegalModal .help-content": {
      en: `
        <p style="background:#fef2f2; border-left:3px solid #dc2626; padding:10px 12px; border-radius:6px; color:#7f1d1d; font-weight:600">
          ⚠ <strong>Important:</strong> Any data loss, damage or service interruption arising from the use of this software is the sole responsibility of the user / organisation. Backups are mandatory before use for any important data.
        </p>

        <h4>📜 License</h4>
        <p>Copyright © 2026 <strong>Orhan Engin Okay</strong>. All rights reserved.<br>
        This software is distributed under the <a href="https://www.gnu.org/licenses/agpl-3.0.html" target="_blank" rel="noopener" style="color:#2F5496"><strong>GNU AGPL-3.0</strong></a> license.</p>

        <h4>❌ Disclaimer of warranty</h4>
        <p>The software is provided <strong>"AS IS"</strong>. The author makes no warranty, express or implied.</p>

        <h4>⚠️ Limitation of liability</h4>
        <p><strong>Data processing, transfer and any potential losses are entirely the user's responsibility.</strong>
        The author is in no way liable for any data loss, lost revenue, business interruption, indirect or consequential damages arising from the use of the software.</p>

        <h4>🔒 Data privacy</h4>
        <p>The software runs locally; uploaded files are not sent to the internet. Temporary working files are cleaned up automatically. For organisations that process personal data, obligations under <strong>GDPR / equivalent privacy laws</strong> belong to the data controller.</p>

        <h4>🚫 Restrictions</h4>
        <ul>
          <li>Copying / redistribution of the software is subject to AGPL-3.0 terms</li>
          <li>Reverse engineering requires the author's permission</li>
          <li>Use of the brand name / logos for other purposes is prohibited</li>
        </ul>

        <h4>⚖️ Governing law</h4>
        <p>The laws of the Republic of Türkiye apply. Disputes are subject to the jurisdiction of the courts of Ankara. For use outside Türkiye, local copyright laws and international treaties (Berne, TRIPS) apply.</p>

        <p style="text-align:center; margin-top:14px; font-size:12px; color:#64748b">
          See <strong>LICENSE</strong> for the full text, or open the <strong>⚖️ Legal</strong> button at any time.
        </p>
      `,
    },

    // -------------------- Legal modal (full, from header button) ---------
    "#legalModalBack .help-content": {
      en: `
        <div class="sec-warn" style="background:#fef2f2; border-left-color:#dc2626; color:#7f1d1d">
          <strong>⚠ Data responsibility:</strong>
          Any data loss, damage or service interruption arising from the use of this software is the sole responsibility of the user / organisation. Backups are mandatory before use for any important data.
        </div>

        <h4>📜 Copyright</h4>
        <p>Copyright © 2026 <strong>Orhan Engin Okay</strong>. All rights reserved.</p>
        <p>This software is distributed under the <a href="https://www.gnu.org/licenses/agpl-3.0.html" target="_blank" rel="noopener" style="color:#2F5496">GNU AGPL-3.0</a> license.</p>
        <p>This software is protected under international copyright law (Berne Convention, TRIPS Agreement) and the laws of the Republic of Türkiye.</p>

        <h4>🔒 Usage rights</h4>
        <p>The software is provided for authorised in-house use.</p>

        <h4>🚫 Restrictions</h4>
        <p>Without the author's express written permission the following are prohibited:</p>
        <ul>
          <li>Copying, redistribution or sale of the software</li>
          <li>Modification of the source code (modification, derivative works)</li>
          <li>Reverse engineering (decompile, disassemble)</li>
          <li>Integration of the software into another product</li>
          <li>Use of brand name, names or logos for other purposes</li>
        </ul>

        <h4>❌ Disclaimer of warranty</h4>
        <p>The software is provided <strong>"AS IS"</strong> and <strong>"AS AVAILABLE"</strong>. The author makes no warranty of any kind, express or implied (including fitness for a particular purpose, merchantability, uninterrupted operation, etc.).</p>

        <h4>⚠️ Limitation of liability</h4>
        <p>The author is <strong>NOT LIABLE IN ANY WAY</strong> for any data loss, lost revenue, business interruption, indirect / special / consequential / punitive damages arising from the use, inability to use, or operation of the software.</p>
        <p style="background:#fef2f2; padding:8px 10px; border-radius:6px; color:#7f1d1d">
          <strong>Data processing, transfer and any potential losses are entirely the user's responsibility.</strong>
        </p>

        <h4>🛡 Data privacy &amp; GDPR</h4>
        <p>The software runs locally; uploaded files are not sent to the internet. Temporary working files are cleaned up automatically. For organisations that process personal data, obligations under <strong>applicable data-protection laws (GDPR / KVKK / similar)</strong> belong to the data controller / user organisation.</p>

        <h4>📦 Third-party libraries</h4>
        <p>The software bundles independent libraries distributed under their own open-source licenses: FastAPI, PyMuPDF, EasyOCR, openpyxl, pdf2docx, pdfplumber. The license text for each library is included in its own package.</p>

        <h4>⚖️ Governing law</h4>
        <p>This agreement is primarily governed by the laws of the <strong>Republic of Türkiye</strong>. Disputes are subject to the jurisdiction of the <strong>Ankara Courts and Enforcement Offices</strong>. For use outside Türkiye, local copyright laws and international treaties (Berne Convention, TRIPS) apply.</p>

        <h4>✅ Effect &amp; acceptance</h4>
        <p>By installing, running or using the software you are deemed to have read, understood and accepted all terms of this agreement.</p>

        <p style="margin-top:14px; font-size:11px; color:#94a3b8; text-align:center">
          Full text (TR + EN): <code>LICENSE.txt</code> · Version 1.0 · April 2026
        </p>
      `,
    },

    // -------------------- Security modal --------------------------------
    "#securityModalBack .sec-content": {
      en: `
        <h4>📋 Scan details</h4>
        <ul>
          <li><strong>Scan date:</strong> April 25, 2026</li>
          <li><strong>VirusTotal (online):</strong> 0 detection — No security vendors flagged this file</li>
          <li><strong>MetaDefender / OPSWAT (online):</strong> 0 / 21 — No Threats Detected</li>
          <li><strong>Kaspersky (local enterprise):</strong> 31,248 files scanned — no threats</li>
          <li><strong>Vulnerability (CVE) scan:</strong> No Vulnerabilities Found</li>
          <li><strong>File:</strong> Admin_PDF_Toolkit_Portable.zip</li>
          <li><strong>Size:</strong> 447.87 MB · 32,602 files</li>
        </ul>

        <div class="sec-hash">
          <div class="lbl-row">
            <span>SHA-256 Hash</span>
            <button type="button" class="copy" data-copy="5ea0fe8e6213a24291a8399b39d964c7eed11c66d163c4c0e01c4883776438d1">Copy</button>
          </div>
          5ea0fe8e6213a24291a8399b39d964c7eed11c66d163c4c0e01c4883776438d1
        </div>

        <div class="sec-hash">
          <div class="lbl-row">
            <span>SHA-1</span>
            <button type="button" class="copy" data-copy="f3fe7eac2e3bfebe5487e8e7270b9c751e69e477">Copy</button>
          </div>
          f3fe7eac2e3bfebe5487e8e7270b9c751e69e477
        </div>

        <div class="sec-hash">
          <div class="lbl-row">
            <span>MD5</span>
            <button type="button" class="copy" data-copy="307d962e079f5a00e8fd3ada4ec59e37">Copy</button>
          </div>
          307d962e079f5a00e8fd3ada4ec59e37
        </div>

        <p style="margin-top:10px; display:flex; flex-wrap:wrap; gap:8px">
          <a class="sec-link" href="https://www.virustotal.com/gui/file/5ea0fe8e6213a24291a8399b39d964c7eed11c66d163c4c0e01c4883776438d1/detection" target="_blank" rel="noopener">View on VirusTotal ↗</a>
          <a class="sec-link" style="background:#047857" href="https://metadefender.com/threat-intelligence/search?type=hash&amp;query=5ea0fe8e6213a24291a8399b39d964c7eed11c66d163c4c0e01c4883776438d1" target="_blank" rel="noopener">View on MetaDefender ↗</a>
        </p>

        <h4>🟡 About 1 file (false-positive explanation)</h4>
        <p>Out of the package's 32,602 files, only <strong>1 file</strong> was flagged as "suspicious" by <strong>1</strong> of 65 antivirus vendors. That file is open source and comes from the official <strong>PyPI</strong> (Python Package Index) package; the same file is found in millions of Python projects. This is a classic "false positive" — a single antivirus vendor's heuristic analysis raising a wrong alert.</p>

        <table class="vt-table">
          <thead>
            <tr><th>File</th><th>Detection</th><th>Package</th></tr>
          </thead>
          <tbody>
            <tr>
              <td class="path">__mypyc.cp313-win_amd64.pyd</td>
              <td class="detect">1 / 65</td>
              <td>mypyc — standard output of the Python type-checker compiler</td>
            </tr>
          </tbody>
        </table>

        <div class="sec-warn">
          <strong>Note for IT department:</strong>
          The package was verified by <strong>three independent systems</strong>: VirusTotal (0 detection), MetaDefender (0/21) and enterprise Kaspersky (31,248 files clean). No engine flagged anything malicious. Inside the package, only 1 file (mypyc.pyd) raised a heuristic warning from a single vendor; this is the standard component of the Python type-checker library from PyPI. For whitelisting requests, you can share the SHA-256 hash above.
        </div>

        <h4>🔒 Security design of this application</h4>
        <ul>
          <li><strong>Runs fully offline.</strong> Server runs on the local machine, does not send files to the internet.</li>
          <li><strong>Uploaded PDFs are removed from disk</strong> — cleared automatically seconds after the download completes; periodic cleanup removes anything older than 30 minutes.</li>
          <li><strong>No admin rights required.</strong> Runs with portable Python.</li>
          <li><strong>Open-source libraries:</strong> FastAPI, PyMuPDF, EasyOCR, openpyxl, pdf2docx — all from PyPI, all open source.</li>
          <li><strong>History log:</strong> stored locally in a SQLite database, never sent to any external server.</li>
          <li><strong>Author:</strong> Orhan Engin Okay · AGPL-3.0 open source.</li>
        </ul>

        <h4>✅ Verify it yourself</h4>
        <p>Don't take this report on faith — verify it yourself:</p>
        <ul>
          <li>Upload the ZIP file to <a href="https://www.virustotal.com" target="_blank" rel="noopener">virustotal.com</a></li>
          <li>Verify the SHA-256 hash above in PowerShell:
            <br><code style="font-size:11px">Get-FileHash file.zip -Algorithm SHA256</code></li>
          <li>The results should match the values on this page exactly</li>
        </ul>
      `,
    },
  };

  // ========================================================================
  // 3. Internal state
  // ========================================================================
  const STORAGE_KEY = "ht_pdf_lang";
  const SUPPORTED = ["tr", "en"];
  const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "CODE", "PRE", "KBD", "TEXTAREA"]);
  const ATTRS = ["title", "placeholder", "aria-label", "value"];

  // Snapshot store — orijinal Türkçe değerleri tutar
  const textSnapshots = new WeakMap();   // textNode → original string
  const attrSnapshots = new WeakMap();   // element → { attr → original }

  let currentLang = "tr";
  let observer = null;
  let applying = false;   // observer-loop koruması

  // ========================================================================
  // 4. Translation helpers
  // ========================================================================
  function normalize(s) {
    return (s || "").replace(/\s+/g, " ").trim();
  }

  function translateOne(raw) {
    const s = normalize(raw);
    if (!s) return null;

    // 1) exact match
    if (Object.prototype.hasOwnProperty.call(STRINGS, s)) {
      return raw.replace(s, STRINGS[s]);
    }

    // 2) regex patterns
    for (const p of PATTERNS) {
      const m = s.match(p.re);
      if (m) {
        let out;
        if (typeof p.en === "function") {
          out = p.en(m);
        } else {
          out = p.en;
          for (let i = 1; i < m.length; i++) {
            out = out.replaceAll("$" + i, m[i] != null ? m[i] : "");
          }
        }
        return raw.replace(s, out);
      }
    }
    return null;
  }

  // ========================================================================
  // 5. DOM walker — applies a language to a subtree
  // ========================================================================
  function shouldSkipElement(el) {
    if (!el || !el.closest) return false;
    return el.closest("[data-i18n-skip]") != null;
  }

  function applyToTextNode(node, lang) {
    const parent = node.parentNode;
    if (!parent) return;
    if (SKIP_TAGS.has(parent.tagName)) return;
    if (shouldSkipElement(parent)) return;
    if (!node.nodeValue || !node.nodeValue.trim()) return;

    if (!textSnapshots.has(node)) {
      textSnapshots.set(node, node.nodeValue);
    }
    const original = textSnapshots.get(node);

    if (lang === "tr") {
      if (node.nodeValue !== original) node.nodeValue = original;
    } else {
      const out = translateOne(original);
      const target = out !== null ? out : original;
      if (node.nodeValue !== target) node.nodeValue = target;
    }
  }

  function applyToElementAttrs(el, lang) {
    if (shouldSkipElement(el)) return;
    let store = attrSnapshots.get(el);
    for (const attr of ATTRS) {
      if (!el.hasAttribute(attr)) continue;
      if (!store) {
        store = {};
        attrSnapshots.set(el, store);
      }
      if (!(attr in store)) store[attr] = el.getAttribute(attr);
      const original = store[attr];
      if (lang === "tr") {
        if (el.getAttribute(attr) !== original) el.setAttribute(attr, original);
      } else {
        const out = translateOne(original);
        const target = out !== null ? out : original;
        if (el.getAttribute(attr) !== target) el.setAttribute(attr, target);
      }
    }
  }

  function walkSubtree(root, lang) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) {
      applyToTextNode(root, lang);
      return;
    }
    if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE) return;

    // Element attributes
    if (root.nodeType === Node.ELEMENT_NODE) {
      applyToElementAttrs(root, lang);
    }

    // Walk text nodes
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) applyToTextNode(n, lang);

    // Walk attributes on descendants
    const els = root.querySelectorAll
      ? root.querySelectorAll("[title], [placeholder], [aria-label]")
      : [];
    for (const el of els) applyToElementAttrs(el, lang);
  }

  function applyLanguageToWholePage(lang) {
    applying = true;
    try {
      walkSubtree(document.body, lang);
    } finally {
      applying = false;
    }
  }

  // ========================================================================
  // 6. MutationObserver — catches runtime DOM/text changes
  // ========================================================================
  // When the page mutates a text/attribute from the OUTSIDE (i.e. user JS
  // sets el.textContent = "Geri Al"), our snapshot of the original Turkish
  // value goes stale. We need to detect that and update the snapshot to the
  // new TR base, otherwise the next translation pass keeps re-applying the
  // OLD translation forever.
  function refreshTextSnapshotIfStale(node) {
    if (!textSnapshots.has(node)) return;
    const stored = textSnapshots.get(node);
    const current = node.nodeValue;
    if (current === stored) return;
    // Is `current` actually the EN translation of `stored`? Then it's our
    // own writeback — leave the snapshot alone.
    const expectedEn = translateOne(stored);
    if (expectedEn !== null && current === expectedEn) return;
    // Otherwise: external code wrote a new TR value. Adopt it as the new base.
    textSnapshots.set(node, current);
  }

  function refreshAttrSnapshotIfStale(el, attr) {
    const store = attrSnapshots.get(el);
    if (!store || !(attr in store)) return;
    const stored = store[attr];
    const current = el.getAttribute(attr);
    if (current === null || current === stored) return;
    const expectedEn = translateOne(stored);
    if (expectedEn !== null && current === expectedEn) return;
    store[attr] = current;
  }

  function setupObserver() {
    if (observer) observer.disconnect();
    observer = new MutationObserver((mutations) => {
      if (applying) return;
      applying = true;
      try {
        for (const m of mutations) {
          if (m.type === "characterData") {
            refreshTextSnapshotIfStale(m.target);
            applyToTextNode(m.target, currentLang);
          } else if (m.type === "childList") {
            for (const node of m.addedNodes) {
              walkSubtree(node, currentLang);
            }
          } else if (m.type === "attributes") {
            if (m.attributeName) refreshAttrSnapshotIfStale(m.target, m.attributeName);
            applyToElementAttrs(m.target, currentLang);
          }
        }
      } finally {
        applying = false;
      }
    });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ATTRS,
    });
  }

  // ========================================================================
  // 6b. Modal-level HTML replacement
  // ------------------------------------------------------------------------
  // For long Turkish paragraphs that the text-walker cannot translate cleanly
  // (because <strong> / <code> nests split text into many nodes), we just
  // swap the entire innerHTML of a container element. The original HTML is
  // snapshotted so switching back to TR restores it.
  // ========================================================================
  const HTML_BLOCK_SNAPSHOTS = new Map();   // selector → original innerHTML

  function applyHtmlBlocks(lang) {
    for (const [selector, htmlByLang] of Object.entries(HTML_BLOCKS)) {
      const el = document.querySelector(selector);
      if (!el) continue;
      if (!HTML_BLOCK_SNAPSHOTS.has(selector)) {
        HTML_BLOCK_SNAPSHOTS.set(selector, el.innerHTML);
      }
      const original = HTML_BLOCK_SNAPSHOTS.get(selector);
      const target = lang === "en" && htmlByLang.en ? htmlByLang.en : original;
      // Avoid pointless DOM rewrites
      if (el.innerHTML !== target) {
        applying = true;
        try {
          el.innerHTML = target;
        } finally {
          applying = false;
        }
      }
    }
  }

  // ========================================================================
  // 7. Public API
  // ========================================================================
  function setLang(lang) {
    if (!SUPPORTED.includes(lang)) lang = "tr";
    currentLang = lang;
    document.documentElement.setAttribute("lang", lang);
    applyHtmlBlocks(lang);                  // big modal blocks first
    applyLanguageToWholePage(lang);          // then per-node translation
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch (e) { /* private mode */ }
    const btn = document.getElementById("langBtn");
    if (btn) btn.textContent = lang === "en" ? "🌐 EN" : "🌐 TR";
    document.dispatchEvent(new CustomEvent("i18n:changed", { detail: { lang } }));
  }

  function detectInitial() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && SUPPORTED.includes(saved)) return saved;
    } catch (e) { /* ignore */ }
    const nav = (navigator.language || "tr").toLowerCase();
    return nav.startsWith("en") ? "en" : "tr";
  }

  window.HTI18N = {
    get lang() { return currentLang; },
    set: setLang,
    t(text) {
      if (currentLang === "tr") return text;
      const out = translateOne(text);
      return out !== null ? out : text;
    },
    addStrings(map) {
      Object.assign(STRINGS, map);
      if (currentLang !== "tr") applyLanguageToWholePage(currentLang);
    },
    addPatterns(arr) {
      PATTERNS.unshift(...arr);
      if (currentLang !== "tr") applyLanguageToWholePage(currentLang);
    },
  };

  // ========================================================================
  // 8. Boot
  // ========================================================================
  function boot() {
    setupObserver();
    const initial = detectInitial();
    if (initial !== "tr") {
      setLang(initial);
    } else {
      const btn = document.getElementById("langBtn");
      if (btn) btn.textContent = "🌐 TR";
    }
    const btn = document.getElementById("langBtn");
    if (btn) {
      btn.addEventListener("click", () => {
        setLang(currentLang === "tr" ? "en" : "tr");
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
