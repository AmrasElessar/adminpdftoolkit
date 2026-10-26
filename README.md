<div align="center">

<img src="web/public/icon.svg" width="112" alt="Admin PDF Toolkit logo" />

# Admin PDF Toolkit

**Çevrimdışı, LAN içi, açık kaynak PDF uygulaması — Acrobat seviyesinde düzenleme, KVKK uyumlu**

*PDF düzenle · dönüştür · OCR · dijital imza · formlar · KVKK karartma · PDF/A · karşılaştırma — dosyalar makineden çıkmaz*
*Offline, LAN-first, open-source PDF application — edit, convert, OCR, sign, forms, redact, archive. Files never leave the machine.*

🌐 **TR · EN** — Bu README iki dillidir / This README is bilingual (English collapsibles below each section)

</div>

<div align="center">

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0.0--dev-orange)](CHANGELOG.md)
[![CI](https://github.com/AmrasElessar/adminpdftoolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/AmrasElessar/adminpdftoolkit/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AmrasElessar/adminpdftoolkit/actions/workflows/codeql.yml/badge.svg)](https://github.com/AmrasElessar/adminpdftoolkit/actions/workflows/codeql.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Svelte 5](https://img.shields.io/badge/Svelte-5-FF3E00?logo=svelte&logoColor=white)](https://svelte.dev/)
[![PyMuPDF](https://img.shields.io/badge/PyMuPDF-EB5424)](https://pymupdf.readthedocs.io/)
[![WCAG 2.1 AA](https://img.shields.io/badge/WCAG_2.1-AA-success)](STANDARDS.md)
[![PDF/A · PAdES · PDF/UA](https://img.shields.io/badge/ISO-PDF%2FA_%C2%B7_PAdES_%C2%B7_PDF%2FUA-informational)](STANDARDS.md)
[![KVKK](https://img.shields.io/badge/KVKK-uyumlu_%2F_compliant-success)](#-kvkk--personal-data)
[![D Brand](https://img.shields.io/badge/D_Brand-family-purple)](#-d-brand-ailesi--d-brand-family)

</div>

<div align="center">

### 🛡️ Güvenlik / Security

[![VT Launcher exe](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fgithub.com%2FAmrasElessar%2Fadminpdftoolkit%2Freleases%2Flatest%2Fdownload%2Fvirustotal.json&query=%24.exe&label=VT%20Launcher%20exe&logo=virustotal&logoColor=white&color=2f6db3&cacheSeconds=3600)](https://github.com/AmrasElessar/adminpdftoolkit/releases/latest) [![VT Windows](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fgithub.com%2FAmrasElessar%2Fadminpdftoolkit%2Freleases%2Flatest%2Fdownload%2Fvirustotal.json&query=%24.windows&label=VT%20Windows&logo=virustotal&logoColor=white&color=2f6db3&cacheSeconds=3600)](https://github.com/AmrasElessar/adminpdftoolkit/releases/latest) [![VT macOS](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fgithub.com%2FAmrasElessar%2Fadminpdftoolkit%2Freleases%2Flatest%2Fdownload%2Fvirustotal.json&query=%24.macos&label=VT%20macOS&logo=virustotal&logoColor=white&color=2f6db3&cacheSeconds=3600)](https://github.com/AmrasElessar/adminpdftoolkit/releases/latest) [![VT Linux](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fgithub.com%2FAmrasElessar%2Fadminpdftoolkit%2Freleases%2Flatest%2Fdownload%2Fvirustotal.json&query=%24.linux&label=VT%20Linux&logo=virustotal&logoColor=white&color=2f6db3&cacheSeconds=3600)](https://github.com/AmrasElessar/adminpdftoolkit/releases/latest)

[![HTTPS](https://img.shields.io/badge/HTTPS-local_CA_·_TLS_1.2%2B-2ea44f)](SECURITY.md) [![Network](https://img.shields.io/badge/network-LAN_only-2ea44f)](SECURITY.md) [![Updates](https://img.shields.io/badge/updates-Ed25519_signed-2f6db3)](SECURITY.md) [![Bundles](https://img.shields.io/badge/bundled_tools-SHA--256_verified-2f6db3)](THIRD_PARTY_LICENSES.md) [![CSP](https://img.shields.io/badge/CSP-strict_%28no_unsafe--eval%29-2ea44f)](SECURITY.md) [![Code signing](https://img.shields.io/badge/code_signing-free_%2F_ad--hoc-lightgrey)](SECURITY.md)

Her sürüm yayımlanırken [VirusTotal](https://www.virustotal.com) ile otomatik taranır; sonuçlar sürüm sayfasında. *Every release is scanned on VirusTotal automatically; results are on the release page.*

</div>

## ⬇️ İndir ve İlk Açılış / Download & First Start

[**Son sürüm sayfası / Latest release**](https://github.com/AmrasElessar/adminpdftoolkit/releases/latest) — kurulum gerektirmez, ücretsizdir.

| Sistem | Dosya | Aç |
|---|---|---|
| **Windows 10 / 11** (64 bit) | `AdminPDFToolkit-…-Windows.zip` | Çıkarın → `AdminPDFToolkit.exe` |
| **macOS 11+** (Apple Silicon M1–M4) | `AdminPDFToolkit-…-macOS-arm64.zip` | `AdminPDFToolkit.app`'i Uygulamalar'a sürükleyin → çift tıklayın |
| **Linux x86_64** (Ubuntu 22.04+, Debian 12+, Mint 21+, Pardus 23+, Fedora 36+) | `AdminPDFToolkit-…-Linux-x86_64.tar.gz` | Açın → `AdminPDFToolkit` |
| Intel Mac, ARM Linux, diğer | `AdminPDFToolkit-…-Linux-macOS.zip` | Python 3.11+ ile `scripts/start.sh` |
| Sunucu / NAS | Docker | `docker compose up -d --build` |

> [!IMPORTANT]
> **İlk açılışta işletim sistemi uyarı gösterecek — bu normaldir.** Uygulama ücretsiz ve açık kaynak olduğu için Microsoft ve Apple'ın ücretli kod imzalama / onay hizmetlerinden geçirilmedi; uyarı bir hata ya da virüs bulgusu değildir. Bir kez onaylarsınız, sonra çıkmaz:
>
> - **Windows — "Windows bilgisayarınızı korudu" (SmartScreen):** **Ek bilgi ▸ Yine de çalıştır**. (Zip'i açmadan önce sağ tık ▸ Özellikler ▸ **Engellemeyi kaldır** işaretlerseniz hiç çıkmaz.)
> - **Windows — "Güvenlik Uyarısı: sertifika yüklemek üzeresiniz":** **Evet**. Bu, uygulamanın yerel HTTPS sertifikasıdır; yalnızca bu bilgisayar ve yerel ağ adresleri için geçerlidir, hiçbir internet sitesi için geçerli değildir.
> - **Windows — Güvenlik duvarı** (ağ paylaşımı açıkken): yalnızca **Özel ağlar**'a izin verin.
> - **macOS — "Geliştirici doğrulanamadığından açılamıyor":** **Bitti** ▸ **Sistem Ayarları ▸ Gizlilik ve Güvenlik** ▸ aşağıda **Yine de Aç** ▸ parolanız. (Terminal: `xattr -dr com.apple.quarantine /Applications/AdminPDFToolkit.app`)
> - **macOS — parola isteği:** uygulamanın yerel HTTPS sertifikasına güvenmek içindir.
> - **Linux / telefonlar — tarayıcı sertifika uyarısı:** sertifikayı bir kez yükleyin (Linux: veri klasöründeki `tls/ca.crt`; telefon: eşleştirme ekranında **Sertifikayı yükle**).
>
> İndirdiğiniz dosyanın değiştirilmediğini sürüm sayfasındaki **`SHA256SUMS`** ile doğrulayabilirsiniz: Windows `certutil -hashfile <dosya> SHA256` · macOS `shasum -a 256 <dosya>` · Linux `sha256sum <dosya>`.

<details>
<summary>🇬🇧 Download & first start (English)</summary>

Get the package for your system from the [latest release](https://github.com/AmrasElessar/adminpdftoolkit/releases/latest) — free, nothing to install: **Windows 10 / 11** (`…-Windows.zip` → `AdminPDFToolkit.exe`), **macOS 11+ on Apple Silicon** (`…-macOS-arm64.zip` → drag `AdminPDFToolkit.app` to Applications), **Linux x86_64** (`…-Linux-x86_64.tar.gz` → `AdminPDFToolkit`), the Python 3.11+ package for Intel Macs / ARM Linux, or Docker.

> [!IMPORTANT]
> **The operating system will warn you on first start — that is expected.** Being free and open source, the app has not gone through Microsoft's and Apple's paid code-signing / notarisation; the warning is not an error or a virus finding. Confirm it once:
>
> - **Windows — "Windows protected your PC" (SmartScreen):** **More info ▸ Run anyway**. (Right-click the zip ▸ Properties ▸ **Unblock** before extracting and it never appears.)
> - **Windows — "Security Warning: you are about to install a certificate":** **Yes**. It is the app's local HTTPS certificate, valid only for this PC and local-network addresses, never for any website.
> - **Windows — Firewall** (with network sharing on): allow **Private networks** only.
> - **macOS — "cannot be opened because the developer cannot be verified":** **Done** ▸ **System Settings ▸ Privacy & Security** ▸ **Open Anyway** ▸ your password. (Terminal: `xattr -dr com.apple.quarantine /Applications/AdminPDFToolkit.app`)
> - **macOS — password prompt:** to trust the app's local HTTPS certificate.
> - **Linux / phones — browser certificate warning:** install the certificate once (Linux: `tls/ca.crt` in the data folder; phones: **Install certificate** on the pairing screen).
>
> Verify a download against **`SHA256SUMS`** on the release page: Windows `certutil -hashfile <file> SHA256` · macOS `shasum -a 256 <file>` · Linux `sha256sum <file>`.

</details>

## 🎬 Demo

<div align="center">

| | |
|---|---|
| <img src="docs/media/tools.png" alt="Araç listesi" width="440" /> | <img src="docs/media/editor.png" alt="PDF editörü" width="440" /> |
| **50+ araç, tek ekranda** — üzerine gelince açıklama | **PDF editörü** — metni değiştir, vurgula, not, imza |
| <img src="docs/media/kvkk.png" alt="KVKK modu" width="440" /> | <img src="docs/media/organizer.png" alt="Sayfa düzenleyici" width="440" /> |
| **KVKK modu** — tara, karart / bulanıklaştır / maskele | **Sayfa düzenleyici** — sürükle-bırak, döndür, sil |
| <img src="docs/media/viewer.png" alt="Görüntüleyici" width="440" /> | <img src="docs/media/shortcuts.png" alt="Klavye kısayolları" width="440" /> |
| **Görüntüleyici** — arama, yer imleri, yazdırma | **Klavye kısayolları** — `?` ile her yerde |

</div>

---

## 📌 Kısaca

**Admin PDF Toolkit**, kurum içi ağda çalışan, **internete ihtiyaç duymayan** ve **ücretsiz** bir PDF uygulamasıdır. Bir bilgisayarda sunucu olarak çalışır; aynı ağdaki herkes tarayıcıdan veya telefondan (PWA) kullanır. Yüklenen dosyalar **makineden hiç çıkmaz**, bulut servislerine gönderilmez ve süre sonunda silinir.

Adobe Acrobat'ta beklenen işlerin neredeyse tamamını yapar: **mevcut metni düzenleme** (taranmış belgelerde OCR ile bile), sayfa düzenleme, Word/Excel/PowerPoint ↔ PDF dönüşümü, **OCR**, **PAdES dijital imza**, **form oluşturma ve doldurma**, **KVKK'ya göre kişisel veri tarama ve kalıcı karartma**, **PDF/A**, belge karşılaştırma, sıkıştırma, şifreleme ve daha fazlası.

<details>
<summary>🇬🇧 At a glance (English)</summary>

**Admin PDF Toolkit** is a free PDF application that runs on your own network and **needs no internet**. One computer runs the server; everyone on the LAN uses it from a browser or phone (PWA). Uploaded files **never leave the machine**, are never sent to a cloud service and expire automatically.

It covers almost everything people use Adobe Acrobat for: **editing existing text** (even on scans, via OCR), page organisation, Word/Excel/PowerPoint ↔ PDF, **OCR**, **PAdES digital signatures**, **form creation and filling**, **personal-data scanning and permanent redaction (KVKK/GDPR)**, **PDF/A**, document comparison, compression, encryption and more.

</details>

---

## ✨ Öne Çıkan Özellikler / Highlights

| Grup | Neler var |
|---|---|
| ✎ **PDF editörü** | Mevcut metni yerinde değiştirme (orijinal font eşleştirme, sistem fontları), metin kutusu, görsel, el yazısı / yazılı / görsel imza, şekiller, kalem, beyazla kapatma, bağlantı, vurgulama / altı / üstü çizili, yapışkan not, **form alanı oluşturma**; taşı, boyutlandır, geri al / yinele |
| 🔍 **Taranmış belgeler** | Görsel tabanlı PDF'ler algılanır, tek tıkla **OCR** (Türkçe + İngilizce) uygulanır ve metin düzenlenebilir hale gelir; eğik sayfalar otomatik düzeltilir |
| ⬛ **KVKK modu** | Belge otomatik taranır: T.C. kimlik no, IBAN, kart, telefon, e-posta, plaka, vergi no, ad-soyad, adres, doğum bilgisi ve **özel nitelikli veri** ipuçları; her biri için **karart / bulanıklaştır / maskele / beyazla / dokunma** seçilir, kalıcı uygulanır; **Ekstra güvenli PDF** seçeneği sayfaları görüntüye çevirip yeniden PDF yapar (altta seçilebilir metin kalmaz) |
| 📑 **Sayfalar** | Küçük resimlerle sürükle-bırak düzenleme, döndür, sil, çoğalt, boş sayfa; birleştir (yer imli), böl, çıkar |
| 🔄 **Dönüştür** | PDF ↔ Word, PDF → Excel (tablo algılama), Word / Excel / PowerPoint → PDF, PDF ↔ JPG / PNG, PDF → metin |
| 📷 **Görselden PDF** | Telefon fotoğrafı yönü (EXIF), **otomatik eğim düzeltme**, kâğıdı bulup **perspektif düzeltme**, gölge temizleme, siyah-beyaz tarama görünümü; sayfa boyutu (görsel boyutu / A4 / Letter / A3) ve yerleşim (**sığdır / doldur / genişlet / özgün boyut**) |
| ✒ **İmza** | PAdES dijital imza (görünür / görünmez), imza doğrulama, imza sertifikası oluşturma |
| 🧾 **Formlar** | Alanları listele, doldur, düzleştir; editörde metin kutusu, onay kutusu, açılır liste, imza alanı çiz |
| 🏛 **Arşiv & standartlar** | PDF/A-1b/2b/3b, **PDF/UA erişilebilirlik denetimi ve düzeltme**, meta veri, yer imleri (otomatik dahil), gömülü ekler |
| ⚖ **Karşılaştır** | İki sürüm arasında eklenen / silinen sözcükler ve sayfalar, yan yana rapor |
| 🛡 **Güvenlik** | Her zaman **HTTPS** (kendi yerel sertifika yetkilisi), **yalnızca yerel ağ**, cihaz başına dosya yalıtımı; AES-256 şifreleme ve izinler, güvenlik taraması (JavaScript, gömülü dosya, ClamAV), güvenli temizleme, onarım |
| 📊 **İş akışları** | Çağrı kaydı PDF'leri → birleşik Excel, mükerrer silme, filtreleme, ekiplere dağıtım |
| ⌨ **Kullanım** | Seçili dosyaya uygun araçlar yeşil renkte ve öne sıralanır, **sık kullanılanlar** kullanıcı seçer; tam klavye desteği ve kısayollar (`?`), TR / EN, açık / koyu tema, telefon ve tablet için PWA (QR ile bağlanma) |
| ℹ️ **Hakkında ve Lisanslar** | Uygulama içinde Türkçe ve İngilizce ayrı: çalıştığı sistemler, ilk açılış uyarıları, kullanılan tüm açık kaynak bileşenler ve lisansları |

<details>
<summary>🇬🇧 Highlights (English)</summary>

- **PDF editor** — change existing text in place (original font matching, system fonts), text boxes, images, drawn / typed / image signatures, shapes, pen, whiteout, links, highlight / underline / strikethrough, sticky notes, **form-field creation**; move, resize, undo / redo.
- **Scanned documents** — image-only PDFs are detected and made editable with one-click **OCR** (Turkish + English); tilted pages are straightened.
- **KVKK mode** — automatic scan for national IDs, IBANs, cards, phones, e-mails, plates, tax numbers, names, addresses, birth details and **special-category** hints; choose **black-out / blur / mask / white-out / keep** per finding and apply permanently; the **extra-secure PDF** option turns pages into images and back into a PDF (no selectable text left underneath).
- **Pages** — drag-and-drop organiser, rotate, delete, duplicate, blank pages; merge (with bookmarks), split, extract.
- **Convert** — PDF ↔ Word, PDF → Excel (table detection), Word / Excel / PowerPoint → PDF, PDF ↔ JPG / PNG, PDF → text.
- **Images → PDF** — EXIF orientation, **automatic deskew**, sheet detection with **perspective correction**, shadow removal, black-and-white scan look; page size (image / A4 / Letter / A3) and placement (**fit / fill / stretch / original size**).
- **Signatures** — PAdES (visible / invisible), verification, self-signed certificate creation.
- **Forms**, **PDF/A**, **PDF/UA check & fix**, metadata, bookmarks, attachments, **compare**, AES-256, security scan, sanitise, repair, call-log workflows.
- **Security** — always **HTTPS** (own local certificate authority), **local network only**, per-device file isolation.
- Tools that fit the selected file are shown green and first, **favourites** chosen by the user; full keyboard support (`?`), TR / EN, light / dark, installable PWA for phones and tablets (connect by QR).
- **About & Licences** in the app — Turkish and English separately: supported systems, first-start warnings, every open-source component and its licence.

</details>

---

## 🎯 Vizyon / Vision

Kamu kurumları, okullar, sağlık birimleri, hukuk büroları ve şirket BT ekipleri PDF'lerini **dışarıya göndermeden** işlemek zorundadır. Çevrimiçi PDF servisleri KVKK riski taşır, ticari masaüstü yazılımları kullanıcı başına pahalıdır. Admin PDF Toolkit bu boşluğu doldurur: **tek kurulum, tüm ağ, sıfır dış bağımlılık, açık kaynak.**

<details>
<summary>🇬🇧 Vision (English)</summary>

Public bodies, schools, healthcare units, law firms and corporate IT teams must process PDFs **without sending them outside**. Online PDF services are a compliance risk and commercial desktop software is expensive per seat. Admin PDF Toolkit fills the gap: **one install, the whole network, zero external dependencies, open source.**

</details>

---

## 📥 Kurulum / Installation

### Windows (en kolay — kurulum gerektirmez)

1. [Son sürüm](https://github.com/AmrasElessar/adminpdftoolkit/releases/latest) sayfasından **`AdminPDFToolkit-…-Windows.zip`** dosyasını indirin ve bir klasöre çıkarın.
2. **`AdminPDFToolkit.exe`** dosyasına çift tıklayın. Başlatıcı Python'dan başlayarak her bileşeni tek tek denetleyip işaretler (✔ / ⚠ / –), sunucuyu **konsol penceresi açmadan** başlatır, "Sistem hazır" der ve adres, yerel ağ adresleri, sertifika parmak izi, veri klasörü bilgilerini gösterir; tarayıcı açılır. Pencereyi kapatınca uygulama **sistem çubuğunda** çalışmaya devam eder; **Çıkış** ile tamamen kapanır.

Python veya başka bir program kurmanız gerekmez; paket kendi Python'unu, tüm kütüphaneleri, **OCR motorunu (Tesseract + Türkçe/İngilizce dil verisi)** ve **Ghostscript'i (PDF/A)** içerir; internetsiz çalışır — indirmeleri engelleyen kurum ağlarında da. Gömülü araçlar her kullanımdan önce paketteki SHA-256 listesine göre doğrulanır.

**Güncellemeler:** başlatıcı açılışta (isteğe bağlı) yeni sürümü denetler; varsa içerdiği bileşen sürümleriyle birlikte sorar, **kurup kurmamak sizin seçiminiz**. Yalnızca imzası (Ed25519) ve SHA-256 özeti doğrulanan paketler kurulur; verileriniz ve sertifikanız korunur. Ağ güncellemeyi engelliyorsa uygulama normal çalışmaya devam eder.

İlk açılışta Windows, uygulamanın yerel HTTPS sertifikasına güvenmek için bir kez onay ister (sonradan: başlatıcıda **Diğer ▸ Sertifikaya bu bilgisayarda güven**). Konsollu yedek başlatma dosyaları `scripts\` klasöründedir.

### macOS (Apple Silicon M1–M4 — kurulum gerektirmez)

1. [Son sürüm](https://github.com/AmrasElessar/adminpdftoolkit/releases/latest) sayfasından **`AdminPDFToolkit-…-macOS-arm64.zip`** dosyasını indirin; çift tıklayarak açın.
2. **`AdminPDFToolkit.app`**'i **Uygulamalar** (Applications) klasörüne sürükleyin ve çift tıklayın.
3. **İlk açılışta macOS uyarı verir — bu normaldir:**

   > [!WARNING]
   > *"AdminPDFToolkit.app" açılamıyor, çünkü geliştirici doğrulanamıyor.* (macOS 15+: *"Apple, AdminPDFToolkit.app uygulamasının kötü amaçlı yazılım içermediğini doğrulayamadı."*)
   >
   > Uygulama ücretsiz ve açık kaynak olduğu için Apple'ın ücretli geliştirici hesabı ve onay (notarization) sürecinden geçirilmedi; uyarı bir virüs bulgusu değildir. **Bir kez** şunu yapın:
   > 1. Uyarıda **Bitti**'ye basın (**Çöp Sepetine Taşı**'ya basmayın).
   > 2. **Sistem Ayarları ▸ Gizlilik ve Güvenlik**'i açın, aşağı kaydırın.
   > 3. *"AdminPDFToolkit.app engellendi"* yanındaki **Yine de Aç**'a basın, parolanızı (veya Touch ID) girin, son soruda yine **Aç** deyin.
   >
   > Sonraki açılışlar normaldir. Terminal'i biliyorsanız aynısı: `xattr -dr com.apple.quarantine /Applications/AdminPDFToolkit.app`

4. Başlatıcı bileşenleri tek tek denetler, **"Sistem hazır"** der ve tarayıcıyı açar. İlk açılışta macOS, yerel HTTPS sertifikasına güvenmek için **parolanızı** bir kez isteyebilir.
5. OCR ve PDF/A için (isteğe bağlı): [Homebrew](https://brew.sh) ile `brew install tesseract tesseract-lang ghostscript`; başlatıcı eksikse bu komutu gösterir. Diğer tüm araçlar bunlar olmadan da çalışır.

Veriler: `~/Library/Application Support/AdminPDFToolkit` (güncellemede silinmez). Intel Mac'lerde Python paketini (`…-Linux-macOS.zip`) kullanın.

### Linux (x86_64 — Ubuntu 22.04+, Debian 12+, Mint 21+, Pardus 23+, Fedora 36+)

1. [Son sürüm](https://github.com/AmrasElessar/adminpdftoolkit/releases/latest) sayfasından **`AdminPDFToolkit-…-Linux-x86_64.tar.gz`** dosyasını indirin ve açın: `tar xzf AdminPDFToolkit-*-Linux-x86_64.tar.gz`
2. **`AdminPDFToolkit/AdminPDFToolkit`** dosyasına çift tıklayın (veya terminalde `./AdminPDFToolkit/AdminPDFToolkit`). Uygulamalar menüsüne eklemek için bir kez `Uygulamalar menusune ekle.sh`.
3. Başlatıcı bileşenleri denetler, **"Sistem hazır"** der ve tarayıcıyı açar.
4. **Tarayıcı sertifika uyarısı verirse:** başlatıcıda **Diğer ▸ Sertifikaya bu bilgisayarda güven** sertifikanın yerini gösterir (`~/.local/share/AdminPDFToolkit/tls/ca.crt`); onu tarayıcının sertifika ayarlarından **Yetkili / Authorities** olarak bir kez içe aktarın. Yalnızca bu bilgisayar ve yerel ağ adresleri için geçerlidir.
5. OCR ve PDF/A için (isteğe bağlı): `sudo apt install tesseract-ocr tesseract-ocr-tur ghostscript` (Fedora: `sudo dnf install tesseract tesseract-langpack-tur ghostscript`).

Veriler: `~/.local/share/AdminPDFToolkit`. ARM Linux'ta Python paketini (`…-Linux-macOS.zip`) kullanın.


### Docker (tüm araçlar dahil: OCR, LibreOffice, Ghostscript, ClamAV)

```bash
git clone https://github.com/AmrasElessar/adminpdftoolkit.git
cd adminpdftoolkit
docker compose up -d --build        # https://localhost:8000 (sertifika: docker cp ile /data/tls/ca.crt)
```

### Kaynaktan / From source

```bash
# sunucu / server (Python 3.11+)
cd server && pip install -e ".[dev]"
# arayüz / web UI (Node 20+) — bir kez derleyin / build once
cd ../web && npm ci && npm run build
# çalıştır / run
cd ../server && python -m adminpdf --open
```

İsteğe bağlı sistem araçları — yoksa ilgili araç açık bir uyarı verir, diğerleri çalışır:
**Tesseract** + `tur` dil paketi (OCR), **LibreOffice** (Office → PDF yüksek doğruluk), **Ghostscript** (PDF/A), **qpdf** (onarım), **ClamAV** (virüs taraması).

> **Windows'ta OCR:** kurulum gerektirmeyen Windows paketinde OCR hazır gelir. Python paketiyle çalıştırıyorsanız **`OCR Kur (Windows).bat`** Tesseract'ı (winget, kurulum dosyası özeti doğrulanarak) ve Türkçe dil paketini kurar. Elle kurmak isterseniz: [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) kurulumunda *Additional language data* altından **Turkish**'i işaretleyin. PATH'e eklemeniz gerekmez; uygulama `Program Files\Tesseract-OCR` ve `Program Files\gs` klasörlerini kendisi bulur. Kurulumdan sonra uygulamayı yeniden başlatın.

<details>
<summary>🇬🇧 Installation (English)</summary>

- **Windows:** download **`AdminPDFToolkit-…-Windows.zip`** from the [latest release](https://github.com/AmrasElessar/adminpdftoolkit/releases/latest), unzip, double-click **`AdminPDFToolkit.exe`**. The launcher ticks off every component (Python, libraries, UI, certificate, OCR, Ghostscript, …), starts the server with no console window, says "System ready" and shows the addresses and certificate fingerprint; closing the window keeps it in the notification area. Nothing to install — Python, all libraries, Tesseract (+ Turkish/English) and Ghostscript are inside; works offline, also on networks that block downloads. Optional update check at start: a newer release is offered with its component versions and installed only if you agree and its Ed25519 signature and SHA-256 verify. Console fallbacks are in `scripts\`.
- **macOS (Apple Silicon M1–M4):** download **`…-macOS-arm64.zip`**, open it, drag **`AdminPDFToolkit.app`** to **Applications**, double-click. **On first start macOS warns** *"cannot be opened because the developer cannot be verified"* (macOS 15+: *"Apple could not verify … is free of malware"*) — expected, as the free app has no paid Apple developer account / notarisation. Once: **Done** (not *Move to Trash*) ▸ **System Settings ▸ Privacy & Security** ▸ **Open Anyway** ▸ password / Touch ID ▸ **Open**. (Terminal: `xattr -dr com.apple.quarantine /Applications/AdminPDFToolkit.app`.) macOS may then ask for your password once to trust the local HTTPS certificate. OCR / PDF/A: `brew install tesseract tesseract-lang ghostscript`. Data: `~/Library/Application Support/AdminPDFToolkit`.
- **Linux x86_64:** download **`…-Linux-x86_64.tar.gz`**, `tar xzf` it, run **`AdminPDFToolkit/AdminPDFToolkit`** (menu entry: `Uygulamalar menusune ekle.sh`). If the browser warns about the certificate, import `~/.local/share/AdminPDFToolkit/tls/ca.crt` once as an **Authority** (the launcher's **More ▸ Trust the certificate here** shows where it is). OCR / PDF/A: `sudo apt install tesseract-ocr tesseract-ocr-tur ghostscript`.
- **Docker:** `docker compose up -d --build` — includes OCR, LibreOffice, Ghostscript and ClamAV.
- **From source:** `pip install -e ".[dev]"` in `server/`, `npm ci && npm run build` in `web/`, then `python -m adminpdf --open`.
- Optional tools: Tesseract (+`tur`), LibreOffice, Ghostscript, qpdf, ClamAV. Missing tools only disable their own features.
- OCR on Windows: bundled in the self-contained package. With the Python package, **`OCR Kur (Windows).bat`** installs Tesseract (winget, installer hash checked) and the Turkish data. Manually: install [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and tick **Turkish** under *Additional language data*. No PATH change needed — the default install folders of Tesseract and Ghostscript are detected. Restart the app afterwards.

</details>

---

## 🚀 İlk Adımlar / Quick Start

1. Dosyaları sol panele **sürükleyin** (PDF, Word, Excel, PowerPoint, JPG, PNG…).
2. Bir PDF seçip **PDF Düzenle**, **Sayfaları Düzenle**, **KVKK Tara ve Karart** veya listeden bir araç seçin.
3. Sonucu indirin ya da **Çalışma alanına ekle** ile bir sonraki araca girdi yapın (ör. birleştir → sıkıştır → şifrele).
4. `?` tuşu tüm klavye kısayollarını gösterir.

**Telefondan / tabletten erişim:** başlatıcıda **Ağ paylaşımı** kutusunu işaretleyin (veya `python -m adminpdf --lan`) — sunucu bilgisayarında sağ üstteki **📱 Cihaz bağla** penceresindeki QR kodu telefonla okutun. Bağlantı her zaman **HTTPS**'tir; uyarısız kullanım için eşleştirme ekranındaki **Sertifikayı yükle** ile sunucunun sertifikasını cihaza bir kez yükleyin. **Yalnızca aynı yerel ağdaki** (özel IP) cihazlar bağlanabilir; internetten gelen her istek reddedilir.

*Phones/tablets: tick **Network sharing** in the launcher (or start with `--lan`), scan the QR code under **📱 Connect device** on the server PC. Always HTTPS (the server's own local CA; install it once via **Install certificate** for warning-free use). Only devices on the same local network are ever served.*

### Ayarlar / Configuration (`APT_*`)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `APT_HOST` / `APT_PORT` | `127.0.0.1` / `8000` | Dinlenen adres |
| `APT_DATA_DIR` | `_data` | Yüklemeler ve iş klasörleri |
| `APT_MAX_UPLOAD_MB` | `200` | Dosya başına sınır |
| `APT_FILE_TTL_MINUTES` | `120` | Dosyalar bu süre sonunda silinir |
| `APT_MAX_WORKERS` | `2` | Eşzamanlı iş sayısı |
| `APT_JOB_TIMEOUT_SECONDS` | `600` | İş başına zaman sınırı |
| `APT_WORKER_MEMORY_MB` | `4096` | İş süreci bellek tavanı (POSIX) |
| `APT_LAN_ENABLED` / `APT_PAIRING_KEY` | kapalı | Ağdaki cihazlar eşleştirme anahtarıyla bağlanır (anahtar en az 12 karakter; `--lan` rastgele üretir) |
| `APT_TRUSTED_NETWORKS` | — | Eşleştirme istemeyen **yerel** ağlar (CIDR) veya `gateway` (Docker ana makinesi; LAN modunda yok sayılır) |
| `APT_ALLOWED_HOSTS` | — | Ek Host adları (ör. `pdf.kurum.local`); sertifikaya da eklenir |
| `APT_TLS` | `true` | HTTPS (kendi yerel CA'sı, `APT_DATA_DIR/tls`). Yalnızca kendi TLS vekil sunucunuzun arkasında kapatın |
| `APT_TLS_CERT_FILE` / `APT_TLS_KEY_FILE` | — | Kurumunuzun kendi sertifikası |
| `APT_MAX_STORAGE_MB` | `10240` | Toplam depolama tavanı (aşılırsa yükleme 507) |
| `APT_API_DOCS` | `false` | `/api/docs` geliştirici belgeleri |
| `APT_OCR_DIR` / `APT_GS_DIR` | — | Gömülü Tesseract / Ghostscript klasörü (Windows paketi ayarlar; dosyalar `manifest.json` ile doğrulanır) |

---

## ⬛ KVKK / Personal data

- Dosyalar **yalnızca sunucu bilgisayarında** işlenir; hiçbir bulut servisine gönderilmez, analitik/telemetri yoktur.
- Yüklemeler ve sonuçlar **süre sonunda kendiliğinden silinir** (`APT_FILE_TTL_MINUTES`).
- **KVKK modu** kişisel verileri bulur; uygulanan her işlem alttaki metni **kalıcı olarak siler** (bulanıklaştırma yalnızca görünümü korur), meta veriyi temizler.
- Özel nitelikli veri (KVKK md. 6) ipuçları otomatik işlenmez, **insan kararına** sunulur.

<details>
<summary>🇬🇧 Personal data (English)</summary>

Files are processed only on the server machine — no cloud, no telemetry; uploads expire automatically. KVKK mode finds personal data and every treatment permanently removes the underlying text (blur only keeps the look) and strips metadata. Special-category hints (KVKK art. 6) are left for a human decision.

</details>

---

## 🛠️ Teknoloji / Tech Stack

| Katman | Teknoloji |
|---|---|
| Sunucu | Python 3.11+ · FastAPI · PyMuPDF · pikepdf · pyHanko · OCRmyPDF/Tesseract · pdf2docx · OpenCV · LibreOffice (isteğe bağlı) |
| Arayüz | Svelte 5 · TypeScript · Vite · pdf.js |
| Başlatıcı | Windows: C# / .NET Framework (`AdminPDFToolkit.exe`) · macOS / Linux: Python + Tk · gömülü Python (python.org embeddable / python-build-standalone) |
| Mimari | İşlem kayıt defteri (her araç tek sınıf, form şemadan üretilir) · her iş ayrı süreçte (zaman aşımı, iptal, bellek sınırı) · güvenlik tek ara katmanda (Host izin listesi, CSRF, sıkı CSP, LAN eşleştirme) |
| Kalite | 350+ sunucu testi · mypy --strict · ruff · svelte-check · axe-core WCAG 2.1 AA denetimi · CodeQL · Windows/macOS/Linux CI · her sürümde VirusTotal taraması ve Ed25519 imzalı `SHA256SUMS` |

Ayrıntılar: [ARCHITECTURE.md](ARCHITECTURE.md) · Standartlar: [STANDARDS.md](STANDARDS.md)

---

## 📐 Standartlar / Standards

ISO 32000 (PDF) · ISO 19005 (PDF/A) · ISO 14289 (PDF/UA denetim + düzeltme) · ETSI EN 319 142 (PAdES) · ISO/IEC 40500 / WCAG 2.1 AA (arayüz) · ISO 8601 · BCP 47 · KVKK / GDPR — ayrıntılar ve sınırlar [STANDARDS.md](STANDARDS.md) içinde.

---

## 🗺️ Yol Haritası / Roadmap

- [x] v2 mimarisi, güvenlik ara katmanı, süreç izole iş motoru
- [x] Görüntüleyici, sayfa düzenleyici, PDF editörü (taranmış belgeler dahil)
- [x] Dönüştürme, OCR, formlar, dijital imza, KVKK modu, PDF/A, PDF/UA, karşılaştırma
- [x] Docker, CI, PWA, klavye kısayolları, erişilebilirlik
- [x] Kurulum gerektirmeyen Windows, macOS ve Linux paketleri (OCR ve Ghostscript gömülü, başlatıcı penceresi)
- [x] HTTPS, yalnızca yerel ağ, telefon / tablet eşleştirme (QR)
- [x] İmzalı güncellemeler (Ed25519), her sürümde VirusTotal taraması
- [ ] Windows kurulum sihirbazı (MSI)
- [ ] PAdES zaman damgası (kurum içi TSA desteğiyle)
- [ ] Etiketsiz belgeler için yarı otomatik PDF/UA etiketleme

v1 (1.13.2) kaynak kodu [`archive/`](archive/) klasöründe ve git geçmişindedir.

---

## 🤝 Katkı / Contributing

Katkılar memnuniyetle karşılanır — [CONTRIBUTING.md](CONTRIBUTING.md). Güvenlik açıkları için lütfen [SECURITY.md](SECURITY.md).

---

## 🎨 D Brand Ailesi / D Brand Family

Admin PDF Toolkit, **D Brand** açık kaynak araç ailesinin bir parçasıdır. *Admin PDF Toolkit is part of the **D Brand** family of open-source tools:*

[d-terminal](https://github.com/AmrasElessar/d-terminal) · [d-transfer](https://github.com/AmrasElessar/d-transfer) · [d-medic](https://github.com/AmrasElessar/d-medic) · [d-space](https://github.com/AmrasElessar/d-space) · [d-livewallpaper](https://github.com/AmrasElessar/d-livewallpaper)

---

## ❤️ Destekle / Support

Proje işinize yaradıysa ⭐ vererek veya [sponsor olarak](https://github.com/sponsors/AmrasElessar) destekleyebilirsiniz.

---

## 📜 Lisans / License

[GNU AGPL-3.0](LICENSE) — bu yazılımı değiştirip **ağ üzerinden hizmet olarak** sunarsanız, değiştirilmiş kaynak kodu kullanıcılarla paylaşmanız gerekir. Üçüncü taraf lisansları: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) ve uygulamada **Hakkında ve Lisanslar**.

<details>
<summary>🇬🇧 License (English)</summary>

GNU AGPL-3.0 — if you modify this software and offer it **as a network service**, you must share the modified source with its users. Third-party licences: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) and **About & Licences** in the app.

</details>
