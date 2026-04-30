"""Abstract parser interface.

Every concrete parser implements at minimum ``is_match`` (classification).
Specific parsers expose additional methods for the formats they understand
(``parse_records``, ``write_excel``, ``to_csv``, ``extract_rows``).

Callers use ``parsers.classify(doc)`` to dispatch and then check what the
returned parser supports — or, when the conversion target is fixed, look up
a specific parser via ``parsers.get_parser(name)``.
"""

from __future__ import annotations

from typing import Any


class BaseParser:
    """Base class for all PDF parsers.

    Subclasses set ``name`` and implement ``is_match``. Conversion methods
    are optional — only implement what the parser actually supports.
    """

    name: str = "base"

    def is_match(self, doc: Any) -> bool:
        """Return True if this parser handles the given fitz.Document."""
        return False

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r}>"
