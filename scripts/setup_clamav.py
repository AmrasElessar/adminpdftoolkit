"""Download portable ClamAV (Windows x64) into ``./clamav/`` and pull
the initial signature database so the engine is ready before the server
starts.

Run once on a dev machine + during the portable build pipeline + by the
launcher (``Sunucuyu Başlat.bat`` / ``Admin PDF Toolkit Baslat.bat``)::

    python scripts/setup_clamav.py

Idempotent: skips the download if ``./clamav/clamscan.exe`` exists AND
the signature DB is present. Pass ``--force`` to re-download binaries
(database is preserved). Pass ``--skip-signatures`` to install binaries
only (lifespan thread will fetch sigs on first boot).

What's bundled (downloaded by this script)
------------------------------------------
- ``clamscan.exe``   — single-file scanner (used by ``pdf_safety.clamav_scan``)
- ``freshclam.exe``  — signature-DB updater (used by ``core.clamav_update``)
- All ``*.dll`` runtime libraries the ClamAV team ships in the official ZIP
- ``freshclam.conf`` — minimal config pointing at the official mirror
- ``database/main.cvd`` + ``daily.cvd`` + ``bytecode.cvd`` — pulled by
  freshclam after binaries land (~300 MB; takes 30-90 s on typical lines)

Linux / macOS
-------------
ClamAV on those platforms is typically installed via the system package
manager (``apt install clamav clamav-daemon`` / ``brew install clamav``),
so this script only handles Windows. On other OSes, ``pdf_safety`` will
fall back to whatever ``clamscan`` it finds on PATH; signature updates
are managed by the OS package.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# Force UTF-8 stdout so progress lines render on Windows cp1254 consoles.
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        with contextlib.suppress(Exception):
            _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CLAMAV_DIR = ROOT / "clamav"
DATABASE_DIR = CLAMAV_DIR / "database"

# Pin a known-good release. Bump after testing a new one against
# tests/test_pdf_safety.py + an end-to-end safety scan on a JS-embedded
# fixture. Releases: https://github.com/Cisco-Talos/clamav/releases
CLAMAV_VERSION = "1.4.2"
ZIP_URL = (
    f"https://github.com/Cisco-Talos/clamav/releases/download/"
    f"clamav-{CLAMAV_VERSION}/clamav-{CLAMAV_VERSION}.win.x64.zip"
)

FRESHCLAM_CONF = """# freshclam config bundled with admin-pdf-toolkit
# DatabaseDirectory is supplied via CLI (--datadir=...) by core.clamav_update
DatabaseMirror database.clamav.net
DNSDatabaseInfo current.cvd.clamav.net
LogTime yes
"""


def info(msg: str) -> None:
    print(f"[setup_clamav] {msg}")


_DB_FILES = ("main.cvd", "main.cld", "daily.cvd", "daily.cld")


def already_installed() -> bool:
    return (CLAMAV_DIR / "clamscan.exe").exists() and (CLAMAV_DIR / "freshclam.exe").exists()


def signatures_present() -> bool:
    if not DATABASE_DIR.is_dir():
        return False
    return any((DATABASE_DIR / f).exists() for f in _DB_FILES)


def _download(url: str, dest: Path) -> None:
    info(f"downloading {url}")
    info(f"  -> {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            written = 0
            with dest.open("wb") as fp:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    fp.write(chunk)
                    written += len(chunk)
                    if total:
                        pct = written / total * 100
                        print(
                            f"\r  {written / 1e6:6.1f} / {total / 1e6:.1f} MB ({pct:5.1f}%)",
                            end="",
                            flush=True,
                        )
            if total:
                print()  # newline after progress
        info(f"  downloaded {written / 1e6:.1f} MB")
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        info(f"  ! download failed: {e}")
        if dest.exists():
            dest.unlink()
        raise


def _extract(zip_path: Path, target: Path) -> None:
    """Extract the ZIP, flattening the top-level ``clamav-X.Y.Z`` directory
    so binaries land directly under ``target/``.

    Aggressive filter — we only keep what's needed to run ``clamscan`` and
    ``freshclam``. Everything else (debug symbols, static libs, headers,
    user-manual HTML, docs, examples) is dropped to keep the bundle ~50 MB
    instead of ~200 MB.
    """
    info(f"extracting {zip_path.name} → {target}")
    target.mkdir(parents=True, exist_ok=True)

    KEEP_PATTERNS = (".exe", ".dll")
    SKIP_DIR_FRAGMENTS = (
        "usermanual/",
        "conf_examples/",
        "/docs/",
        "etc/",
        "include/",
        "yara_examples/",
        "newsfeed/",
    )
    SKIP_FILE_SUFFIXES = (
        ".lib",
        ".pdb",
        ".exp",
        ".h",
        ".pc",
        ".md",
        ".txt",
        ".rst",
    )

    kept = 0
    skipped = 0
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.endswith("/"):
                continue
            parts = member.split("/", 1)
            rel = parts[1] if len(parts) == 2 and parts[0].startswith("clamav-") else member
            lower = rel.lower().replace("\\", "/")

            # Drop entire doc/manual/header/lib trees
            if any(frag in lower for frag in SKIP_DIR_FRAGMENTS):
                skipped += 1
                continue
            # Drop non-runtime file types
            if lower.endswith(SKIP_FILE_SUFFIXES) and not any(
                lower.endswith(k) for k in KEEP_PATTERNS
            ):
                skipped += 1
                continue

            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
            kept += 1
    info(f"  extraction done (kept {kept}, skipped {skipped})")


def _write_freshclam_conf() -> None:
    conf = CLAMAV_DIR / "freshclam.conf"
    if conf.exists():
        info("  freshclam.conf already exists — leaving it alone")
        return
    conf.write_text(FRESHCLAM_CONF, encoding="utf-8")
    info(f"  wrote {conf.name}")


def _write_marker() -> None:
    """Drop a small JSON next to the binary so we know which version landed."""
    marker = CLAMAV_DIR / "INSTALL_INFO.json"
    marker.write_text(
        json.dumps(
            {
                "version": CLAMAV_VERSION,
                "source": ZIP_URL,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _run_initial_freshclam(timeout: int = 600) -> bool:
    """Pull the signature DB synchronously so the server is fully armed
    before it starts answering requests.

    Returns True on success (or "already up to date"), False otherwise.
    Failure is non-fatal — pdf_safety degrades gracefully without sigs.
    """
    info("")
    info("Imza veritabani indiriliyor (~300 MB, 30-90 saniye sürebilir)...")
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    exe = CLAMAV_DIR / "freshclam.exe"
    if not exe.exists():
        info("  ! freshclam.exe yok — atlandi")
        return False

    cmd = [str(exe)]
    conf = CLAMAV_DIR / "freshclam.conf"
    if conf.exists():
        cmd += ["--config-file", str(conf)]
    cmd += [f"--datadir={DATABASE_DIR}", "--no-warnings"]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(CLAMAV_DIR),
            timeout=timeout,
            text=True,
            capture_output=True,
        )
    except subprocess.TimeoutExpired:
        info(f"  ! freshclam {timeout}s icinde bitiremedi — atlaniyor")
        return False
    except Exception as e:
        info(f"  ! freshclam calismadi: {e}")
        return False

    # exit 0 = updated, 1 = already up-to-date — both fine.
    if proc.returncode in (0, 1):
        info(f"  imza veritabani hazir (exit={proc.returncode})")
        return True

    tail = "\n".join(((proc.stdout or "") + (proc.stderr or "")).splitlines()[-10:])
    info(f"  ! freshclam exit={proc.returncode}")
    if tail:
        info("  son satirlar:")
        for line in tail.splitlines():
            info(f"    {line}")
    return False


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-download binaries even if ./clamav/ already has them. Database is preserved.",
    )
    p.add_argument(
        "--keep-zip",
        action="store_true",
        help="Keep the downloaded ZIP at clamav/_download.zip "
        "instead of deleting after extraction.",
    )
    p.add_argument(
        "--skip-signatures",
        action="store_true",
        help="Install binaries only; let the lifespan thread fetch "
        "the signature DB on first server boot.",
    )
    args = p.parse_args()

    if sys.platform != "win32":
        info(
            "Not Windows — skipping. ClamAV on Linux/macOS is expected to be "
            "installed via the system package manager."
        )
        return 0

    binaries_already = already_installed()
    sigs_already = signatures_present()

    # Fast path: everything's already in place.
    if binaries_already and sigs_already and not args.force:
        info(f"ClamAV already installed under {CLAMAV_DIR} (binaries + signatures).")
        return 0

    # Binaries: install if missing or --force
    need_binaries = (not binaries_already) or args.force
    if need_binaries:
        if args.force and CLAMAV_DIR.exists():
            info(f"--force: removing existing {CLAMAV_DIR}")
            # Preserve the database to avoid re-downloading 300 MB of sigs
            db_backup = None
            if DATABASE_DIR.exists():
                db_backup = ROOT / "_clamav_db_backup"
                if db_backup.exists():
                    shutil.rmtree(db_backup)
                shutil.move(str(DATABASE_DIR), str(db_backup))
                info("  database/ moved aside; will be restored after extract")
            shutil.rmtree(CLAMAV_DIR)
            if db_backup:
                CLAMAV_DIR.mkdir(parents=True, exist_ok=True)
                shutil.move(str(db_backup), str(DATABASE_DIR))

        zip_path = CLAMAV_DIR / "_download.zip"
        try:
            _download(ZIP_URL, zip_path)
            _extract(zip_path, CLAMAV_DIR)
        except Exception as e:
            info(f"FAILED: {e}")
            return 1
        finally:
            if zip_path.exists() and not args.keep_zip:
                zip_path.unlink()
                info(f"  removed {zip_path.name}")

        DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        _write_freshclam_conf()
        _write_marker()
        info(f"ClamAV {CLAMAV_VERSION} binaries installed under {CLAMAV_DIR}")
    else:
        info(f"ClamAV binaries already present under {CLAMAV_DIR}")

    # Signatures: pull synchronously unless explicitly skipped
    if args.skip_signatures:
        info("--skip-signatures: imza veritabani sonra (lifespan thread'inde) indirilecek.")
    elif not signatures_present():
        ok = _run_initial_freshclam()
        if not ok:
            info(
                "UYARI: Imza indirme basarisiz oldu. Yapisal kontrol + "
                "Defender ile devam edilebilir; ClamAV bir sonraki acilista "
                "tekrar deneyecek."
            )
    else:
        info("Imza veritabani zaten yerinde — atlandi.")

    info("")
    info("Hazir. Server'i baslatabilirsiniz.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
