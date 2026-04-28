# Roadmap

## v1.7 — Shipped (2026-04-27) — PDF Editor Phase 4d (smart replace) — **PDF Editor complete**

Mevcut metni tıkla → değiştir akışı canlı. Phase 4 fully shipped.

- ✅ `core.extract_text_spans` — sayfa-sayfa span metadata'sı
- ✅ `core._map_font_name_to_family` — orijinal PDF font adından bundled
  paketteki en yakın aile + bold/italic tahmini
- ✅ `core._apply_replace_ops_for_page` — sayfa başına tek
  `apply_redactions()` çağrısı (performans), sonra her replace için
  matched-font ile `insert_text`
- ✅ Yeni op: `replace` (redact + insert tek atomik akışta)
- ✅ Yeni endpoint: `/pdf/edit/spans` (sayfa-sayfa span listesi)
- ✅ Frontend: span hover-able outline, inline pre-filled editor, kırmızı
  strikethrough preview commit edilen replace op'u için
- ✅ 11 yeni test → toplam **180 yeşil**
- ✅ Sıfır hardcoded TR/EN; tüm yeni stringler i18n.js'de

## v1.6 — Shipped (2026-04-27) — PDF Editor Phase 4c (overlay)

Yeni metin / şekil ekleme modu canlı. PyMuPDF'in page-level drawing
primitive'lerini (`insert_text`, `draw_rect`, `draw_oval`, `draw_line`)
canvas overlay'e bağladık. Bundled font paketi tam kullanılıyor —
font/variant resolver `core.resolve_editor_font()` üzerinden.

- ✅ 4 yeni op tipi (`text`, `rect`, `ellipse`, `line`)
- ✅ Family-bazlı font kataloğu (`core.editor_font_catalog`) +
  `resolve_editor_font(family_id, bold, italic)` graceful fallback chain
- ✅ Frontend inline text editor: pdf.js canvas üstünde absolute textarea,
  Enter commit / Esc iptal, font/style senkronu
- ✅ Bold/Italic checkbox'ları family'nin variants listesine göre gate'leniyor
- ✅ 11 yeni test → toplam **169 yeşil**
- ✅ Tüm yeni stringler i18n.js sözlüğünde

## v1.5 — Shipped (2026-04-27) — PDF Editor Phase 4b (annotation)

Annotation modu canlı. PyMuPDF native annotation primitive'lerini frontend'in
canvas overlay sistemine bağladık. Operasyonlar tek bir POST'ta uygulanır,
hatalar izole edilir, kısmi sonuç raporlanır.

- ✅ `core.apply_editor_operations(input, output, ops)` — 6 op tipini
  `add_highlight_annot` / `add_underline_annot` / `add_strikeout_annot` /
  `add_text_annot` / `add_ink_annot` / `insert_image` çağrılarına dönüştürür.
- ✅ `/pdf/edit/save` artık gerçek uygulayıcı (Phase 4a stub'ı emekli);
  `X-Operations-Applied` / `X-Operations-Skipped` / `X-First-Error` /
  `X-Editor-Phase: 4b` header'ları.
- ✅ `static/pdf-editor.mjs` — overlay canvas, mouse + touch handler'ları,
  per-page operations state, geri al / sayfayı temizle, drag preview.
- ✅ Sticky not içerik prompt'u (4c'de zenginleşecek).
- ✅ Görsel/imza ekleme: dosya seç → canvas'ta dikdörtgen sürükle.
- ✅ Coordinate dönüşümü: canvas px ↔ PDF point, yakınlaştırma uyumlu.
- ✅ 10 yeni annotation testi → toplam **158 yeşil**.
- ✅ Tüm yeni stringler `static/i18n.js`'de — sıfır hardcoded TR/EN.

## v1.4 — Shipped (2026-04-27) — PDF Editor Phase 4a (viewer + plumbing)

A new "🖊 PDF Düzenle" header button opens a 3-mode editor (annot / overlay /
replace) backed by pdf.js for in-browser rendering and pymupdf for the
backend operations. Bundled with Noto + DejaVu font pack so all generated
text — including Turkish glyphs — renders identically across machines.

**Phase 4a — Shipped (viewer + plumbing)**:
- ✅ pdf.js v4.10.38 self-hosted under `static/pdfjs/` (loaded lazily on
  first modal open)
- ✅ Noto Sans / Serif / Mono + DejaVu Sans / Serif / Mono — 14 TTFs
  bundled under `static/fonts/`. `_find_unicode_font()` now prefers the
  bundled `NotoSans-Regular.ttf` so xhtml2pdf / watermark / page numbers
  use the same font on every host.
- ✅ `scripts/setup_editor_assets.py` — one-shot CDN downloader; runs
  automatically inside `build_portable.py`.
- ✅ Editor modal: file open, page navigation, zoom (75–200%), mode picker
  (inert until 4b), font selector populated from `/pdf/edit/fonts`.
- ✅ Backend: `GET /pdf/edit/fonts` (catalogue) and `POST /pdf/edit/save`
  (operation-list round-trip stub; returns input untouched, reports counts
  via `X-Operations-Applied` / `X-Editor-Phase: 4a` headers).
- ✅ `static/pdf-editor.mjs` — ES module orchestrating the viewer.
- ✅ i18n: 30+ TR↔EN strings + 4 dynamic regex patterns; nothing hardcoded.
- ✅ 8 yeni test (`tests/test_pdf_editor.py`); suite total **148 yeşil**.

**Phase 4b — Shipped in v1.5 (see above).**

**Phase 4c — Shipped in v1.6 (see above).**

**Phase 4d — Shipped in v1.7 (see above).**

## v1.3 — Shipped (2026-04-27) — Section C (light) — AI heuristics

The "model-free" slice of Section C: features that add real value without
adding any new dependency or pulling a model file. Each runs purely on
pymupdf + Pillow + regex.

- ✅ **Boş Sayfa Bul** — `core.detect_blank_pages` + `/pdf/detect-blank`
  (text-first hybrid: page is blank iff no extractable text *and* the
  rendered pixel histogram is ≥99.9% bright)
- ✅ **Boş Sayfa Sil** — `core.remove_blank_pages` + `/pdf/remove-blank`
  (X-Pages-Kept / X-Pages-Removed response headers)
- ✅ **İmza Tespiti** — `core.detect_signatures` + `/pdf/detect-signatures`
  (widget signature fields + ``doc.get_sigflags()`` digital signature
  bayrağı; JSON yanıt)
- ✅ **Otomatik Kategorizasyon** — `core.classify_pdf` + `/pdf/classify`
  (kural tabanlı; 9 kategori: fatura / dekont / sözleşme / ekstre / fiş /
  mektup / rapor / form / kimlik + "diğer"; her kategoriye ait regex
  koleksiyonu skoru ve eşleşme örnekleri JSON'da döner)
- ✅ UI: PDF Araçları modaline 4 yeni kart; submit handler JSON cevaplı
  araçlar için inline sonuç gösterici (boş sayfa listesi, imza özeti,
  kategori skor tablosu).
- ✅ 16 yeni test (`tests/test_pdf_ai.py`); suite total **140 yeşil**.

## v1.2 — Shipped (2026-04-27) — Conversion expansion (Section B)

All Section B items landed as additional cards inside the same "🛠 PDF Araçları"
modal. Pure-Python wheels only — no LibreOffice, no headless Chrome, no
system fonts required at runtime (Unicode TTFs are auto-detected, falling
back to Helvetica when none are present).

- ✅ **Image → PDF** — `core.image_to_pdf` + `/pdf/from-images`
  (JPG / PNG / WebP / BMP / TIFF / GIF, multi-image bundle)
- ✅ **.docx → PDF** — `core.docx_to_pdf` + `/pdf/from-docx`
  (`python-docx` → custom HTML emit → xhtml2pdf; headings, bold/italic/
  underline, tables; modern .docx only — old .doc rejected at boundary)
- ✅ **.xlsx → PDF** — `core.xlsx_to_pdf` + `/pdf/from-xlsx`
  (`openpyxl` data-only → HTML tables; one sheet section per visible sheet,
  optional ``sheet=`` filter; modern .xlsx only)
- ✅ **HTML → PDF** — `core.html_to_pdf` + `/pdf/from-html`
- ✅ **URL → PDF** — `core.url_to_pdf` + `/pdf/from-url` (http(s) only;
  ``file://`` / ``ftp://`` rejected; stdlib urllib, no httpx runtime dep)
- ✅ **PDF → Markdown** — `core.pdf_to_markdown` + `/pdf/to-markdown`
  (font-size heuristic for H1/H2/H3, bold runs wrapped in ``**…**``)
- ✅ **PDF → CSV** — `core.pdf_to_csv` + `/pdf/to-csv`
  (`pdfplumber`, single-table by index or all-tables concat)
- ✅ Runtime patch of `pisaContext.__init__` to register a Unicode TTF as
  ``HTUni`` — required to make Turkish glyphs survive xhtml2pdf's Latin-1
  default fonts; falls back gracefully when no system TTF is found.
- ✅ 26 yeni test (`tests/test_pdf_conversions.py`); suite total **124 yeşil**.
- ✅ Yeni runtime deps: `python-docx>=1.1`, `xhtml2pdf>=0.2.16`, `Pillow>=10.0`.

## v1.1 — Shipped (2026-04-27) — Generic-PDF utilities (Section A)

All Section A items from the v1.x candidate list landed as a single header-button
modal "🛠 PDF Araçları". Pure pymupdf, no new dependencies, no system deps.

- ✅ **PDF Birleştir** — `core.pdf_merge` + `/pdf/merge`
- ✅ **PDF Böl** — `core.pdf_split` + `/pdf/split` (range spec `"1-3,5,7-"`, ZIP output)
- ✅ **PDF Sıkıştır** — `core.pdf_compress` + `/pdf/compress`
  (image quality + DPI cap, X-Bytes-Before / X-Bytes-After response headers)
- ✅ **PDF Şifre Ekle / Kaldır** — `core.pdf_encrypt` + `/pdf/encrypt` (AES-256,
  configurable print/copy/modify perms), `core.pdf_decrypt` + `/pdf/decrypt`
- ✅ **Metin Damga** — `core.pdf_watermark_text` + `/pdf/watermark-text`
  (TextWriter + morph for arbitrary rotation, Unicode TTF auto-detect)
- ✅ **Görsel Damga** — `core.pdf_watermark_image` + `/pdf/watermark-image`
- ✅ **Sayfa Numarası** — `core.pdf_page_numbers` + `/pdf/page-numbers`
  (configurable position, format string `{n}` / `{total}` / `{page}`)
- ✅ **Header / Footer** — `core.pdf_header_footer` + `/pdf/header-footer`
- ✅ **Kenar Kırp** — `core.pdf_crop` + `/pdf/crop` (pt / mm / inç birim seçimi)
- ✅ **Döndür** — `core.pdf_rotate` + `/pdf/rotate` (per-page opsiyonel)
- ✅ **Sayfa Sırala** — `core.pdf_reorder_pages` + `/pdf/reorder` (drop / duplicate)
- ✅ **Sayfa Sil** — `core.pdf_delete_pages` + `/pdf/delete-pages`
- ✅ Ön yüz: header'da "🛠 PDF Araçları" butonu + 13 araç kartı + dinamik form
  + i18n (TR/EN) entegrasyonu
- ✅ 37 yeni test (`tests/test_pdf_utils.py`); suite total 98 yeşil

## v1.0 — Shipped (2026-04-26)

Done as of this release:

- ✅ Helper extraction → `core.py` (453 lines), `state.py`, `settings.py`
  (Pydantic Settings, `HT_*` env vars + `.env`)
- ✅ Persistent job state (`_work/_state/{kind}/{token}.json`) — server
  restarts don't strand polling clients
- ✅ Per-job hard timeout (`HT_MAX_JOB_TIMEOUT_SECONDS`, default 30 min)
- ✅ `_sanitize_error()` — strips Windows + POSIX paths, traceback prefixes
  from any error string sent to the client
- ✅ `/batch-convert` mapping JSON validation (typed dict + int parse + bound
  check at start, no IndexError mid-flight)
- ✅ `logger.exception()` everywhere a worker thread can fail
- ✅ Backend SSE: `/events/{kind}/{token}` (asyncio, push + heartbeat)
- ✅ Frontend SSE migration: `pollOrStream(kind, token, opts)` helper
  replaces all 3 polling loops; falls back to polling on EventSource error
  or absence
- ✅ Batch parallelisation: `ProcessPoolExecutor` with `parse_pdf_for_batch`
  worker in `core.py` (pickle-friendly), auto worker count
  (`min(cpu_count, 4)`), serial fallback below 4 PDFs and on pool failure
- ✅ OCR model preload at startup (daemon thread, opt-out via
  `HT_PRELOAD_OCR_MODEL=false`)
- ✅ `/health` returns uptime, thread count, work-dir bytes, free disk,
  per-kind running/total job counts
- ✅ `/docs` Swagger + `/redoc` ReDoc + `/openapi.json` enabled
- ✅ ARIA: every modal gets `role="dialog"` + `aria-modal="true"` +
  `aria-labelledby` at boot; `#status` and `#ocrStatus` are `aria-live="polite"`
- ✅ Keyboard: `:focus-visible` ring, ESC closes the top-most modal,
  freshly opened modals receive focus
- ✅ 48 tests (17 original + 31 new), all green
- ✅ i18n (Türkçe ⇄ English) — `static/i18n.js` with DOM walker,
  MutationObserver, snapshot stale-detection, modal innerHTML replacement
- ✅ Docker (multi-stage), docker-compose with healthcheck + named volumes
- ✅ CI/CD: `.github/workflows/ci.yml` (ruff lint+format, mypy, pytest +
  coverage on Linux/macOS/Windows × Python 3.11/3.12/3.13, Docker build)
- ✅ CodeQL weekly scan, Dependabot weekly updates (pip + actions + docker)

## v1.1 — Still optional (only do if a real user need surfaces)

These were *intentionally* left out of v1.0 because the trade-off didn't
favour shipping them, not because they were forgotten.

### `app.py` → `routers/` split
**Status:** all helpers already live in `core.py`; what remains in `app.py`
is the FastAPI app instance, lifespan, and ~25 endpoint handlers. Splitting
them into `routers/{convert,batch,ocr,preview,distribute,history}.py`
buys IDE-navigation comfort but no behaviour win — and the test suite
imports `from app import _apply_pipeline` etc., so every router file would
need re-export aliases.

**Gate to do it:** when adding a new endpoint becomes painful (>3 unrelated
files modified per change), or when a contributor explicitly asks.

### `pdf2docx` replacement
**Status:** still bundled. Upstream's last release was 2023 and PDF→Word
fidelity issues are an open category in real-world testing.

**Why deferred:** writing a replacement is a multi-week R&D project
(custom PyMuPDF + python-docx layout exporter, table/image handling, font
embedding). Forking pdf2docx itself would be cheaper but still substantial.

**Gate to do it:** when the next pdf2docx-related bug actually blocks a
real user (so far the bundled version works for our common shapes).

### Mobile virtual scroll for batch lists
**Status:** the batch file list renders all rows; >100 PDFs on a phone
slows the modal noticeably.

**Why deferred:** in practice nobody uploads 100+ PDFs from a phone — the
typical mobile flow is 1–5 files. Doing this now would be over-engineering
for a use case nobody hits.

**Gate to do it:** real telemetry (or a real complaint) showing users on
phones with 50+ files at once.

## v2.0 — Bigger swings (would change the app's shape)

- WebSocket bidirectional channel — replaces SSE, enables cancel/resume.
- Job state in a SQLite table proper (current per-token state.json works
  but isn't queryable for an admin dashboard).
- Multi-tenant: optional auth + per-user history (the app exists because
  uploads stay on-prem; multi-tenant would require an actual user model).
- IP rate-limiting (currently relies on the LAN being trusted).

## v1.x — Candidate generic-PDF features (under review)

Discussed informally; **constraint is hard: free + permissive licenses only,
no paid SDKs, no commercial SaaS, no proprietary models**. The project's
whole pitch is "offline + free + KVKK-safe", so this isn't negotiable.

Each item lists the library it would use and that library's license. All of
these are candidates only — none are committed to a release yet.

### A. Core PDF utilities — **✅ SHIPPED in v1.1 (2026-04-27)**

See the v1.1 section above for the per-item endpoint and helper-function map.

### B. Conversion expansion — **✅ SHIPPED in v1.2 (2026-04-27)**

See the v1.2 section above. The original LibreOffice / weasyprint plan was
swapped for pure-Python equivalents (`python-docx`, `openpyxl`, `xhtml2pdf`)
to honour the all-in-one / zero-system-dep constraint.

### C. AI / smart processing (all run **locally**, no cloud calls)

**Light (no model download) — ✅ SHIPPED in v1.3 (2026-04-27):**
- **Boş sayfa tespiti + sil** — text + pixel histogram heuristic.
- **İmza tespiti** — widget + `/SigFlags` check.
- **Otomatik kategorizasyon (rule-based)** — regex over text content.

**Heavy (model download on first use) — Phase 3b/3c, not yet shipped:**
- **PII maskeleme** ⭐⭐⭐ (Presidio + `dbmdz/bert-base-turkish-cased`,
  ~500 MB lazy download)
- **PDF özet** (`llama-cpp-python` + Mistral 7B GGUF Q4, ~4 GB lazy download)
- **PDF içinde semantik arama** (`chromadb` + sentence-transformers
  multilingual, ~500 MB lazy download)
- **Soru-cevap (chat with PDF)** — RAG combo of the two above.
- **AI-tabanlı kategorizasyon** (LLM prompt) — opsiyonel ek katman; v1.3'in
  rule-based kategorizasyonunu üzerine kurar.

### D. Comparison / archive utilities

- **PDF compare / diff** (sözleşme revizyonu için) — `pdfplumber` text diff +
  side-by-side render. Effort: 1 day.
- **Duplicate sayfa tespiti** — image hash via `Pillow`. Effort: 4 hours.
- **PDF versiyonlama / hash kayıt defteri** — pure SQLite, no new dep. Effort: 4 hours.

### E. Workflow

- **Webhook tetikleyici** ("PDF işlendi → Slack/email"). `httpx` already in deps.
  Effort: 4 hours.
- **Scheduler** ("her gece şu klasörü tara, yeni PDF'leri otomatik dönüştür")
  — `apscheduler` (MIT). Effort: 1 day.

### Forbidden — never recommend (paid / restrictive)

- Adobe PDF SDK
- Aspose.PDF / Aspose.Cells
- ABBYY FineReader / Cloud OCR
- iText 7 (dual-license commercial trap)
- LeadTools, PDFTron / Apryse
- Cloud LLM APIs (OpenAI, Anthropic Claude API, Azure OpenAI) — break the offline pitch
- Microsoft Office Interop (requires Office license per user)

## Will **not** be done

- Microservices split. The whole point of this app is a single ~80 MB
  Docker image / single 1.2 GB portable folder. Splitting backends would
  torpedo that.
- React/Vue rewrite. Vanilla JS keeps the bundle to one HTML file with no
  build step — a hard requirement for the portable target.
- Cloud-only mode. The app exists because uploaded files must stay on-prem.
