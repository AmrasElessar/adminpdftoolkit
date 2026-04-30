"""Test session bootstrap.

S4 tightened production defaults: ``docs_url``/``redoc_url`` ship as ``None``
in the prod profile so the live deployment doesn't broadcast its API surface.
The test suite, however, relies on ``/docs`` and ``/openapi.json`` being
mounted (existing endpoints assert their availability), so we flip the
process into the dev profile *before any project module is imported*.

Same goes for the safety policy: tests want behaviour to be deterministic
regardless of what the operator configured locally, so we pin
``HT_SAFETY_POLICY=block_danger`` (the default — but explicit beats implicit
when running in CI).
"""

from __future__ import annotations

import os

os.environ.setdefault("HT_PROFILE", "dev")
os.environ.setdefault("HT_DOCS_URL", "/docs")
os.environ.setdefault("HT_REDOC_URL", "/redoc")
os.environ.setdefault("HT_SAFETY_POLICY", "block_danger")
