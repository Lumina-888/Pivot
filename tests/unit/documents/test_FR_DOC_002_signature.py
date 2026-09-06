from __future__ import annotations

import pytest
from fakes import ooxml, pdf_bytes
from pivot.documents.errors import DocumentError


def test_FR_DOC_002_pdf_disguised_as_docx_is_rejected(service):
    with pytest.raises(DocumentError) as error:
        service.upload(
            filename="fake.docx",
            declared_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            content=pdf_bytes(),
            title="fake",
            actor_id="usr_admin",
            request_id="req_fake",
        )
    assert error.value.code == "INVALID_FILE_SIGNATURE"


def test_FR_DOC_002_zip_bomb_disguised_as_pdf_is_rejected(service):
    with pytest.raises(DocumentError) as error:
        service.upload(
            filename="bomb.pdf",
            declared_mime="application/pdf",
            content=ooxml("docx"),
            title="bomb",
            actor_id="usr_admin",
            request_id="req_zip",
        )
    assert error.value.code == "INVALID_FILE_SIGNATURE"


def test_FR_DOC_002_mime_mismatch_is_rejected(service):
    with pytest.raises(DocumentError) as error:
        service.upload(
            filename="a.pdf",
            declared_mime="application/zip",
            content=pdf_bytes(),
            title="a",
            actor_id="usr_admin",
            request_id="req_mime",
        )
    assert error.value.code == "INVALID_FILE_SIGNATURE"
