"""Native parse extra (PyMuPDF/docx/pptx/xlsx). Default registry stays heuristic."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from pivot.chunking import ChunkingPolicy, ChunkSplitter
from pivot.parsing import ParserRegistry
from pivot.parsing.errors import ParseError
from pivot.parsing.office import DocxParser
from pivot.parsing.pdf import PdfParser
from pivot.parsing.registry import native_parser_registry
from pivot_worker.ingest import IngestRequest, IngestWorker
from samples import ooxml_docx, pdf_with_text

_ROOT = Path(__file__).resolve().parents[3]
_PYPROJECT = _ROOT / "worker" / "pyproject.toml"
_NATIVE_SRC = _ROOT / "api" / "src" / "pivot" / "parsing" / "native.py"


def _fitz():
    return pytest.importorskip("fitz")


def _docx():
    return pytest.importorskip("docx")


def _pptx():
    return pytest.importorskip("pptx")


def _openpyxl():
    return pytest.importorskip("openpyxl")


def _native_pdf(text: str = "Late arrival policy") -> bytes:
    fitz = _fitz()
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    payload = doc.tobytes()
    doc.close()
    return payload


def _empty_pdf() -> bytes:
    fitz = _fitz()
    doc = fitz.open()
    doc.new_page()
    payload = doc.tobytes()
    doc.close()
    return payload


def _encrypted_pdf() -> bytes:
    fitz = _fitz()
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "secret policy")
    payload = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="user",
        owner_pw="owner",
    )
    doc.close()
    return payload


def _scan_pdf() -> bytes:
    fitz = _fitz()
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 16, 16), 0)
    pixmap.clear_with(128)
    doc = fitz.open()
    page = doc.new_page(width=72, height=72)
    page.insert_image(page.rect, pixmap=pixmap)
    payload = doc.tobytes()
    doc.close()
    return payload


def _native_docx(*paragraphs: str, heading: str | None = None) -> bytes:
    Document = _docx().Document
    doc = Document()
    if heading is not None:
        doc.add_heading(heading, level=1)
    for item in paragraphs:
        doc.add_paragraph(item)
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _native_pptx(*slides: str) -> bytes:
    Presentation = _pptx().Presentation
    prs = Presentation()
    layout = prs.slide_layouts[5]
    for text in slides:
        slide = prs.slides.add_slide(layout)
        box = slide.shapes.add_textbox(0, 0, 1, 1)
        box.text_frame.text = text
    buffer = BytesIO()
    prs.save(buffer)
    return buffer.getvalue()


def _native_xlsx(values: dict[str, str] | None = None) -> bytes:
    Workbook = _openpyxl().Workbook
    book = Workbook()
    sheet = book.active
    sheet.title = "attendance"
    for coord, value in (values or {"A1": "late", "A2": "absent"}).items():
        sheet[coord] = value
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _encrypted_ooxml() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("EncryptedPackage", b"secret")
        archive.writestr("EncryptionInfo", b"info")
    return buffer.getvalue()


def test_FR_DOC_004_native_extra_is_declared():
    text = _PYPROJECT.read_text(encoding="utf-8")
    assert "parse" in text
    assert "pymupdf" in text
    assert "python-docx" in text
    assert "python-pptx" in text
    assert "openpyxl" in text
    assert "pdfplumber" not in text


def test_FR_DOC_004_default_registry_stays_heuristic():
    registry = ParserRegistry()
    assert isinstance(registry._parsers["pdf"], PdfParser)
    assert isinstance(registry._parsers["docx"], DocxParser)
    parsed = registry.parse("pdf", pdf_with_text())
    assert "Late arrival policy" in parsed.text
    office = registry.parse("docx", ooxml_docx(["Attendance policy"]))
    assert "Attendance policy" in office.text


def test_FR_DOC_004_native_does_not_freeze_page_or_size_limits():
    text = _NATIVE_SRC.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "max_pages" not in lowered
    assert "page_limit" not in lowered
    assert "max_sheets" not in lowered
    assert "max_file" not in lowered
    assert "1024 * 1024" not in text
    assert "50 * 1024" not in text


def test_FR_DOC_004_native_requires_parse_extra(monkeypatch):
    for name in ("fitz", "docx", "pptx", "openpyxl"):
        monkeypatch.setitem(__import__("sys").modules, name, None)
    with pytest.raises(RuntimeError, match=r"pivot_worker\[parse\]"):
        native_parser_registry()


def test_FR_DOC_004_native_pdf_parses_text_and_page_locator():
    parsed = native_parser_registry().parse("pdf", _native_pdf())
    assert parsed.kind == "pdf"
    assert "Late arrival policy" in parsed.text
    assert parsed.blocks[0].locator == "page=1"


def test_FR_DOC_004_native_docx_parses_paragraphs():
    parsed = native_parser_registry().parse(
        "docx",
        _native_docx("Late arrival is recorded.", heading="Attendance policy"),
    )
    assert parsed.kind == "docx"
    assert "Attendance policy" in parsed.text
    assert "Late arrival is recorded." in parsed.text
    assert parsed.blocks[0].locator.startswith("paragraph=")
    assert "Attendance policy" in parsed.blocks[-1].title_path


def test_FR_DOC_004_native_pptx_parses_slides():
    parsed = native_parser_registry().parse("pptx", _native_pptx("Q3 review"))
    assert parsed.kind == "pptx"
    assert "Q3 review" in parsed.text
    assert parsed.blocks[0].locator == "slide=1"


def test_FR_DOC_004_native_xlsx_parses_sheets():
    parsed = native_parser_registry().parse("xlsx", _native_xlsx())
    assert parsed.kind == "xlsx"
    assert "late" in parsed.text
    assert "absent" in parsed.text
    assert parsed.blocks[0].locator == "sheet=attendance"


def test_FR_DOC_004_native_encrypted_pdf_is_encrypted_file():
    with pytest.raises(ParseError) as caught:
        native_parser_registry().parse("pdf", _encrypted_pdf())
    assert caught.value.code == "ENCRYPTED_FILE"
    assert caught.value.retryable is False


def test_FR_DOC_004_native_corrupted_pdf_is_corrupted_file():
    with pytest.raises(ParseError) as caught:
        native_parser_registry().parse("pdf", b"not-a-pdf")
    assert caught.value.code == "CORRUPTED_FILE"


def test_FR_DOC_004_native_empty_pdf_is_empty_text():
    with pytest.raises(ParseError) as caught:
        native_parser_registry().parse("pdf", _empty_pdf())
    assert caught.value.code == "EMPTY_TEXT"


def test_FR_DOC_004_native_scan_pdf_is_unsupported_scan():
    with pytest.raises(ParseError) as caught:
        native_parser_registry().parse("pdf", _scan_pdf())
    assert caught.value.code == "UNSUPPORTED_SCAN_PDF"


def test_FR_DOC_004_native_empty_docx_is_empty_text():
    with pytest.raises(ParseError) as caught:
        native_parser_registry().parse("docx", _native_docx())
    assert caught.value.code == "EMPTY_TEXT"


def test_FR_DOC_004_native_corrupted_office_is_corrupted_file():
    with pytest.raises(ParseError) as caught:
        native_parser_registry().parse("docx", b"not-a-zip")
    assert caught.value.code == "CORRUPTED_FILE"


def test_FR_DOC_004_native_encrypted_office_is_encrypted_file():
    with pytest.raises(ParseError) as caught:
        native_parser_registry().parse("xlsx", _encrypted_ooxml())
    assert caught.value.code == "ENCRYPTED_FILE"


def test_FR_DOC_004_native_four_formats_ingest_ok():
    worker = IngestWorker(
        parsers=native_parser_registry(),
        splitter=ChunkSplitter(ChunkingPolicy(max_chars=80, overlap_chars=8)),
        dimension=8,
    )
    jobs = [
        ("pdf", _native_pdf()),
        ("docx", _native_docx("Attendance policy")),
        ("pptx", _native_pptx("Q3 review")),
        ("xlsx", _native_xlsx()),
    ]
    for kind, content in jobs:
        result = worker.run(
            IngestRequest(
                version_id=f"ver_native_{kind}",
                kind=kind,
                content=content,
                message_id=f"msg_native_{kind}",
            )
        )
        assert result["status"] == "ok"
        assert result["error_code"] is None
        assert result["content"]["locators"]
