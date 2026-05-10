# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security — full audit sweep (2026-05-10)

Triggered by `SECURITY_AUDIT_2026_05_10.md`; closes ~20 issues beyond
the four documented in the Chrome extension roadmap. 394 tests still
green; one Windows-admin-only symlink test skipped.

#### Cross-origin / SSRF / LFI
- `/pdf/from-url` redirect bypass closed — every 301/302 target is
  re-validated through `_assert_public_url`; URL basic-auth rejected;
  response body capped at 50 MB.
- `/pdf/from-html` body capped at 10 MB (was the upload limit, i.e.
  ~2 GB before the cap drop).
- `xhtml2pdf` `link_callback` now strict: only `ht-font://` and
  `data:` schemes resolve; `file:///etc/passwd`, external `http://`
  return empty (defense against LFI through `<img src=…>` in
  attacker-supplied HTML).
- `save_pdf_upload` runs `gate_pdf_safety` by default — closes 30+
  `/pdf/*` and `/pdf/edit/*` endpoints that previously bypassed the
  safety scanner.

#### CSRF
- `/admin/enable-mobile`, `/admin/disable-mobile`,
  `/admin/clamav-update`, and `DELETE /history` now require an
  Origin/Referer matching the server's own host; blocks the
  cross-origin POST-from-evil-site attack against the operator's
  loopback session.
- Mobile token migrated from `?key=` URL parameter to `#key=` URL
  fragment — fragments never reach the server, never log, never
  appear in referer headers. `?key=` fallback dropped from
  middleware. Existing JS already captures the bootstrap token from
  the URL into `localStorage`.

#### Path traversal / DoS
- `make_job_dir` hardened in three layers: explicit separator/`..`
  reject, pre-`mkdir` resolve+containment check (avoids leftover
  directories from rejected probes), post-`mkdir` symlink check
  (guards against TOCTOU symlink races).
- `routers/batch.py` token-taking endpoints validate `check_token`
  before touching the filesystem.
- `parse_int_list` capped at 100 000 entries (defends against
  `1-99999999` style page lists OOMing the worker).
- Bounded background-worker concurrency via `submit_worker` /
  `HT_MAX_INFLIGHT_JOBS` (default 4); saturation returns 503 instead
  of unbounded thread spawn.

#### Authn / info disclosure
- `/health` returns only `{ok: true}` to unauthenticated remote
  callers; version + telemetry restricted to loopback / mobile-token
  callers.
- `pdfid.py` is now invoked through `sys.executable` (PATH-poisoning
  defense).
- `HT_LOOPBACK_BYPASS=false` setting for reverse-proxy deployments
  where the proxy connects via 127.0.0.1 and would otherwise hide
  every remote client from the auth middleware.

#### Crypto / cert
- Self-signed cert: `datetime.now(timezone.utc)` (replaces deprecated
  `utcnow`); validity reduced 5 y → 1 y; auto-rotates when fewer than
  30 days remain; key file is `chmod 0600` on POSIX.

#### Hardening defaults
- Default `MAX_UPLOAD_MB` lowered 2048 → 200 (raise via
  `HT_MAX_UPLOAD_MB`).
- `safe_filename` adds NFKC normalisation + control-char strip.
- `extract_images` capped (50 MB / image, 200 MB / job),
  `pdf_to_csv` at 100 k rows, `pdf_to_markdown` at 50 MB.
- Baseline browser headers on every response:
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`,
  `Cross-Origin-Opener-Policy: same-origin`.

### Added
- `CHROME_EXTENSION_ROADMAP.md` — deferred plan for a Manifest V3
  browser extension that bridges the operator's browser to the
  locally-running app via `localhost`.

## [1.11.0] - 2026-04-28 — `core/` package, perf pass, ClamAV bundling

### Added — ClamAV bundled-and-self-installing
- **`scripts/setup_clamav.py`** — downloads portable ClamAV ZIP from the
  Cisco-Talos GitHub release (~150 MB), unpacks just the runtime
  binaries (skips UserManual / `*.lib` / `*.pdb` / headers / docs), drops
  a minimal `freshclam.conf`, and pulls the signature database
  synchronously (~300 MB) so the engine is fully armed before the server
  starts. Idempotent; passes `--force`, `--skip-signatures`, `--keep-zip`.
- **`core/clamav_update.py`** — `should_update` (24 h throttle + missing
  DB), `update_signatures` (subprocess freshclam wrapper, atomic state
  file under `_work/clamav_state.json`), `maybe_update` (lifespan hook),
  `status` (admin endpoint payload).
- **`app.py:_lifespan`** — daemon thread runs `_maybe_update_clamav()`
  on every boot. No-op when ClamAV isn't bundled or DB is fresh; refresh
  in background otherwise.
- **`/admin/clamav` (GET)** — DB age, last update, last error, throttle
  state. Local-only.
- **`/admin/clamav-update` (POST)** — manual trigger; runs freshclam on
  a daemon thread + returns immediately. Local-only.
- **Self-install in launcher BATs** — `Sunucuyu Başlat.bat` and the
  end-user `Admin PDF Toolkit Baslat.bat` (rendered by `Portable Paket.bat`)
  now check for `clamav\clamscan.exe` + `clamav\database\main.cvd|cld`
  on every boot; missing → invoke `setup_clamav.py` automatically before
  starting the server.
- **15 new tests** (`tests/test_clamav_update.py`) — should_update / update
  state / timeout / network failure / status — all use a stub subprocess,
  no real network reach.

### Added — `core/` package (split from monolithic `core.py`)
- `core.py` (3932 lines) → `core/` package with **16 thematic submodules**
  (`logging_setup`, `errors`, `jobs`, `files`, `cleanup`, `history_db`,
  `network`, `security`, `distribution`, `ocr_preload`, `batch`,
  `pdf_tools`, `converters`, `analysis`, `editor`, `fonts`, `metadata`).
  `core/__init__.py` is now 185 lines of pure re-exports. The
  `core.X` access pattern is preserved for routers + tests.
- **Late-binding gotcha documented:** modules touching values tests
  monkeypatch on `core` (e.g. `STATE_DIR`, `HISTORY_DB_PATH`) read via
  `import core; core.X` inside functions — NOT at import time — so
  patches resolve at call site.

### Performance — measured against 56 real PDFs (465 MB)
- **`log_history` SQLite connection reuse** — 2284 ms / 1000 inserts →
  415 ms (**−82%**). Process-wide cached `Connection` (WAL,
  `check_same_thread=False`); the existing `_history_lock` already
  serialised access so no concurrency change needed.
- **`deep_analyze` 5 PDF opens → 1** — added internal `*_from_doc`
  variants (`_classify_extractability_from_doc`, `_metadata_from_doc`,
  `_outline_from_doc`, `_headers_footers_from_doc`); public functions
  are thin wrappers. Bench-resistant on small PDFs (open cost ≪ page
  walk) but the structural win is real and shows up on big documents.
- **`pdf_converter.py` heavy imports deferred** — `openpyxl` and
  `pdf2docx` moved into the functions that use them. The spawn-mode
  `parse_pdf_for_batch` worker now pulls **0 heavy modules** at boot
  (verified via `sys.modules` snapshot). Significant win for batch
  jobs on Windows where spawn imports the worker module fresh per
  process.
- **Lifespan font cache pre-warm** — `_find_unicode_font`,
  `_patch_pisa_for_local_fonts`, `_ensure_pisa_unicode_font`,
  `discover_system_fonts` fired in a daemon thread at boot so first
  watermark / HTML→PDF / editor render doesn't pay 100-300 ms of
  scanning + xhtml2pdf+reportlab patching.
- **Pixmap eager release in pipelines** — `pix = None` after
  `pix.save()` / `pix.tobytes()` in `pipelines/convert.py`,
  `pipelines/ocr.py` (×2), `pdf_converter.py` (×2). Stops PyMuPDF
  pixel buffers (in C heap, GC-blind) accumulating during 100+ page
  batches.
- **Safety + kind-detection doc reuse** — `pdf_safety.check_structure`
  and `full_scan` accept an optional pre-opened `fitz.Document`.
  `routers/batch.py` and `routers/convert.py` now open once and pass
  the doc to safety, eliminating one redundant `fitz.open` per file.

### Added — Benchmark harness
- **`scripts/bench_perf.py`** — runs the six hot paths against PDFs in
  `_bench_samples/` (or auto-synthesises a 10-page PDF if empty).
  Modes: `--save baseline.json`, `--compare baseline.json`,
  `--simulate-pre-perf` (recreates the inefficient pre-optimisation
  paths inline so before/after compares without git history),
  `--ab` (one-shot before+after diff). Pure stdlib + tracemalloc.

### Changed
- **`tests/test_pdf_engine.py`** — `SAMPLES_DIR` migrated from a
  hardcoded `C:/Projeler/pdfconverter/örnek` path to a portable
  `Path(__file__).resolve().parent.parent / "_bench_samples"`.
- **Packaging consistency:** `Dockerfile`, `build_portable.py`,
  `Portable Paket.bat`, `scripts/check_packaging.py` and `.gitignore`
  all updated for the `core/` directory move and the optional
  `clamav/` bundling. `scripts/` directory is now copied into the
  portable build (was previously missing — end-user `Baslat.bat`
  needed it for `setup_clamav.py`).

### Test count
- **378 → 394** (+15 new ClamAV tests, +1 sample-redirect win).
  All green; one platform skip (Windows symlink admin).

## [1.10.0] - 2026-04-27 — Rebrand: Admin PDF Toolkit by Engin

### Changed
- **Görünür ad** "HT Admin PDF Çevirici" / "HT Admin PDF Converter" →
  **"Admin PDF Toolkit"** (TR + EN ortak — "Toolkit" Türkçe'de de kullanılıyor).
  Alt başlık: **"by Engin"**.
- Tüm UI string'leri, başlıklar, modal'lar, BAT script title'ları, NOTICE,
  README'ler, SECURITY, CONTRIBUTING, manifest, service worker, Dockerfile
  label, docker-compose service adı, CI workflow image tag'leri güncellendi.
- Package adı (`pyproject.toml`): `ht-admin-pdf-converter` → `admin-pdf-toolkit`.
- Portable build çıktı dizini: `dist/HT_Admin_PDF_Portable/` →
  `dist/Admin_PDF_Toolkit_Portable/`.
- Portable starter BAT: `HT Admin PDF Baslat.bat` → `Admin PDF Toolkit Baslat.bat`.
- HTTPS self-signed cert CN: `HT Admin PDF Local` → `Admin PDF Toolkit Local`.
- PWA manifest: name `Admin PDF Toolkit`, short_name `Admin PDF`.
- iOS app title meta: `HT PDF` → `Admin PDF Toolkit`.

### Preserved (compat)
- **`HT_*` env prefix** — `HT_PORT`, `HT_MAX_UPLOAD_MB` vb. kullanan
  `.env` dosyaları çalışmaya devam eder.
- **Logger adı** `ht_pdf` — log filtreleri etkilenmez.
- **Windows servis adı** `HTAdminPDF` (NSSM SVCNAME) — daha önce kurulmuş
  servisler `Servis Yoneticisi.bat` ile yönetilebilir; sadece DisplayName
  güncellendi.

### Notes
- Hiçbir test kırılmadı. Suite **232/232 yeşil**.
- İçeride çalışan kullanıcılar: yeni portable build aldıktan sonra eski
  `dist/HT_Admin_PDF_Portable/` klasörünü silebilirler.

## [1.9.1] - 2026-04-27 — Replace mode: dynamic font fitting

### Added
- **`_fit_fontsize_to_rect(text, rect, ...)`** — replace mode'da uzun metin
  yerleştirilince fontsize otomatik küçülerek sığdırılır. Tek-shot ratio
  hesabı (rect.width / text_width × 0.97) + verifikasyon iterasyonu;
  minimum 4pt floor. Orijinal kısa metni büyütmez (sadece sığmıyorsa
  küçültür) — visual integrity korunur.
- 3 yeni test: shrink-on-long, no-grow-on-short, real PDF replace round-trip.

### Notes
- Suite total **232 yeşil** (önce 229).
- 130 karakterlik metin 12pt → ~9pt'ye küçülerek 562pt rect'e sığdı.
- Gemini'nin önerisi (mantığa kanal açan) iyi noktaydı — algoritmayı
  iteratif loop yerine direct ratio + verify olarak yazdık (daha
  deterministik). RapidOCR/EasyOCR migration'ı ayrı round'da
  değerlendirilecek.

## [1.9.0] - 2026-04-27 — Engine v2: system fonts + 8 new analyzers

### Added — System fonts
- **`discover_system_fonts()`** — Windows `C:/Windows/Fonts/`, macOS
  `/System/Library/Fonts/` + `/Library/Fonts/`, Linux `/usr/share/fonts/`
  taranır. TTF/OTF binary `name` ve `OS/2` tabloları stdlib ``struct`` ile
  okunur (yeni dep yok). Family + Regular/Bold/Italic/BoldItalic variant
  gruplaması otomatik. fsType bit 1 (Restricted Embed) olan fontlar elenir
  → output PDF'lerde lisans güvenliği.
- **`resolve_system_font(family_id, bold, italic)`** + ``resolve_editor_font``
  artık ``"system:arial"`` gibi id'leri çözüyor (graceful fallback chain).
- **``editor_font_catalog()`` artık merged liste**: önce bundled (Noto/
  DejaVu, kategori `bundled`), sonra sistem fontları (`system`).
- Test makinasında **147 sistem fontu** + 6 bundled = **153 family** keşfedildi.

### Added — 8 yeni public helper (PDF Intelligence Engine v2)
1. **`extract_metadata(input)`** — Info-dictionary + structural counts
   (title/author/subject/keywords/creator/dates/page_count/encrypted).
2. **`set_metadata(input, output, **kwargs)`** — yeni metadata yaz.
3. **`extract_outline(input)`** — TOC/bookmark hiyerarşisini düz liste
   olarak (`{level, title, page, y}`) döner.
4. **`find_text(input, query, *, case_sensitive, whole_words, max_pages,
   max_results)`** — sayfa-sayfa metin arama; her eşleşme için bbox + 60-char
   context.
5. **`extract_images(input, output_dir, *, min_size, page)`** — gömülü
   raster'ları tek tek dosya olarak çıkar; xref dedupe; CMYK→RGB; minimum
   boyut filtresi.
6. **`pdf_thumbnail(input, output, *, page_no, dpi, fmt)`** — tek sayfa
   PNG/JPG render.
7. **`detect_text_columns(page)`** — span x0 histogramından 1/2/3 sütun
   tahmini.
8. **`detect_headers_footers(input)`** — sayfaların üst %10 / alt %10
   şeritlerinde tekrar eden satırları bulur (digit normalization ile
   "Sayfa 3" + "Sayfa 4" eşleşir).
- **`deep_analyze(input)`** — yukarıdakileri + `classify_pdf_extractability`
  birleştirir; per-page `width/height/rotation/char_count/image_count/
  columns` bilgisi de döner. Editor PDF açılışında tek call.

### Added — Yeni endpoint'ler
- `POST /pdf/find` — JSON match list (page + bbox + context)
- `POST /pdf/outline` — TOC JSON
- `POST /pdf/metadata` (GET-style) — Info dict
- `POST /pdf/set-metadata` — yeni PDF döner
- `POST /pdf/extract-images` — ZIP (X-Image-Count header)
- `POST /pdf/thumbnail` — PNG/JPG image
- `POST /pdf/deep-analyze` — tüm intelligence rapor

Toplam ``/pdf/*`` endpoint sayısı: **34** (Engine v2 öncesi 27).

### Tests
- **33 yeni test** (`tests/test_pdf_engine.py`): system font discovery +
  cache, metadata roundtrip, outline, find_text, image extraction (her
  filtre dahil), thumbnail (PNG + invalid DPI), columns/headers/footers
  detection, deep_analyze. Plus cross-PDF smoke test üzerinde 6 örnek
  PDF'i deep_analyze ile gezer.
- Suite total **229 yeşil** (önceden 196).

### Notes
- Sistem fontu kullanımı yasal olarak temiz: kullanıcı kendi makinesinde
  kuruluyu kullanıyor (Word/Acrobat ile aynı pratik), output PDF'e
  PyMuPDF subset olarak gömüyor → çıktı self-contained.
- fsType=Restricted (0x0002) fontlar otomatik eleniyor → embedding hak
  ihlali riski yok.
- Engine artık "main motor" rolünde: editor + PDF Tools + cross-cut tüm
  primitive'leri ortak kullanıyor.

## [1.8.0] - 2026-04-27 — PDF Intelligence Engine + Editor precision

This release elevates the PDF analysis primitives we built for the editor's
"replace" mode into a shared **engine** that the rest of the app reuses.

### Added — Yeni public helpers (core.py "PDF Intelligence")
- **`classify_pdf_extractability(input)`** — `{type: vector|image|hybrid|empty,
  total_pages, pages_with_text, pages_with_only_images, total_chars,
  extractable, message}`. Replace mode'un destek olmadığı PDF'leri (taranmış,
  vektör-only) önceden tespit eder; hata mesajı kullanıcı dostu.
- **`extract_text_spans(input, *, granularity, merge_adjacent, max_pages)`**
  — `granularity` parametresi:
  - `"word"` → mevcut span davranışı (her kelime ayrı)
  - `"line"` → aynı satırdaki span'lar tek entry'de (varsayılan)
  - `"block"` → aynı paragraf tek entry'de
  `merge_adjacent` (default `True`): aynı satırdaki aynı font/boyut/renk
  parçaları otomatik birleştirir (sözleşmelerde "tarafından imzalanmıştır"
  gibi öbekleri tek tıklamayla seçilebilir hale getirir).
- **`font_glyph_coverage(font_buffer, text)`** — `(covered, total)`. PyMuPDF
  `Font.has_glyph(cp)` ile **doğru** kapsama kontrolü.

### Changed — Editor precision
- **DPR scaling**: pdf.js canvas'ı `devicePixelRatio × scale` boyutunda
  render ediliyor (cap 3, bellek koruma). Retina/4K ekranda 2-3× daha
  keskin önizleme. Tüm coordinate dönüşümleri `_bitmapPerPoint() = scale ×
  dpr` üzerinden geçiyor.
- **Background sampling**: Replace ops için `_sample_bg_color(page, rect)`
  — rect'in 4 kenar strip'inde 72 DPI sampling, mode color → redact fill.
  Renkli zeminde **beyaz leke kalmıyor**.
- **Embedded font reuse + glyph coverage check**: Replace path orijinal PDF
  embedded font'u extract eder, glyph coverage kontrolü yapar, eksik
  glyph varsa otomatik bundled Noto fallback'e düşer. Subset font tofu
  riskini ortadan kaldırır.
- **Granularity radio**: Replace modunda Kelime / Satır / Paragraf seçimi
  (default Satır). Granularite değişince spans yeniden çekilir.
- **PDF type badge**: Topbar'da Vector / Image / Mixed / Empty etiketi
  (renk-kodlu). Image-only PDF'te replace modu net uyarı mesajıyla
  reddedilir, ama annot/overlay modları hâlâ kullanılabilir.
- **MIME type fix** (taşıma): `.mjs` artık `text/javascript` olarak servis
  ediliyor (önceden `text/plain` olduğu için modül silently fail oluyordu).
- **Editor full-screen**: Modal `100vw × 100vh`, topbar (başlık + Aç/
  Kaydet/Kapat), sidebar (collapsible `<details>` grupları), mobile için
  hamburger drawer (899px altı).
- **`button.primary` global stilinin topbar'a sızması**: explicit override
  (`width:auto`, height:32px) — Kaydet butonu artık makul boyutta.

### Cross-cut integration (yeni kullanım yerleri)
- `pdf_to_markdown` artık `classify_pdf_extractability` ile preflight check
  yapıyor — image-only PDF'te "boş .md" yerine net hata.

### Added — Yeni endpoint
- **`POST /pdf/extractability`** — bağımsız hızlı tip kontrolü; PDF Tools'un
  diğer dönüşümleri de bu primitive'i kullanabilir.
- `POST /pdf/edit/spans` artık `granularity` + `merge_adjacent` parametreleri
  alıyor, response'a `extractability` bilgisi de ekliyor. `X-Editor-Phase: 4e`.

### Tests
- **16 yeni test** (`tests/test_pdf_editor.py`): extractability classifier
  (vector/image/empty), 3 granularite davranışı, glyph coverage (full +
  missing chars), `/pdf/extractability` endpoint, `pdf_to_markdown`'un
  image-only PDF'i reddetmesi. Suite total **196 yeşil**.

### Notes
- Tüm yeni stringler `static/i18n.js`'de — 0 hardcoded TR/EN.
- Mevcut motorumuzun "main engine" hâline geldiği faz: `extract_text_spans`,
  `classify_pdf_extractability`, `font_glyph_coverage` artık hem editor hem
  PDF Tools tarafında ortak primitive olarak kullanılıyor.

## [1.7.0] - 2026-04-27 — PDF Editor Phase 4d (smart replace)

### Added — Mevcut metni tıkla-değiştir
- "Mevcut Metni Değiştir" üst-modu canlı. PDF açıldığında arka planda
  `/pdf/edit/spans` endpoint'i çağrılır, sayfa-sayfa metin parçaları
  (font, boyut, renk, bold, italic) çıkarılır. Replace modunda her span
  hover-able dikdörtgen olarak gösterilir; tıklanan span için orijinal metni
  ön-doldurulmuş ve eşleşen font/stille stillenmiş inline editor açılır.
- **Akıllı font matching:** Orijinal PDF'in font adından (örn.
  `Arial-BoldMT`, `TimesNewRomanPS-Italic`, `Courier-Bold`) bizim bundled
  paketimizdeki en yakın aile + bold/italic bayrağı tahmin edilir
  (`core._map_font_name_to_family`).
- **Yeni op tipi `replace`:** `add_redact_annot(rect, fill=(1,1,1))` ile
  orijinal glyph'leri görsel + içerik akışından siler, sayfa başına tek
  `apply_redactions()` çağrısı (performans), ardından
  `insert_text(...)` ile yeni metni eşleşen font + boyut + renkle aynı
  konuma yerleştirir.
- **Yeni endpoint `/pdf/edit/spans`** — PDF'i alır, sayfa-sayfa span
  metadata'sı döner: `{page, rect, text, font_name, font_id, fontsize,
  color, bold, italic}`.
- **`core.extract_text_spans(input_path, max_pages=None)`** + 
  **`core._map_font_name_to_family()`** + 
  **`core._apply_replace_ops_for_page()`** helper'ları.
- Boş yeni metin = sadece silme: orijinal kaldırılır, yerine bir şey eklenmez.

### Frontend
- Replace mode görsel: aktif span'ın altı/üstü mavi outline; commit edilen
  replace op'u kırmızı strikethrough + dashed outline + yeni metin label'ı.
- Per-page "Geri Al" / "Sayfayı Temizle" replace op'larını da destekler.

### Tests
- 11 yeni test (`tests/test_pdf_editor.py`): span çıkarma, font name
  mapping (Helvetica/Arial/Times/Courier), replace round-trip (text
  swapping + boş silme), `/pdf/edit/spans` endpoint, geçersiz rect
  atlama. Suite total **180 yeşil**.

### Notes
- **Phase 4 (PDF Editor) tamamlandı.** Tüm 4 mod canlı: viewer + annot +
  overlay + smart replace.
- Tüm yeni stringler `static/i18n.js` STRINGS / PATTERNS sözlüklerinde —
  hardcoded TR/EN yok.

## [1.6.0] - 2026-04-27 — PDF Editor Phase 4c (overlay modes)

### Added — Yeni metin / şekil ekleme aktif
- "Metin / Şekil Ekle" üst-modu canlı; alt modlar:
  - **Metin (T)** — canvas üzerinde tıkla, açılan inline textarea'da yaz,
    Enter ile onayla. Font ailesi, boyutu, rengi, kalın, italik tüm seçimler
    metne uygulanır. Backend `page.insert_text()` + bundled TTF kullanır;
    Türkçe glyph'ler %100 doğru.
  - **Dikdörtgen (▭) / Elips (◯)** — sürükle, dolgu opsiyonel, kenar genişliği
    ayarlanabilir.
  - **Çizgi (—)** — iki nokta arasına düz çizgi.
- 4 yeni op tipi `core.apply_editor_operations`'a eklendi:
  `text` (`page.insert_text`), `rect` (`page.draw_rect`),
  `ellipse` (`page.draw_oval`), `line` (`page.draw_line`).
- **Font kataloğu family-bazlı.** `core.editor_font_catalog()` sadece diskte
  bulunan TTF'leri döner; her family'nin `variants: ["regular", "bold",
  "italic", "bolditalic"]` listesi var. Frontend buna göre Bold/Italic
  checkbox'larını gate'liyor (variant yoksa disabled).
- **`core.resolve_editor_font(family_id, bold, italic)`** — graceful fallback:
  istenen variant → family'nin regular'ı → Noto Sans → sistem fontu → None.
- Inline text editor (`spawnTextEditor`): pdf.js canvas'ının üstünde absolute
  positioned textarea, anlık font/size/color/style senkronizasyonu, Enter
  commit / Esc iptal.

### Changed
- `/pdf/edit/fonts` artık family + variants döner (eski item-flat liste yerine).
  `X-Editor-Phase: 4c`.
- `core.py` "16. Editor operations" bölümü `EDITOR_FONT_FAMILIES` global
  listesi + 2 yeni helper içeriyor; eski `_EDITOR_FONT_CATALOG` (app.py'da)
  emekli edildi.

### Tests
- 11 yeni test (`tests/test_pdf_editor.py`): text/rect/ellipse/line için
  uygulama doğrulaması, geçersiz girişlerin atlanması, font katalog +
  resolver davranışı, `/pdf/edit/fonts` yeni şema.
- Suite total **169 yeşil**.

### Notes
- Phase 4d (mevcut metni tıkla → değiştir, akıllı font matching) sıradaki.
- Tüm yeni stringler `static/i18n.js` STRINGS sözlüğünde — sıfır hardcoded.

## [1.5.0] - 2026-04-27 — PDF Editor Phase 4b (annotation modes)

### Added
- **Annotation modu canlı.** Editor modal'inde "Vurgu / Not" üst-modu altında
  6 alt mod aktif: vurgu, altçizgi, üstçizgi, sticky note, serbest çizim, ve
  görsel/imza ekleme.
- **`core.apply_editor_operations(input, output, operations)`** — frontend'in
  ürettiği operasyon listesini PyMuPDF annotation primitive'lerine dönüştürür:
  - `highlight` → `add_highlight_annot`
  - `underline` → `add_underline_annot`
  - `strikeout` → `add_strikeout_annot`
  - `sticky` → `add_text_annot` (içerik zorunlu)
  - `ink` → `add_ink_annot` (en az 1 stroke + 2 nokta)
  - `image` → `insert_image` (PNG/JPG/WebP data URL ile)
- **Hata izolasyonu:** Bir operasyon başarısız olursa diğerleri devam eder;
  cevap header'ında `X-Operations-Applied`, `X-Operations-Skipped` ve ilk
  hatanın özeti `X-First-Error` olarak döner.
- **`/pdf/edit/save`** stub'tan gerçek uygulayıcıya geçti; `X-Editor-Phase: 4b`.
- **Frontend canvas overlay sistemi** (`static/pdf-editor.mjs`):
  - pdf.js render canvas'ının üstünde ikinci canvas (`peOverlayCanvas`)
  - Mouse + touch event handler'ları her mod için ayrı (drag rect, click,
    free-draw)
  - Her sayfa için ayrı operasyon listesi; sayfa değiştirince overlay yeniden
    çizilir
  - Coordinate dönüşümü: canvas px ↔ PDF point (yakınlaştırma uyumlu)
  - Live preview: drag sırasında dashed rect, ink çizimi sırasında stroke
- **Geri Al / Sayfayı Temizle** butonları her sayfanın operasyon yığını için.
- **Sticky not içeriği** için inline `prompt()` (4c'de zenginleşecek).
- **Görsel/imza ekleme:** önce dosya seç, sonra canvas'ta dikdörtgen sürükle.

### Tests
- 10 yeni annotation testi (`tests/test_pdf_editor.py`) — her tip için
  uygulama doğrulaması, geçersiz girişlerin atlanması, parsiyel hata raporu.
- Suite total **158 yeşil**.

### Notes
- Phase 4c (overlay = yeni metin/şekil ekleme) ve Phase 4d (replace = mevcut
  metni font matching ile değiştirme) ayrı sürümlerde gelecek.
- Tüm string'ler `static/i18n.js`'in STRINGS / PATTERNS sözlüklerinden
  geliyor — hardcoded TR/EN if/else yok.

## [1.4.0] - 2026-04-27

### Added — PDF Editor (Phase 4a — viewer + plumbing)
- Header'da yeni **🖊 PDF Düzenle** butonu, ona bağlı tam-genişlikli editor
  modal (`pdfEditorModalBack`).
- Sol tarafta düzenleme modu seçici (Vurgu / Not, Metin / Şekil, Mevcut
  Metni Değiştir — modlar 4b/4c'de canlanıyor), font ailesi/boyutu/
  rengi/kalın/italik kontrolleri ve yakınlaştırma.
- Sağ tarafta canlı pdf.js canvas viewer: dosya seç, sayfa nav (önceki/
  sonraki), zoom in/out (%75-%200 preset + ince ayar).
- **`scripts/setup_editor_assets.py`** — pdf.js v4.10.38 + Noto Sans/Serif/
  Mono + DejaVu fontlarını CDN'den indirip ``static/pdfjs/`` ve
  ``static/fonts/`` altına yerleştiren kurulum scripti. ``build_portable.py``
  artık asset'leri eksikse otomatik indirir.
- **Bundled font pack:** Noto Sans / Serif / Mono (4 stil + 2 stil mono) +
  DejaVu Sans / Serif / Mono — toplam 14 TTF, ~9 MB. Tüm ileride üretilecek
  PDF'lerde (xhtml2pdf, watermark, page numbers, header/footer) artık ilk
  tercih edilen font Noto Sans (Türkçe glyph kapsamı %100).
- **Yeni endpoint'ler:**
  - `GET /pdf/edit/fonts` — frontend'in font seçicisini dolduran katalog;
    yalnızca diskte gerçekten bulunan TTF'ler listelenir.
  - `POST /pdf/edit/save` — PDF + ``operations`` JSON listesi alır; **Phase
    4a stub'ı** olarak operasyonları sayar ama uygulamadan PDF'i compact
    olarak yeniden kaydedip döner. Response header'larda
    ``X-Operations-Applied`` / ``X-Operations-Received`` /
    ``X-Editor-Phase: 4a`` raporlanır.
- **`static/pdf-editor.mjs`** — ES module; pdf.js'i lazy yükler, dosya
  açma / sayfa render / zoom / pagination / font katalog fetch'i yönetir.
- **i18n:** 30+ yeni TR↔EN string + 4 yeni dinamik regex pattern (sayfa
  bilgisi, hata mesajları). Hiçbir string hardcoded değil — tümü
  `static/i18n.js` STRINGS / PATTERNS sözlüklerinde.

### Added — Other
- 8 yeni editor testi (`tests/test_pdf_editor.py`); suite total **148 yeşil**.

### Changed
- `build_portable.py` artık ``core.py``, ``state.py``, ``settings.py``
  dosyalarını da kopyalıyor (önceden eksikti); ``ensure_editor_assets()``
  helper'ı kopya öncesinde asset bootstrap'i tetikliyor.

### Notes
- Phase 4a tamamen altyapı: gerçek düzenleme henüz yok, **viewer hazır**.
- Phase 4b: annotation modu (vurgu, sticky note, çizim, imza görseli).
- Phase 4c: overlay modu (yeni metin / şekil ekle).
- Phase 4d: replace modu (mevcut metni değiştir + akıllı font matching).

## [1.3.0] - 2026-04-27

### Added
- **Section C (light) — yerel AI / heuristic özellikler.** Hiçbiri model
  indirmesi gerektirmez; saf pymupdf + Pillow + regex:
  - **Boş Sayfa Bul** (`/pdf/detect-blank`) — text + pixel-histogram melez
    heuristik: önce ``page.get_text()`` ile metin olup olmadığına bakar
    (hızlı yol), metin yoksa düşük DPI'de render edip ≥240 gri tonlu pixel
    oranını kontrol eder.
  - **Boş Sayfa Sil** (`/pdf/remove-blank`) — bulduğu boş sayfaları çıkarıp
    yeni PDF üretir; ``X-Pages-Kept`` / ``X-Pages-Removed`` response
    header'larıyla raporlar.
  - **İmza Tespiti** (`/pdf/detect-signatures`) — ``page.widgets()`` ile imza
    form alanları + ``doc.get_sigflags()`` ile dijital imza bayrağı tarar;
    JSON ``{is_signed, field_count, filled_count, digital_signature, fields}``.
  - **Otomatik Kategorizasyon** (`/pdf/classify`) — kural tabanlı; PDF metnini
    9 kategori için (fatura / dekont / sözleşme / ekstre / fiş / mektup /
    rapor / form / kimlik) regex koleksiyonuyla skorlar, "diğer" varsayılan.
- UI: PDF Araçları modaline 4 yeni kart + JSON cevaplı araçlar için inline
  sonuç göstericisi (`renderJsonResult`).

### Changed
- `core.py`'a "15. AI helpers (Section C — light)" bölümü.
- Front-end submit handler ``Content-Type: application/json`` cevaplarını
  inline gösterir (boş sayfa listesi, imza özeti, kategori skoru); PDF/CSV/MD
  cevapları eskisi gibi indirilir.

### Notes
- Faz 3a (light AI) yeni runtime dep eklemez. Faz 3b (PII — Presidio + Türkçe
  BERT) ve Faz 3c (yerel LLM — llama-cpp-python + GGUF) ayrı sürümlerde
  gelecek; her ikisi de model indirmeyi ilk kullanımda tetikleyecek.

## [1.2.0] - 2026-04-27

### Added
- **PDF Araçları** modaline 7 yeni dönüşüm aracı (Section B). Tümü pip-wheel
  bağımlılığı; sıfır sistem deps:
  - **Görselden PDF** — JPG/PNG/WebP/BMP/TIFF/GIF → çok-sayfalı PDF
    (`core.image_to_pdf` + `/pdf/from-images`)
  - **Word'den PDF** (.docx) — `python-docx` ile okur, başlık / kalın / italik /
    altçizgi / tablolar korunur, xhtml2pdf ile render edilir
    (`core.docx_to_pdf` + `/pdf/from-docx`)
  - **Excel'den PDF** (.xlsx) — `openpyxl` ile okur, her sayfa ayrı bölüm
    olarak render edilir (`core.xlsx_to_pdf` + `/pdf/from-xlsx`)
  - **HTML → PDF** — xhtml2pdf'in CSS alt kümesi
    (`core.html_to_pdf` + `/pdf/from-html`)
  - **URL → PDF** — http(s) sayfasını indirir, HTML olarak render eder
    (`core.url_to_pdf` + `/pdf/from-url`); `file://`, `ftp://` engellenir
  - **PDF → Markdown** — yazı boyutu heuristic'i ile başlık seviyeleri tahmin
    edilir, kalın koşumlar ``**…**`` ile sarılır
    (`core.pdf_to_markdown` + `/pdf/to-markdown`)
  - **PDF → CSV** — PDF içindeki tabloları çıkarır; tek tablo seçilebilir veya
    hepsi birleştirilebilir; sınırlayıcı `,` `;` `\t` `|`
    (`core.pdf_to_csv` + `/pdf/to-csv`)
- xhtml2pdf'in Latin-1 sınırını aşmak için `pisaContext.__init__` runtime
  patch'i: sistem TTF'i bulduğunda `HTUni` ailesi olarak kaydeder; Türkçe
  glyph'ler (İ, ğ, ş, ç, Ö, Ü, …) doğru render edilir.
- 26 yeni test (`tests/test_pdf_conversions.py`); suite total 124 yeşil.
- Yeni runtime bağımlılıkları: `python-docx>=1.1`, `xhtml2pdf>=0.2.16`,
  `Pillow>=10.0` (önce easyocr üzerinden transitif geliyordu, artık explicit).

### Changed
- `core.py`'a "14. Conversion utilities (Section B)" bölümü ve ortak
  `_xhtml2pdf_render` helper'ı eklendi.
- `templates/index.html`'in `TOOLS` JS objesine 7 yeni araç tanımı; renderField
  ``textarea`` tipini destekliyor (HTML → PDF için).

## [1.1.0] - 2026-04-27

### Added
- **PDF Araçları** modal in the header — 13 generic-PDF utilities, all
  pure-Python (PyMuPDF only, no extra system dependencies):
  - **Birleştir** — concatenate multiple PDFs into one
  - **Böl** — split into ranges (`1-3,5,7-`) or one-file-per-page; output ZIP
  - **Sıkıştır** — image re-encode (JPEG quality + DPI cap) + garbage collect
  - **Şifrele / Şifre Kaldır** — AES-256, configurable print/copy/modify perms
  - **Metin Damga** — diagonal text watermark with arbitrary rotation,
    opacity, colour, font-size; Unicode-capable when a system TTF is found
  - **Görsel Damga** — PNG / JPG / WebP image watermark
  - **Sayfa Numarası** — configurable position, format string
    (`{n}`, `{total}`, `{page}`), font-size and colour
  - **Header / Footer** — constant top/bottom text on every page
  - **Kenar Kırp** — fixed margins (pt / mm / inç) off every page
  - **Döndür** — 90°/180°/270°, optionally per-page
  - **Sayfa Sırala** — drop / duplicate / reorder pages
  - **Sayfa Sil** — drop specified pages
- New endpoints: `/pdf/{merge,split,compress,encrypt,decrypt,watermark-text,watermark-image,page-numbers,header-footer,crop,rotate,reorder,delete-pages}`.
- 37 new tests covering both `core.pdf_*` helpers and HTTP endpoints
  (suite total: 98 tests).
- Turkish + English translations for the new tools modal.

## [1.0.0] - 2026-04-26

### Added
- Initial public release.
- PDF → Excel conversion with dedicated parser for structured call-log PDFs.
- PDF → Word conversion via `pdf2docx` (preserves editable text).
- PDF → JPG page-by-page render, downloadable as a single ZIP.
- OCR pipeline (EasyOCR, Turkish + English) for scanned PDFs.
- Batch operations: merge multiple PDFs into one Excel, deduplicate phone
  numbers, multi-column AND filtering.
- Team distribution (sequential / round-robin / weighted-random).
- Progressive Web App (PWA) — installable on mobile home screen.
- SQLite-backed conversion history.
- Live progress bar for OCR and batch jobs.
- Windows portable build (`build_portable.py`) — embedded Python, ~1.2 GB.
- Windows service installer with menu UI (`Servis Yoneticisi.bat` — install / start / stop / status / remove via NSSM).
- Single-menu portable build script (`Portable Paket.bat` — build / quick-update / 7z / Self-Extracting .exe).
- Optional self-signed HTTPS at startup (`HTTPS=1`).
- Structural PDF safety scan (`pdf_safety.py`) + optional ClamAV integration.
- Internationalisation (i18n) — Turkish + English UI with runtime language switch.

### Security
- Per-job upload size cap (`MAX_UPLOAD_MB`, default 2048 MB).
- Token-scoped temp directories with periodic cleanup (TTL 30 min).
- PDF structural scan flags `/JavaScript`, `/Launch`, `/EmbeddedFile`,
  `/RichMedia`, `/SubmitForm`, `/GoToR`, `/URI`, `/XFA`.

[Unreleased]: https://github.com/orhanenginokay/pdfconverter/compare/v1.10.0...HEAD
[1.10.0]: https://github.com/orhanenginokay/pdfconverter/compare/v1.9.1...v1.10.0
[1.9.1]: https://github.com/orhanenginokay/pdfconverter/compare/v1.9.0...v1.9.1
[1.9.0]: https://github.com/orhanenginokay/pdfconverter/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/orhanenginokay/pdfconverter/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/orhanenginokay/pdfconverter/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/orhanenginokay/pdfconverter/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/orhanenginokay/pdfconverter/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/orhanenginokay/pdfconverter/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/orhanenginokay/pdfconverter/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/orhanenginokay/pdfconverter/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/orhanenginokay/pdfconverter/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/orhanenginokay/pdfconverter/releases/tag/v1.0.0
