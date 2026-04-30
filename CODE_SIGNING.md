# Code Signing Policy

Bu sayfa Admin PDF Toolkit'in kod imzalama politikasını tanımlar.
SignPath Foundation tarafından zorunlu kılınan bilgileri içerir.

> 🐚 **Free code signing provided by [SignPath.io](https://about.signpath.io/),
> certificate by [SignPath Foundation](https://signpath.org/).**

---

## Project

- **Name:** Admin PDF Toolkit
- **Repository:** https://github.com/AmrasElessar/adminpdftoolkit
- **License:** [AGPL-3.0-or-later](LICENSE) (OSI-approved, single-license, no
  commercial dual-licensing).
- **Maintained by:** Orhan Engin Okay
- **Built from source via:** GitHub Actions (`.github/workflows/`) — every
  signed artifact is reproducible from the public repo.

The toolkit ships zero proprietary or closed-source components. Bundled
third parties are listed in [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md)
and run under their own free/open licenses (PyMuPDF AGPL, pdf2docx GPL,
ClamAV GPL, EasyOCR Apache, FastAPI MIT, etc.).

---

## Team & Roles

The project is currently maintained solo by Orhan Engin Okay; the same
person fills all SignPath roles below. If/when the team grows, this
section will list distinct accounts per role.

| Role | Person | GitHub | Responsibility |
|---|---|---|---|
| **Committer** | Orhan Engin Okay | [@AmrasElessar](https://github.com/AmrasElessar) | Authors source changes |
| **Reviewer** | Orhan Engin Okay | [@AmrasElessar](https://github.com/AmrasElessar) | Reviews PRs / direct commits |
| **Approver** | Orhan Engin Okay | [@AmrasElessar](https://github.com/AmrasElessar) | Approves each release for signing |

All accounts have **Multi-Factor Authentication (MFA) enabled** on GitHub
as required by SignPath Foundation.

---

## Signing Policy

- Only artifacts built by the project's GitHub Actions workflow from
  `main` (or release tags `vX.Y.Z`) on the official repository are
  eligible for signing.
- Every signing request is **manually approved** by the Approver before
  the SignPath signing service runs.
- Local developer builds are **never** sent for signing.
- Signed artifacts:
  - `Sunucuyu Başlat.bat` (launcher)
  - `Servis Yoneticisi.bat` (service installer)
  - `Engellemeyi Kaldir.bat` (MotW remover helper)
  - `Portable Paket.bat` (portable build script)
  - Future `Admin_PDF_Toolkit_Portable.exe` (PyInstaller bundle)

---

## Privacy Policy

Admin PDF Toolkit is an **offline-first local tool**. It does not
collect, transmit, or store any user data on remote servers — every PDF
the user opens stays on their machine.

Specifically:

- **No telemetry** is sent to any server.
- **No user accounts** or authentication providers — the tool runs
  loopback-only by default; LAN access is opt-in and gated by a local
  token (see [SECURITY.md](SECURITY.md)).
- **Network traffic** the tool initiates is limited to:
  - First-run downloads (Python packages via pip, ClamAV signature DB
    via `freshclam`, EasyOCR model on first OCR use). All endpoints are
    public, third-party, well-known.
  - User-explicit fetches (e.g. converting a `https://` URL the user
    typed into the "URL → PDF" tool).
- **Crash logs** stay on the user's machine under `_work/logs/`.

The project does not retain any data submitted via the SignPath
application process beyond what GitHub already publishes about the
public repository.

---

## Reporting

Security or signing-policy concerns: open an issue at
https://github.com/AmrasElessar/adminpdftoolkit/issues/new
or email the maintainer per [SECURITY.md](SECURITY.md).
