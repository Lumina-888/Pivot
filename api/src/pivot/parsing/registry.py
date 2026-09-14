"""Pluggable parser registry (SPEC §6.1)."""

from __future__ import annotations

from collections.abc import Mapping

from pivot.parsing.errors import parse_error
from pivot.parsing.mineru import MinerUCloudParser, MinerUHttpClient
from pivot.parsing.models import ParsedDocument
from pivot.parsing.office import DocxParser, PptxParser, XlsxParser
from pivot.parsing.pdf import PdfParser

_WHITELIST = ("pdf", "docx", "pptx", "xlsx")


class ParserRegistry:
    def __init__(self, parsers: Mapping[str, object] | None = None) -> None:
        self._parsers = dict(
            parsers
            or {
                "pdf": PdfParser(),
                "docx": DocxParser(),
                "pptx": PptxParser(),
                "xlsx": XlsxParser(),
            }
        )

    def parse(self, kind: str, content: bytes) -> ParsedDocument:
        parser = self._parsers.get(kind)
        if parser is None:
            raise parse_error("UNSUPPORTED_EXTENSION", f"无解析器: {kind}")
        return parser.parse(content)


def mineru_parser_registry(
    client: MinerUHttpClient,
    *,
    endpoint: str,
    token: str,
    timeout_seconds: float | None = None,
    poll_timeout_seconds: float | None = None,
    poll_interval_seconds: float | None = None,
    model: str | None = None,
) -> ParserRegistry:
    kwargs = dict(
        endpoint=endpoint,
        token=token,
        timeout_seconds=timeout_seconds,
        poll_timeout_seconds=poll_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        model=model,
    )
    return ParserRegistry(
        {
            kind: MinerUCloudParser(client, kind=kind, **kwargs)
            for kind in _WHITELIST
        }
    )
