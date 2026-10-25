"""Errors that are safe to show to the user, in both UI languages."""

from __future__ import annotations


class UserError(Exception):
    """A failure caused by the input, with a message fit for the end user.

    Anything else raised inside a job is logged and reported generically, so
    internal paths and tracebacks never reach the client.
    """

    def __init__(self, tr: str, en: str | None = None) -> None:
        super().__init__(tr)
        self.tr = tr
        self.en = en or tr

    def payload(self) -> dict[str, str]:
        return {"tr": self.tr, "en": self.en}
