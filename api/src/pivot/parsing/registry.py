"""Pluggable parser registry (SPEC §6.1)."""

from __future__ import annotations

from collections.abc import Mapping

from pivot.parsing.errors import parse_error
from pivot.parsing.models import ParsedDocument
from pivot.parsing.office import DocxParser, PptxParser, XlsxParser
from pivot.parsing.pdf import PdfParser


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
