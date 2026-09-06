from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile


def pdf_with_text(text: str = "Late arrival policy") -> bytes:
    return b"%PDF-1.4\nBT (" + text.encode("latin-1") + b") Tj ET\n%%EOF\n"


def ooxml_docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{item}</w:t></w:r></w:p>" for item in paragraphs)
    xml = (
        '<?xml version="1.0"?><w:document xmlns:w='
        '"http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


def ooxml_pptx(slides: list[str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for index, text in enumerate(slides, start=1):
            xml = (
                '<?xml version="1.0"?><p:sld xmlns:a='
                '"http://schemas.openxmlformats.org/drawingml/2006/main" '
                'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
                f"<a:t>{text}</a:t></p:sld>"
            )
            archive.writestr(f"ppt/slides/slide{index}.xml", xml)
    return buffer.getvalue()


def ooxml_xlsx(values: list[str]) -> bytes:
    shared = (
        '<?xml version="1.0"?><sst xmlns='
        '"http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        + "".join(f"<si><t>{value}</t></si>" for value in values)
        + "</sst>"
    )
    cells = "".join(
        f'<c r="A{index}" t="s"><v>{index - 1}</v></c>'
        for index, _ in enumerate(values, start=1)
    )
    sheet = (
        '<?xml version="1.0"?><worksheet xmlns='
        '"http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData><row r=\"1\">{cells}</row></sheetData></worksheet>"
    )
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("xl/sharedStrings.xml", shared)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()
