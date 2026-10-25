# Contributing to Admin PDF Toolkit

[🇬🇧 English](#english) · [🇹🇷 Türkçe](#türkçe)

---

## English

Thanks for taking the time to contribute!

### Development setup

```bash
git clone https://github.com/<your-username>/adminpdftoolkit.git
cd adminpdftoolkit

# Server (Python 3.11+)
cd server
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest

# Web UI (Node 20+)
cd ../web
npm ci
npm run dev        # hot reload on :5173, proxies /api to :8000
npm run build      # writes server/adminpdf/web_dist

# Run the app
cd ../server && python -m adminpdf --open
```

Optional system tools for the full test suite: Tesseract (+`tur`), Ghostscript, qpdf, LibreOffice.

### Adding a tool

Every tool is one `Operation` subclass in `server/adminpdf/ops/` (organisation-specific workflows go to
`server/adminpdf/plugins/`). Modules are discovered automatically — no router or registry edits. The
`Params` model drives validation **and** the generated UI form; give every field Turkish and English
labels with `Field(tr=..., en=...)`, raise `UserError(tr, en)` for user-caused failures, and bound every
input. See [ARCHITECTURE.md](ARCHITECTURE.md).

### Checks (CI runs the same)

```bash
cd server && ruff check . && ruff format --check . && mypy adminpdf && pytest
cd web && npm run check && npm run build
```

### Branching, commits and pull requests

- Feature branches (`feat/...`, `fix/...`); [Conventional Commits](https://www.conventionalcommits.org/).
- Add or update tests for every behaviour change.
- Update `CHANGELOG.md` under `[Unreleased]`.
- User-facing strings in **both** Turkish and English (`Field(tr=, en=)` on the server, `t("tr", "en")` in the UI).
- Keep the UI keyboard-accessible; the WCAG 2.1 AA audit (`web/e2e/a11y.mjs`) runs in CI.
- Fill in the PR template; explain the *why*.

### Releasing

1. Set `VERSION` in `server/adminpdf/config.py` (and `server/pyproject.toml`, `web/package.json`)
   and move `[Unreleased]` in `CHANGELOG.md` to a `[x.y.z]` section; merge to `main`.
2. Run the **Release** workflow on `main` with *publish* ticked (Actions → Release → Run workflow),
   or push a `vX.Y.Z` tag. It builds the self-contained Windows package and the Linux/macOS package,
   starts both as a smoke test and publishes the GitHub release (creating the tag if needed).

### Licensing

By contributing you agree that your contribution is licensed under AGPL-3.0. Only free / open-source
dependencies compatible with AGPL-3.0 are accepted; no cloud APIs (the application must work offline).

---

## Türkçe

Katkı için teşekkürler!

### Geliştirme ortamı

```bash
git clone https://github.com/<kullanici-adiniz>/adminpdftoolkit.git
cd adminpdftoolkit

# Sunucu (Python 3.11+)
cd server && pip install -e ".[dev]" && pytest

# Arayüz (Node 20+)
cd ../web && npm ci && npm run dev    # :5173 üzerinde canlı geliştirme
npm run build                          # server/adminpdf/web_dist içine

# Uygulamayı çalıştır
cd ../server && python -m adminpdf --open
```

### Yeni araç eklemek

Her araç `server/adminpdf/ops/` altında tek bir `Operation` sınıfıdır (kuruma özel iş akışları
`server/adminpdf/plugins/` altına). Modüller otomatik bulunur. `Params` modeli hem doğrulamayı hem
arayüz formunu üretir; her alana `Field(tr=..., en=...)` ile Türkçe ve İngilizce etiket verin,
kullanıcı kaynaklı hatalarda `UserError(tr, en)` kullanın, tüm girdileri sınırlayın.

### Kontroller

```bash
cd server && ruff check . && ruff format --check . && mypy adminpdf && pytest
cd web && npm run check && npm run build
```

### Dal, commit ve PR

- `feat/...`, `fix/...` dalları; Conventional Commits.
- Her davranış değişikliğine test.
- `CHANGELOG.md` → `[Unreleased]`.
- Kullanıcıya görünen metinler **hem Türkçe hem İngilizce**.
- Arayüz klavyeyle kullanılabilir kalmalı; WCAG 2.1 AA denetimi CI'da çalışır.

### Sürüm çıkarma

1. `server/adminpdf/config.py` içindeki `VERSION`'ı (ve `server/pyproject.toml`, `web/package.json`)
   güncelleyin, `CHANGELOG.md`'de `[Unreleased]` bölümünü `[x.y.z]` yapın; `main`'e birleştirin.
2. `main` üzerinde **Release** iş akışını *publish* işaretli çalıştırın (Actions → Release → Run
   workflow) ya da `vX.Y.Z` etiketi gönderin. Windows paketi ve Linux/macOS paketi derlenir, ikisi de
   açılıp denenir ve GitHub release'i yayımlanır (etiket yoksa oluşturulur).

### Lisans

Katkılarınız AGPL-3.0 ile lisanslanır. Yalnızca AGPL-3.0 uyumlu ücretsiz/açık kaynak bağımlılıklar
kabul edilir; bulut API'leri kullanılmaz (uygulama çevrimdışı çalışmalıdır).
