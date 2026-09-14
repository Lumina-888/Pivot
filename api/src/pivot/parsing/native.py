"""Native parsers behind worker[parse] extra (SPEC §6.1 MVP)."""

from __future__ import annotations

import zipfile
from io import BytesIO

from pivot.parsing.errors import ParseError, parse_error
from pivot.parsing.models import ParsedBlock, ParsedDocument

_NATIVE_MODULES = ("fitz", "docx", "pptx", "openpyxl")


def require_native_extra() -> None:
    for name in _NATIVE_MODULES:
        try:
            __import__(name)
        except ImportError as exc:
            raise RuntimeError(
                "pivot_worker[parse] is required when PIVOT_PARSER=native"
            ) from exc


def _import_named(name: str):
    try:
        return __import__(name)
    except ImportError as exc:
        raise RuntimeError(
            "pivot_worker[parse] is required when PIVOT_PARSER=native"
        ) from exc


def _reject_encrypted_ooxml(content: bytes) -> None:
    try:
        archive = zipfile.ZipFile(BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise parse_error("CORRUPTED_FILE", "Office 文件损坏") from exc
    names = set(archive.namelist())
    archive.close()
    if "EncryptedPackage" in names or "EncryptionInfo" in names:
        raise parse_error("ENCRYPTED_FILE", "加密文件无法解析")


class PyMuPdfParser:
    kind = "pdf"

    def parse(self, content: bytes) -> ParsedDocument:
        fitz = _import_named("fitz")
        try:
            document = fitz.open(stream=content, filetype="pdf")
        except Exception as exc:
            if b"/Encrypt" in content:
                raise parse_error("ENCRYPTED_FILE", "加密文件无法解析") from exc
            raise parse_error("CORRUPTED_FILE", "PDF 文件损坏") from exc
        try:
            if document.is_encrypted:
                raise parse_error("ENCRYPTED_FILE", "加密文件无法解析")
            blocks: list[ParsedBlock] = []
            failures = 0
            has_image = False
            for index, page in enumerate(document, start=1):
                try:
                    text = page.get_text("text")
                    if page.get_images():
                        has_image = True
                except Exception:
                    failures += 1
                    continue
                if text.strip():
                    blocks.append(
                        ParsedBlock(
                            text=text.strip(),
                            locator=f"page={index}",
                            title_path="",
                        )
                    )
            if failures and blocks:
                raise parse_error("PARTIAL_PAGE_FAILURE", "部分页面解析失败")
            if failures and not blocks:
                raise parse_error("CORRUPTED_FILE", "PDF 文件损坏")
            if not blocks:
                if has_image:
                    raise parse_error("UNSUPPORTED_SCAN_PDF", "扫描件需要 OCR")
                raise parse_error("EMPTY_TEXT", "解析结果为空")
            return ParsedDocument(kind="pdf", blocks=tuple(blocks))
        finally:
            document.close()


class PythonDocxParser:
    kind = "docx"

    def parse(self, content: bytes) -> ParsedDocument:
        _reject_encrypted_ooxml(content)
        Document = _import_named("docx").Document
        try:
            document = Document(BytesIO(content))
        except ParseError:
            raise
        except Exception as exc:
            raise parse_error("CORRUPTED_FILE", "Office 文件损坏") from exc
        paragraphs: list[ParsedBlock] = []
        title = ""
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            style = paragraph.style.name if paragraph.style is not None else ""
            if "Heading" in style:
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


class PythonPptxParser:
    kind = "pptx"

    def parse(self, content: bytes) -> ParsedDocument:
        _reject_encrypted_ooxml(content)
        Presentation = _import_named("pptx").Presentation
        try:
            presentation = Presentation(BytesIO(content))
        except ParseError:
            raise
        except Exception as exc:
            raise parse_error("CORRUPTED_FILE", "Office 文件损坏") from exc
        blocks: list[ParsedBlock] = []
        for index, slide in enumerate(presentation.slides, start=1):
            texts: list[str] = []
            for shape in slide.shapes:
                if not getattr(shape, "has_text_frame", False):
                    continue
                text = shape.text_frame.text.strip()
                if text:
                    texts.append(text)
            if not texts:
                continue
            blocks.append(
                ParsedBlock(
                    text="\n".join(texts),
                    locator=f"slide={index}",
                    title_path=texts[0],
                )
            )
        if not blocks:
            raise parse_error("EMPTY_TEXT", "解析结果为空")
        return ParsedDocument(kind="pptx", blocks=tuple(blocks))


class OpenpyxlParser:
    kind = "xlsx"

    def parse(self, content: bytes) -> ParsedDocument:
        _reject_encrypted_ooxml(content)
        load_workbook = _import_named("openpyxl").load_workbook
        try:
            workbook = load_workbook(BytesIO(content), data_only=True, read_only=True)
        except ParseError:
            raise
        except Exception as exc:
            raise parse_error("CORRUPTED_FILE", "Office 文件损坏") from exc
        try:
            blocks: list[ParsedBlock] = []
            for sheet in workbook.worksheets:
                rows: list[str] = []
                for row in sheet.iter_rows():
                    values = [
                        f"{cell.coordinate}:{cell.value}"
                        for cell in row
                        if cell.value is not None
                    ]
                    if values:
                        rows.append(" | ".join(values))
                text = "\n".join(rows)
                if text.strip():
                    blocks.append(
                        ParsedBlock(
                            text=text,
                            locator=f"sheet={sheet.title}",
                            title_path=sheet.title,
                        )
                    )
            if not blocks:
                raise parse_error("EMPTY_TEXT", "解析结果为空")
            return ParsedDocument(kind="xlsx", blocks=tuple(blocks))
        finally:
            workbook.close()
