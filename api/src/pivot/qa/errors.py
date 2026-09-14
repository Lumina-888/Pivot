"""Writer failures use SPEC appendix B.1 codes. Messages never include secrets."""

from __future__ import annotations


class WriterError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
