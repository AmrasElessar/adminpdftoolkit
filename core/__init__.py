"""Shared helpers used across endpoints — package facade.

This file's only job is to re-export the public symbols of every submodule
so that callers can keep using ``import core`` / ``from core import X`` /
``core.X`` exactly as before. The actual implementation lives in:

  - ``logging_setup`` — application-wide logger
  - ``errors``       — sanitize_error + MAX_ERROR_CHARS
  - ``jobs``         — in-memory + on-disk job state
  - ``files``        — safe filename, upload streaming, table extract helper
  - ``cleanup``      — orphan-dir / stale-job sweeper
  - ``history_db``   — SQLite history log
  - ``network``      — client_ip, lan_ip, self-signed cert
  - ``security``     — token validation + SSRF guard
  - ``distribution`` — record distribution algorithms + phone normalize
  - ``ocr_preload``  — background OCR-model preload
  - ``batch``        — process-pool batch PDF parser
  - ``pdf_tools``    — Section A: merge, split, compress, encrypt, watermark, …
  - ``converters``   — Section B: image/docx/xlsx/html/url → PDF, pdf → md/csv
  - ``analysis``     — Section C: blank-page / signature / categorisation
  - ``editor``       — Phase 4b annotation operations + extractability
  - ``fonts``        — system-font discovery + merged catalog
  - ``metadata``     — metadata, outline, search, image extract, layout

Tests / routers / app.py monkeypatch ``core.X`` to swap behaviour; that
contract still works because every name listed below lands in this
module's namespace via ``from .submod import ...``.
"""

from __future__ import annotations

# State constants and globals re-exported here for ``core.X`` access from
# routers + tests (e.g. ``monkeypatch.setattr(core, 'STATE_DIR', tmp_path)``).
from state import (
    BASE_DIR,
    CLEANUP_INTERVAL,
    HISTORY_DB_PATH,
    JOB_MEMORY_TTL,
    MAX_JOB_TIMEOUT_SECONDS,
    STATE_DIR,
    WORK_DIR,
    WORK_TTL,
    batch_jobs,
    batch_lock,
    convert_jobs,
    convert_lock,
    ocr_jobs,
    ocr_lock,
)

from .analysis import (
    classify_pdf,
    detect_blank_pages,
    detect_signatures,
    remove_blank_pages,
)
from .batch import parse_pdf_for_batch
from .cleanup import (
    cleanup_job_memory,
    cleanup_loop,
    cleanup_orphan_dirs,
    startup_cleanup,
)
from .converters import (
    docx_to_pdf,
    html_to_pdf,
    image_to_pdf,
    pdf_to_csv,
    pdf_to_markdown,
    url_to_pdf,
    xlsx_to_pdf,
)
from .distribution import (
    distribute_custom,
    distribute_roundrobin,
    distribute_sequential,
    normalize_phone,
)
from .editor import (
    _FONTS_DIR,
    _VALID_OPS,
    EDITOR_FONT_FAMILIES,
    _apply_one_op,
    _apply_replace_ops_for_page,
    _coerce_color,
    _coerce_point,
    _coerce_rect,
    _color_int_to_rgb,
    _extract_block_spans,
    _extract_line_spans,
    _fit_fontsize_to_rect,
    _make_span_dict,
    _map_font_name_to_family,
    _merge_consecutive_spans,
    _parse_data_url,
    _sample_bg_color,
    _spans_share_style,
    _try_extract_embedded_font,
    apply_editor_operations,
    classify_pdf_extractability,
    editor_font_catalog,
    extract_text_spans,
    font_glyph_coverage,
    resolve_editor_font,
)
from .errors import MAX_ERROR_CHARS, sanitize_error
from .files import (
    assert_under_work,
    extract_generic_table,
    make_job_dir,
    safe_filename,
    save_upload,
)
from .fonts import (
    discover_system_fonts,
    editor_font_catalog_with_system,
    resolve_editor_font_with_system,
    resolve_system_font,
)
from .history_db import (
    _history_lock,
    _migrate_legacy_history_db,
    init_history_db,
    log_history,
)
from .jobs import (
    check_job_timeout,
    drop_persisted_state,
    job_snapshot,
    load_persisted_state,
    persist_job_state,
    state_path,
)
from .logging_setup import logger, setup_logging
from .network import (
    LOCAL_HOSTS,
    client_ip,
    ensure_self_signed_cert,
    is_local_request,
    lan_ip,
)
from .ocr_preload import preload_ocr_in_background
from .pdf_tools import (
    _find_unicode_font,
    _insert_text_unicode,
    _parse_page_ranges,
    _position_xy,
    _save_pdf,
    pdf_compress,
    pdf_crop,
    pdf_decrypt,
    pdf_delete_pages,
    pdf_encrypt,
    pdf_header_footer,
    pdf_merge,
    pdf_page_numbers,
    pdf_reorder_pages,
    pdf_rotate,
    pdf_split,
    pdf_watermark_image,
    pdf_watermark_text,
)
from .security import _assert_public_url, check_token

# Override the bundled-only versions imported above from .editor so the
# package-level lookups (``core.resolve_editor_font`` /
# ``core.editor_font_catalog``) pick up the merged bundled+system catalog.
resolve_editor_font = resolve_editor_font_with_system  # type: ignore[assignment]  # noqa: F811
editor_font_catalog = editor_font_catalog_with_system  # type: ignore[assignment]  # noqa: F811

from .metadata import (
    deep_analyze,
    detect_headers_footers,
    detect_text_columns,
    extract_images,
    extract_metadata,
    extract_outline,
    find_text,
    pdf_thumbnail,
    set_metadata,
)

# Schema for non-call-log generic table mapping. Populated by app.py at
# import time; ``parse_pdf_for_batch`` reads it from the package namespace.
TARGET_SCHEMA: list[str] = []
