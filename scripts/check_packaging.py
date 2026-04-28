"""Packaging-drift gate.

Both ``Dockerfile`` and ``build_portable.py`` (and ``Portable Paket.bat``)
hand-roll the file list they ship — adding a new top-level Python module
or directory means remembering to update every one of them. This has
already drifted twice (``core.py`` / ``state.py`` / ``settings.py`` were
silently missing from the Docker image; the S5 split's ``app_http.py``
plus ``routers/``/``pipelines/`` were missing from all three).

Run this from CI on every PR so the next drift fails the build instead
of an end user. Standalone Python — no third-party deps.

Exit codes:
  0 — every required source file/dir is referenced everywhere it must be
  1 — at least one drift detected; details printed to stderr
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Top-level Python modules that must ship in every distribution. New
# files added at the project root should be appended here.
REQUIRED_FILES: tuple[str, ...] = (
    "app.py",
    "app_http.py",
    "state.py",
    "settings.py",
    "pdf_converter.py",
    "pdf_safety.py",
    "requirements.txt",
)

# Top-level packages that must ship — empty package dirs are excluded.
REQUIRED_DIRS: tuple[str, ...] = (
    "core",
    "routers",
    "pipelines",
    "parsers",
    "templates",
    "static",
)
# Note: ``clamav/`` is intentionally NOT required — operators run
# ``scripts/setup_clamav.py`` on the build machine to populate it. Builds
# without it still ship; ``pdf_safety`` falls back to system clamscan.

# Distribution targets we audit. Each entry maps a source-of-truth file
# to the list of REQUIRED_FILES + REQUIRED_DIRS it must mention. Some
# targets only need the ``files`` set, some need both — the third tuple
# element flags which list applies (``"both"`` / ``"files"``).
TARGETS: tuple[tuple[str, str], ...] = (
    ("Dockerfile", "both"),
    ("build_portable.py", "both"),
    ("Portable Paket.bat", "both"),
)


def _read(path: Path) -> str:
    """Read with errors='replace' so the .bat file's mixed encoding
    doesn't blow up on a non-Windows runner."""
    return path.read_text(encoding="utf-8", errors="replace")


def _check_target(target_path: Path, required: tuple[str, ...],
                    label: str) -> list[str]:
    """Return a list of strings missing from ``target_path``."""
    if not target_path.exists():
        return [f"target file {target_path} does not exist"]
    text = _read(target_path)
    return [name for name in required if name not in text]


def main() -> int:
    failed = False
    for target_name, scope in TARGETS:
        target = ROOT / target_name
        required: list[str] = []
        if scope in ("files", "both"):
            required.extend(REQUIRED_FILES)
        if scope in ("dirs", "both"):
            required.extend(REQUIRED_DIRS)
        missing = _check_target(target, tuple(required), target_name)
        if missing:
            failed = True
            print(f"[FAIL] {target_name} is missing references to:",
                  file=sys.stderr)
            for m in missing:
                print(f"   - {m}", file=sys.stderr)
        else:
            print(f"[ok]   {target_name} references every required file/dir")

    if failed:
        print(
            "\nFix: edit the listed file(s) and add the missing entries. "
            "Each new top-level Python module or package needs to be "
            "explicitly named in Dockerfile / build_portable.py / "
            "'Portable Paket.bat'.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
