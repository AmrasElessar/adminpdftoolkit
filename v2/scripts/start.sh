#!/usr/bin/env sh
# Admin PDF Toolkit v2 — first run creates a virtualenv, later runs just start.
set -e
cd "$(dirname "$0")/../server"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install . ocrmypdf pikepdf pyhanko
fi
exec .venv/bin/python -m adminpdf --open "$@"
