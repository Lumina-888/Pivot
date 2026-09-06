"""OOXML parsers using the standard library (docx/pptx/xlsx)."""

from __future__ import annotations

import zipfile
from io import BytesIO
from xml.etree import ElementTree

from pivot.parsing.errors import parse_error
from pivot.parsing.models import ParsedBlock, ParsedDocument


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _texts(root: ElementTree.Element, names: set[str]) -> list[str]:
    found: list[str] = []
    for node in root.iter():
        if _local(node.tag) in names and node.text and node.text.strip():
            found.append(node.text.strip())
    return found


def _open_zip(content: bytes) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise parse_error("CORRUPTED_FILE", "Office 文件损坏") from exc


class DocxParser:
    kind = "docx"

    def parse(self, content: bytes) -> ParsedDocument:
        with _open_zip(content) as archive:
            try:
                xml = archive.read("word/document.xml")
            except KeyError as exc:
                raise parse_error("CORRUPTED_FILE", "缺少 word/document.xml") from exc
            root = ElementTree.fromstring(xml)
            paragraphs = []
            title = ""
            for paragraph in root.iter():
                if _local(paragraph.tag) != "p":
                    continue
                runs = _texts(paragraph, {"t"})
                if not runs:
                    continue
                text = "".join(runs)
                styles = [node.get("w:val") or node.get("val") or "" for node in paragraph.iter()]
                heading = any("Heading" in style for style in styles)
                if heading:
                    title = text
                paragraphs.append(
                    ParsedBlock(
                        text=text,
                        locator=f"paragraph={len(paragraphs) + 1}",
                        title_path=title,
                    )
                )
        if not paragraphs:
            raise parse_error("EMPTY_TEXT", "解析结果为空")
        return ParsedDocument(kind="docx", blocks=tuple(paragraphs))


class PptxParser:
    kind = "pptx"

    def parse(self, content: bytes) -> ParsedDocument:
        with _open_zip(content) as archive:
            slides = sorted(
                name for name in archive.namelist() if name.startswith("ppt/slides/slide")
            )
            if not slides:
                raise parse_error("EMPTY_TEXT", "解析结果为空")
            blocks = []
            for index, name in enumerate(slides, start=1):
                root = ElementTree.fromstring(archive.read(name))
                texts = _texts(root, {"t"})
                title = texts[0] if texts else f"slide-{index}"
                body = "\n".join(texts)
                if not body.strip():
                    continue
                blocks.append(
                    ParsedBlock(text=body, locator=f"slide={index}", title_path=title)
                )
        if not blocks:
            raise parse_error("EMPTY_TEXT", "解析结果为空")
        return ParsedDocument(kind="pptx", blocks=tuple(blocks))


class XlsxParser:
    kind = "xlsx"

    def parse(self, content: bytes) -> ParsedDocument:
        with _open_zip(content) as archive:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = _texts(root, {"t"})
            sheets = sorted(
                name
                for name in archive.namelist()
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
            )
            if not sheets:
                raise parse_error("EMPTY_TEXT", "解析结果为空")
            blocks = []
            for sheet in sheets:
                sheet_name = sheet.rsplit("/", 1)[-1].removesuffix(".xml")
                root = ElementTree.fromstring(archive.read(sheet))
                rows: list[str] = []
                for row in root.iter():
                    if _local(row.tag) != "row":
                        continue
                    values = []
                    for cell in row:
                        if _local(cell.tag) != "c":
                            continue
                        ref = cell.get("r") or ""
                        value_node = next(
                            (child for child in cell if _local(child.tag) == "v"), None
                        )
                        if value_node is None or value_node.text is None:
                            continue
                        raw = value_node.text
                        if cell.get("t") == "s" and raw.isdigit() and int(raw) < len(shared):
                            raw = shared[int(raw)]
                        values.append(f"{ref}:{raw}")
                    if values:
                        rows.append(" | ".join(values))
                text = "\n".join(rows)
                if text.strip():
                    blocks.append(
                        ParsedBlock(
                            text=text,
                            locator=f"sheet={sheet_name}",
                            title_path=sheet_name,
                        )
                    )
        if not blocks:
            raise parse_error("EMPTY_TEXT", "解析结果为空")
        return ParsedDocument(kind="xlsx", blocks=tuple(blocks))
