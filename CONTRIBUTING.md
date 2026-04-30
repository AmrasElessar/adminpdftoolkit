# Contributing to Admin PDF Toolkit

[🇬🇧 English](#english) · [🇹🇷 Türkçe](#türkçe)

---

## English

Thanks for taking the time to contribute! This document describes how to set up
the development environment and the standards we follow.

### Development setup

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/<your-username>/pdfconverter.git
cd pdfconverter

# 2. Create a virtual environment (Python 3.11+ required)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Install dev dependencies
pip install -r requirements-dev.txt

# 4. Install pre-commit hooks
pre-commit install

# 5. Run the test suite
pytest

# 6. Start the dev server
python app.py
# → http://127.0.0.1:8000
```

### Branching & commits

- Work on a feature branch: `feat/<short-description>` or `fix/<short-description>`.
- Keep commits focused; one logical change per commit.
- Use [Conventional Commits](https://www.conventionalcommits.org/) when possible:
  - `feat:` new feature
  - `fix:` bug fix
  - `docs:` documentation only
  - `refactor:` code change without behaviour change
  - `test:` add or fix tests
  - `chore:` build / tooling
  - `perf:` performance improvement
  - `security:` security-related change

### Code style

- **Formatter & linter:** [Ruff](https://docs.astral.sh/ruff/) (configured in `pyproject.toml`).
- **Type checker:** [mypy](https://mypy.readthedocs.io/).
- **Line length:** 100 characters.
- **Quotes:** double.

Run locally before pushing:

```bash
ruff check .
ruff format --check .
mypy .
pytest --cov=. --cov-report=term-missing
```

`pre-commit` will run the relevant subset on every commit.

### Pull requests

1. Make sure CI is green (linting, types, tests).
2. Add or update tests for any behaviour change.
3. Update `CHANGELOG.md` under the `[Unreleased]` section.
4. Update both the Turkish and English sections of `README.md` when documentation changes.
5. Add or update UI strings in **both** `tr` and `en` dictionaries (`templates/index.html` → `window.I18N`).
6. Fill in the PR template; describe the *why*, not just the *what*.
7. One reviewer approval is required before merging.

### Reporting bugs / requesting features

Please use the GitHub issue templates:

- 🐛 **Bug report** — include reproduction steps, expected vs. actual behaviour, environment.
- ✨ **Feature request** — describe the use-case, not just the proposed solution.

For **security** issues, do **not** open a public issue — see [SECURITY.md](SECURITY.md).

### Code of Conduct

This project adheres to the [Contributor Covenant v2.1](CODE_OF_CONDUCT.md).
By participating you agree to uphold it.

---

## Türkçe

Katkı sağlamak için zaman ayırdığın için teşekkürler! Bu dokümanda geliştirme
ortamının nasıl kurulacağı ve uyduğumuz standartlar yazılı.

### Geliştirme kurulumu

```bash
# 1. GitHub'da repoyu fork'la, sonra fork'unu clone'la
git clone https://github.com/<kullanıcı-adın>/pdfconverter.git
cd pdfconverter

# 2. Sanal ortam oluştur (Python 3.11+ gerekli)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Geliştirme bağımlılıklarını kur
pip install -r requirements-dev.txt

# 4. Pre-commit hook'larını yükle
pre-commit install

# 5. Testleri çalıştır
pytest

# 6. Geliştirme sunucusunu başlat
python app.py
# → http://127.0.0.1:8000
```

### Branch ve commit kuralları

- Feature branch'inde çalış: `feat/<kısa-açıklama>` veya `fix/<kısa-açıklama>`.
- Commit'leri odaklı tut; commit başına tek bir mantıksal değişiklik.
- Mümkünse [Conventional Commits](https://www.conventionalcommits.org/) kullan:
  - `feat:` yeni özellik
  - `fix:` hata düzeltmesi
  - `docs:` sadece dokümantasyon
  - `refactor:` davranış değişmeyen kod düzenleme
  - `test:` test ekle/düzelt
  - `chore:` build/araç
  - `perf:` performans iyileştirmesi
  - `security:` güvenlikle ilgili değişiklik

### Kod stili

- **Formatlayıcı + linter:** [Ruff](https://docs.astral.sh/ruff/) (`pyproject.toml` içinde).
- **Tip denetleyici:** [mypy](https://mypy.readthedocs.io/).
- **Satır uzunluğu:** 100 karakter.
- **Tırnak:** çift.

Push'lamadan önce yerelde çalıştır:

```bash
ruff check .
ruff format --check .
mypy .
pytest --cov=. --cov-report=term-missing
```

`pre-commit` her commit'te ilgili kontrolleri otomatik çalıştırır.

### Pull request

1. CI'ın yeşil olduğundan emin ol (lint, tip, test).
2. Davranış değişikliği için test ekle/güncelle.
3. `CHANGELOG.md` içinde `[Unreleased]` başlığı altına ekle.
4. Doküman değişikliğinde `README.md` içindeki Türkçe ve İngilizce bölümlerin ikisi de güncellensin.
5. UI metinlerini hem `tr` hem `en` sözlüğüne ekle (`templates/index.html` → `window.I18N`).
6. PR şablonunu doldur; *ne yaptığını* değil, *neden yaptığını* yaz.
7. Merge için bir reviewer onayı gerekli.

### Hata bildirimi / özellik isteği

GitHub issue şablonlarını kullan:

- 🐛 **Bug report** — adımlar, beklenen vs. gerçekleşen, ortam bilgisi.
- ✨ **Feature request** — sadece çözümü değil, kullanım senaryosunu da anlat.

**Güvenlik** açıkları için public issue açma — [SECURITY.md](SECURITY.md)'ye bak.

### Davranış Kuralları

Bu proje [Contributor Covenant v2.1](CODE_OF_CONDUCT.md)'i benimser.
Katkı sağlayarak bu kurallara uyacağını kabul etmiş olursun.
