"""Markdown and minimal Word renderers. Output is bounded by content.py payloads."""

from __future__ import annotations

import zipfile
from io import BytesIO
from xml.sax.saxutils import escape

from pivot.exports.content import sanitize_filename


def render(payload: dict, fmt: str) -> tuple[bytes, str, str]:
    filename = sanitize_filename(str(payload.get("title") or "export"), fmt)
    if fmt == "markdown":
        body = render_markdown(payload).encode("utf-8")
        return body, filename, "text/markdown; charset=utf-8"
    if fmt == "docx":
        return (
            render_docx(payload),
            filename,
            ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        )
    raise ValueError(f"unsupported export format: {fmt}")


def render_markdown(payload: dict) -> str:
    lines: list[str] = ["# 问枢导出", ""]
    source_type = payload.get("source_type")
    if source_type == "conversation":
        lines.extend(
            [
                f"- 会话：{payload.get('conversation_id', '')}",
                f"- Run：{payload.get('run_id', '')}",
                f"- 状态：{payload.get('state', '')}",
                "",
                "## 答案",
                "",
                str(payload.get("answer") or ""),
                "",
                "## Claims",
                "",
            ]
        )
        for claim in payload.get("claims") or []:
            citation_ids = ", ".join(claim.get("citation_ids") or []) or "无"
            lines.extend(
                [
                    f"### {claim.get('text', '')}",
                    f"- 支持度：{claim.get('support', '')}",
                    f"- 引用：{citation_ids}",
                    "",
                ]
            )
        lines.extend(["## Citations", ""])
        for citation in payload.get("citations") or []:
            lines.extend(
                [
                    f"- `{citation.get('id', '')}` {citation.get('locator', '')}",
                    "",
                    str(citation.get("snippet") or ""),
                    "",
                ]
            )
    else:
        lines.extend(
            [
                f"- 文档：{payload.get('document_id', '')}",
                f"- 版本：{payload.get('version_id', '')}",
                "",
                "## 内容",
                "",
                str(payload.get("display_text") or ""),
                "",
                "## 定位",
                "",
            ]
        )
        for locator in payload.get("locators") or []:
            lines.append(f"- {locator}")
        lines.append("")
    return "\n".join(lines)


def render_docx(payload: dict) -> bytes:
    paragraphs = [line for line in render_markdown(payload).split("\n")]
    body = "".join(_w_paragraph(line) for line in paragraphs)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _RELS)
        archive.writestr("word/_rels/document.xml.rels", _DOCUMENT_RELS)
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _w_paragraph(text: str) -> str:
    return f'<w:p><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


_PKG = "http://schemas.openxmlformats.org/package/2006"
_OD = "http://schemas.openxmlformats.org/officeDocument/2006"
_WP = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<Types xmlns="{_PKG}/content-types">'
    '<Default Extension="rels" '
    f'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    f'<Override PartName="/word/document.xml" ContentType="{_WP}"/>'
    "</Types>"
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<Relationships xmlns="{_PKG}/relationships">'
    '<Relationship Id="rId1" '
    f'Type="{_OD}/relationships/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)

_DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>
"""
