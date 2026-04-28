"""Application-wide logging configuration."""

from __future__ import annotations

import logging
import os


def setup_logging() -> logging.Logger:
    """Configure application-wide logging.

    Honours the LOG_LEVEL env var (DEBUG/INFO/WARNING/ERROR), defaulting
    to INFO. Idempotent.
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    else:
        root.setLevel(level)
    return logging.getLogger("ht_pdf")


logger = setup_logging()
