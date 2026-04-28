"""Parser registry & dispatch.

Order matters: the first parser whose ``is_match`` returns True wins.
Most specific parsers are listed first; ``GenericTableParser`` sits at the
end as the fallback (always matches).
"""
from __future__ import annotations

from typing import Any

from .base import BaseParser
from .call_log_360 import CallLog360Parser
from .generic_table import GenericTableParser
from .scanned import ScannedParser


PARSERS: list[BaseParser] = [
    CallLog360Parser(),
    ScannedParser(),
    GenericTableParser(),
]


def classify(doc: Any) -> BaseParser | None:
    """Return the first parser whose ``is_match`` returns True, or None."""
    for parser in PARSERS:
        if parser.is_match(doc):
            return parser
    return None


def get_parser(name: str) -> BaseParser | None:
    """Lookup a parser by its ``name`` attribute."""
    for parser in PARSERS:
        if parser.name == name:
            return parser
    return None
