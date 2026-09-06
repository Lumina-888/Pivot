"""Heuristic PDF parser. Production should swap in PyMuPDF (see M07 change request)."""

from __future__ import annotations

import re

from pivot.parsing.errors import parse_error
from pivot.parsing.models import ParsedBlock, ParsedDocument

_TJ = re.compile(rb"\((?:\\.|[^\\)])*\)\s*Tj")


def _unescape(payload: bytes) -> str:
    text = payload.decode("latin-1", errors="replace")
    return (
        text.replace("\\(", "(")
        .replace("\\)", ")")
        .replace("\\n", "\n")
        .replace("\\\\", "\\")
    )


class PdfParser:
    kind = "pdf"

    def parse(self, content: bytes) -> ParsedDocument:
        if not content.startswith(b"%PDF"):
            raise parse_error("CORRUPTED_FILE", "PDF 文件损坏")
        if b"/Encrypt" in content:
            raise parse_error("ENCRYPTED_FILE", "加密文件无法解析")
        matches = _TJ.findall(content)
        texts = []
        for match in matches:
            inner = match.rsplit(b"Tj", 1)[0].strip()
            if inner.startswith(b"(") and inner.endswith(b")"):
                texts.append(_unescape(inner[1:-1]))
        if b"%%PAGE_FAIL" in content and texts:
            raise parse_error("PARTIAL_PAGE_FAILURE", "部分页面解析失败")
        if not any(text.strip() for text in texts):
            if b"/Subtype /Image" in content or b"/XObject" in content:
                raise parse_error("UNSUPPORTED_SCAN_PDF", "扫描件需要 OCR")
            raise parse_error("EMPTY_TEXT", "解析结果为空")
        blocks = tuple(
            ParsedBlock(text=text, locator=f"page={index}", title_path="")
            for index, text in enumerate(texts, start=1)
            if text.strip()
        )
        return ParsedDocument(kind="pdf", blocks=blocks)
