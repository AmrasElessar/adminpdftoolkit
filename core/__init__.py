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
    WORK_DIR,
    STATE_DIR,
    HISTORY_DB_PATH,
    MAX_JOB_TIMEOUT_SECONDS,
    WORK_TTL,
    JOB_MEMORY_TTL,
    CLEANUP_INTERVAL,
    convert_jobs,
    batch_jobs,
    ocr_jobs,
    convert_lock,
    batch_lock,
    ocr_lock,
)

from .logging_setup import setup_logging, logger
from .errors import sanitize_error, MAX_ERROR_CHARS
from .jobs import (
    check_job_timeout,
    state_path,
    persist_job_state,
    load_persisted_state,
    drop_persisted_state,
    job_snapshot,
)
from .files import (
    safe_filename,
    assert_under_work,
    make_job_dir,
    save_upload,
    extract_generic_table,
)
from .cleanup import (
    cleanup_orphan_dirs,
    cleanup_job_memory,
    startup_cleanup,
    cleanup_loop,
)
from .history_db import (
    _migrate_legacy_history_db,
    init_history_db,
    log_history,
    _history_lock,
)
from .network import (
    client_ip,
    is_local_request,
    lan_ip,
    ensure_self_signed_cert,
    LOCAL_HOSTS,
)
from .security import check_token, _assert_public_url
from .distribution import (
    distribute_sequential,
    distribute_roundrobin,
    distribute_custom,
    normalize_phone,
)
from .ocr_preload import preload_ocr_in_background
from .batch import parse_pdf_for_batch
from .pdf_tools import (
    _find_unicode_font,
    _insert_text_unicode,
    _save_pdf,
    _parse_page_ranges,
    _position_xy,
    pdf_merge,
    pdf_split,
    pdf_compress,
    pdf_encrypt,
    pdf_decrypt,
    pdf_watermark_text,
    pdf_watermark_image,
    pdf_page_numbers,
    pdf_header_footer,
    pdf_crop,
    pdf_rotate,
    pdf_reorder_pages,
    pdf_delete_pages,
)
from .converters import (
    image_to_pdf,
    pdf_to_markdown,
    pdf_to_csv,
    html_to_pdf,
    url_to_pdf,
    docx_to_pdf,
    xlsx_to_pdf,
)
from .analysis import (
    detect_blank_pages,
    remove_blank_pages,
    detect_signatures,
    classify_pdf,
)
from .editor import (
    EDITOR_FONT_FAMILIES,
    _FONTS_DIR,
    _VALID_OPS,
    editor_font_catalog,
    resolve_editor_font,
    apply_editor_operations,
    extract_text_spans,
    classify_pdf_extractability,
    font_glyph_coverage,
    _map_font_name_to_family,
    _fit_fontsize_to_rect,
    _color_int_to_rgb,
    _coerce_rect,
    _coerce_point,
    _coerce_color,
    _parse_data_url,
    _apply_one_op,
    _apply_replace_ops_for_page,
    _try_extract_embedded_font,
    _sample_bg_color,
    _spans_share_style,
    _merge_consecutive_spans,
    _make_span_dict,
    _extract_line_spans,
    _extract_block_spans,
)
from .fonts import (
    discover_system_fonts,
    resolve_system_font,
    resolve_editor_font_with_system,
    editor_font_catalog_with_system,
)

# Override the bundled-only versions imported above from .editor so the
# package-level lookups (``core.resolve_editor_font`` /
# ``core.editor_font_catalog``) pick up the merged bundled+system catalog.
resolve_editor_font = resolve_editor_font_with_system  # type: ignore[assignment]
editor_font_catalog = editor_font_catalog_with_system  # type: ignore[assignment]

from .metadata import (
    extract_metadata,
    set_metadata,
    extract_outline,
    find_text,
    extract_images,
    pdf_thumbnail,
    detect_text_columns,
    detect_headers_footers,
    deep_analyze,
)

# Schema for non-call-log generic table mapping. Populated by app.py at
# import time; ``parse_pdf_for_batch`` reads it from the package namespace.
TARGET_SCHEMA: list[str] = []
