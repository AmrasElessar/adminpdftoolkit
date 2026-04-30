"""Sanity checks on the router split.

These guard against the silent failure mode where a router file is
written but never added to ``routers/__init__.ALL`` (or the inverse —
``ALL`` references a nonexistent module). They exercise the public
contract:

* every expected endpoint path is mounted on the FastAPI app
* every router exposes at least one route
* ``ALL`` and the modules it points at are consistent
"""

from __future__ import annotations

import app
from routers import ALL

# Snapshot of every public-facing endpoint after the S5 split.
# Keep this list in sync intentionally — adding a new endpoint should
# cost one line here, and removing one should require justifying the
# removal in the same PR.
EXPECTED_PATHS: tuple[str, ...] = (
    # Public landing + ops
    "/",
    "/health",
    # SSE
    "/events/{kind}/{token}",
    # Convert (sync + async)
    "/preview",
    "/convert",
    "/convert-start",
    "/convert-progress/{token}",
    "/convert-download/{token}",
    # OCR
    "/ocr-start",
    "/ocr-progress/{token}",
    "/ocr-download/{token}",
    # Batch
    "/batch-analyze",
    "/batch-files",
    "/batch-progress/{token}",
    "/batch-files-download/{token}",
    "/batch-convert",
    "/batch-preview/{token}",
    "/batch-deduplicate/{token}",
    "/batch-undeduplicate/{token}",
    "/batch-filter-options/{token}",
    "/batch-filter/{token}",
    "/batch-download/{token}",
    "/batch-distribute/{token}",
    "/batch-distribute/{token}/team/{team_idx}",
    "/batch-distribute/{token}/download",
    # PDF tools
    "/pdf/merge",
    "/pdf/split",
    "/pdf/compress",
    "/pdf/encrypt",
    "/pdf/decrypt",
    "/pdf/watermark-text",
    "/pdf/watermark-image",
    "/pdf/page-numbers",
    "/pdf/header-footer",
    "/pdf/crop",
    "/pdf/rotate",
    "/pdf/reorder",
    "/pdf/delete-pages",
    "/pdf/from-images",
    "/pdf/to-markdown",
    "/pdf/to-csv",
    "/pdf/from-docx",
    "/pdf/from-xlsx",
    "/pdf/from-html",
    "/pdf/from-url",
    "/pdf/find",
    "/pdf/outline",
    "/pdf/metadata",
    "/pdf/set-metadata",
    "/pdf/extract-images",
    "/pdf/thumbnail",
    "/pdf/deep-analyze",
    "/pdf/extractability",
    "/pdf/detect-blank",
    "/pdf/remove-blank",
    "/pdf/detect-signatures",
    "/pdf/classify",
    "/pdf/batch",
    # Editor
    "/pdf/edit/fonts",
    "/pdf/edit/spans",
    "/pdf/edit/save",
    # History + admin
    "/history",
    "/admin/enable-mobile",
    "/admin/disable-mobile",
    "/admin/mobile-status",
)


def _mounted_paths() -> set[str]:
    return {r.path for r in app.app.routes if hasattr(r, "path")}


def test_every_expected_path_is_mounted() -> None:
    mounted = _mounted_paths()
    missing = [p for p in EXPECTED_PATHS if p not in mounted]
    assert not missing, f"Missing endpoints after router split: {missing}"


def test_no_duplicate_paths_across_routers() -> None:
    """If two routers both declare ``/foo``, the second silently shadows
    the first. Cheaper to fail loud here than to debug a missing endpoint
    in production."""
    seen: dict[str, str] = {}
    for r in ALL:
        for route in r.routes:
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None)
            if path is None:
                continue
            for m in methods or {"<no-method>"}:
                key = f"{m} {path}"
                assert key not in seen, (
                    f"Duplicate route across routers: {key} (first in {seen[key]}, repeated in {r})"
                )
                seen[key] = repr(r)


def test_every_router_has_routes() -> None:
    """A router file that ships with zero routes is dead weight that's
    almost certainly a bug — flag it."""
    for r in ALL:
        assert len(r.routes) > 0, f"Router {r} has zero routes"


def test_all_tuple_matches_expected_count() -> None:
    """Pin the count so adding a router without updating ``ALL`` (or vice
    versa) shows up immediately in CI."""
    # 7 routers as of the S5 split: history, admin, ocr, convert, batch,
    # pdf_tools, editor.
    assert len(ALL) == 7
