"""Background OCR-model preload helper."""

from __future__ import annotations

import time

from .logging_setup import logger


def preload_ocr_in_background() -> None:
    """Warm up the EasyOCR model so the first user-triggered OCR is fast."""
    try:
        from pdf_converter import get_ocr_reader

        t0 = time.time()
        get_ocr_reader()
        logger.info("OCR model preloaded in %.1fs", time.time() - t0)
    except Exception as e:
        logger.warning("OCR preload failed (will retry on first request): %s", e)
