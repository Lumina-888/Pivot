"""Stable parse error codes (FR-DOC-004)."""

from __future__ import annotations

from dataclasses import dataclass

PARSE_CODES = frozenset(
    {
        "UNSUPPORTED_SCAN_PDF",
        "ENCRYPTED_FILE",
        "CORRUPTED_FILE",
        "EMPTY_TEXT",
        "UNSUPPORTED_EXTENSION",
        "RESOURCE_LIMIT",
        "PARTIAL_PAGE_FAILURE",
        "INVALID_FILE_SIGNATURE",
    }
)

RETRYABLE_CODES = frozenset(
    {
        "PROVIDER_TIMEOUT",
        "PROVIDER_RATE_LIMITED",
        "PROVIDER_TEMPORARY_ERROR",
        "RESOURCE_LIMIT",
    }
)


@dataclass(frozen=True)
class ParseError(Exception):
    code: str
    message: str
    retryable: bool = False

    def __str__(self) -> str:
        return self.message


def parse_error(code: str, message: str) -> ParseError:
    return ParseError(code=code, message=message, retryable=code in RETRYABLE_CODES)
