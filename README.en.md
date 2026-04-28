# Admin PDF Toolkit · _by Engin_

[🇬🇧 English](README.en.md) · [🇹🇷 Türkçe](README.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/orhanenginokay/pdfconverter/actions/workflows/ci.yml/badge.svg)](https://github.com/orhanenginokay/pdfconverter/actions/workflows/ci.yml)
[![CodeQL](https://github.com/orhanenginokay/pdfconverter/actions/workflows/codeql.yml/badge.svg)](https://github.com/orhanenginokay/pdfconverter/actions/workflows/codeql.yml)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**LAN-first, offline, open-source PDF processing pipeline.**
Designed for in-house corporate use: uploaded files never leave the
machine, the server is reachable from phones / desktops on the local
network, no third-party service dependencies.

> AGPL-3.0 · © 2026 Orhan Engin Okay

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python app.py                       # http://127.0.0.1:8000
```

Docker:
```bash
docker compose up -d
```

Portable Windows build (no install / Python / internet required on the
target machine):
```cmd
Portable Paket.bat        REM single menu: build · update · 7z · SFX-EXE
```

## Security

This is the project's primary design priority — built for compliance-
sensitive in-house deployments:

- **Runs offline.** Uploaded files never leave the machine; the OCR
  model is downloaded on first use, after that no internet is required.
- **Multi-layered PDF safety scanner.** Structural scanner (`/JavaScript`,
  `/OpenAction`, `/Launch` markers) plus optional ClamAV and Windows
  Defender (`MpCmdRun.exe`). Policy via `HT_SAFETY_POLICY=off|warn|block_danger`,
  default **block_danger**.
- **SSRF guard:** URL→PDF refuses private/loopback/link-local targets.
- **XFF guard:** `X-Forwarded-For` is honoured only from trusted proxies
  (`HT_TRUSTED_PROXIES`); empty by default → header always ignored.
- **Symlink defense:** Every job directory is opened through a single
  `make_job_dir` gate; symlinks escaping the work directory are refused.
- **Mobile-auth middleware:** Non-loopback clients pass with a
  one-shot token; comparison is constant-time (`hmac.compare_digest`).
- **Output sanitisation:** Error messages strip absolute paths and user
  directories before leaving the server.

External validation: VirusTotal 0/72, MetaDefender 0/21, enterprise
Kaspersky clean.

## Features

**Conversion**
- PDF → Excel/Word/JPG (specialised parser for call-log PDFs, generic
  table parser as fallback)
- OCR (EasyOCR · Turkish + English), models pulled to local cache on
  first use

**PDF tools (33+ endpoints)**
Merge, split, compress, AES-256 encrypt/decrypt, text/image watermark,
page numbers, header/footer, crop, rotate, reorder, delete pages,
image→PDF, docx/xlsx/html/url→PDF, PDF→Markdown, PDF→CSV, find,
outline, metadata read/write, extract images, thumbnail, deep-analyze,
extractability, blank detect/remove, signature detect, automatic
category (invoice/receipt/contract/…), batch dispatcher.

**PDF Editor**
- Viewer: pdf.js, page nav, zoom, font picker (Noto/DejaVu bundled)
- Annotation: highlight / underline / strike / sticky / freehand /
  image-as-signature
- Overlay: text (full Turkish support), rect / ellipse / line
- Smart replace: click existing text → edit → write back preserving
  the original font, size and colour
- Per-page undo / clear-page operation stack

**Batch & distribution**
- N PDFs → one merged Excel
- Phone-number deduplication (first occurrence wins)
- Multi-column AND filtering
- Team distribution: sequential / round-robin / custom ratio

**Platform**
- PWA (Add to Home Screen on mobile), responsive UI
- Live progress (polling + SSE)
- SQLite-backed action history
- Runtime TR/EN UI switch

## Project layout

```
app.py             # FastAPI bootstrap (lifespan + middleware + /, /health)
app_http.py        # HTTP helpers shared by routers
core/              # Pure-helper package (logging, errors, jobs, files, cleanup,
                   #   history_db, network, security, distribution, ocr_preload,
                   #   batch, pdf_tools, converters, analysis, editor, fonts, metadata)
state.py           # Shared state + JobStore wrapper
settings.py        # pydantic-settings (HT_* env vars, dev/prod profile)
routers/           # FastAPI routers (convert, batch, ocr, pdf_tools, editor, history, admin)
pipelines/         # Background workers (convert, batch_convert, ocr)
parsers/           # PDF parser registry (call-log, scanned, generic)
pdf_converter.py   # Core conversion functions
pdf_safety.py     # Structural + ClamAV + Defender PDF safety scanner
templates/         # index.html (vanilla, i18n)
static/            # PWA manifest, icons, fonts, pdf.js, sw.js
tests/             # 379 tests, ~66% coverage
scripts/           # setup_editor_assets.py, check_packaging.py
build_portable.py  # Portable build script
Dockerfile         # Multi-stage production image
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest --cov=. --cov-fail-under=62
```

Suite: 372 tests, **65%+ branch coverage**. Coverage:
- Unit: parser registry, distribution algorithms, app_http helpers,
  JobStore, sanitize_error, token validation, persistent state recovery
- Integration: every endpoint contract, OCR / convert / batch workers
  (EasyOCR stubbed), batch pipeline (load_job / save_view /
  load_distribution), sync convert (Excel/Word/JPG renderers), preview
  classifier, mobile-auth middleware, PDF safety gate
- Security: SSRF, XFF spoof, symlink escape, danger-PDF reject, error
  sanitisation
- Maintainability: router registration drift, packaging drift
  (`scripts/check_packaging.py`)

CI gates: ruff lint+format · mypy (strict-not-yet, but errors fail) ·
pytest cov-fail-under=62 · packaging drift gate · Docker build · CodeQL.

## Development setup

PDF editor assets (pdf.js + fonts) are not committed to git; run once
after a fresh clone:

```bash
python scripts/setup_editor_assets.py
```

The portable build (`Portable Paket.bat` or `python build_portable.py`)
runs this automatically.

## Run as a Windows service

```cmd
Servis Yoneticisi.bat       REM as Administrator: install · start · stop · status · remove
```

## License

**GNU AGPL-3.0** — open source, free, modifiable. Derivative work must
also ship under AGPL-3.0; serving over a network requires offering the
source. Full text: [LICENSE](LICENSE) · Third-party:
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## Disclaimer

Software is provided **"AS IS"**. All data-processing, transmission and
loss risks are the user's sole responsibility; back up important data
before use.

## Contributing

PRs welcome — please read [CONTRIBUTING.md](CONTRIBUTING.md) first. By
participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
For bugs / feature requests use the [issue templates](.github/ISSUE_TEMPLATE/);
for security vulnerabilities see [SECURITY.md](SECURITY.md) (do **not**
open a public issue).

---

**by Orhan Engin Okay** · 2026
