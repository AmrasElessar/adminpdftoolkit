"""Plugin-style PDF parsers.

The application identifies an uploaded PDF's *kind* (call-log, scanned page
image, generic table layout) by walking the parser registry and asking each
implementation whether the document matches. The first match wins.

Public surface:
  - ``classify(doc)``  -> matching parser (or None)
  - ``get_parser(name)`` -> parser by registered name
  - ``PARSERS`` (read-only) — the ordered registry list

To add a new parser, drop a module under ``parsers/`` defining a subclass of
``BaseParser`` and register it in ``parsers.registry``.
"""
from .base import BaseParser
from .registry import PARSERS, classify, get_parser

__all__ = ["BaseParser", "PARSERS", "classify", "get_parser"]
