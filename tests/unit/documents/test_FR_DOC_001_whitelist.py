from __future__ import annotations

import pytest
from fakes import ooxml, pdf_bytes
from pivot.documents.errors import DocumentError


def test_FR_DOC_001_pdf_docx_pptx_xlsx_are_accepted(service):
    cases = [
        ("a.pdf", "application/pdf", pdf_bytes()),
        (
            "a.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ooxml("docx"),
        ),
        (
            "a.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ooxml("pptx"),
        ),
        (
            "a.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ooxml("xlsx"),
        ),
    ]
    for filename, mime, content in cases:
        version = service.upload(
            filename=filename,
            declared_mime=mime,
            content=content,
            title=filename,
            actor_id="usr_admin",
            request_id="req_up",
        )
        assert version.state == "uploaded"
        assert version.current is False
        assert version.storage_key.startswith("quarantine/")


def test_FR_DOC_001_legacy_office_is_rejected(service):
    with pytest.raises(DocumentError) as error:
        service.upload(
            filename="old.doc",
            declared_mime="application/msword",
            content=b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32,
            title="old",
            actor_id="usr_admin",
            request_id="req_doc",
        )
    assert error.value.code == "UNSUPPORTED_EXTENSION"
