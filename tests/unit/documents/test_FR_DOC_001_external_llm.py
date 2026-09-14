from __future__ import annotations

from fakes import pdf_bytes


def test_FR_DOC_001_upload_records_external_llm_allowed(service):
    allowed = service.upload(
        filename="allowed.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes() + b"allowed",
        title="allowed",
        actor_id="usr_admin",
        request_id="req_allowed",
        external_llm_allowed=True,
    )
    denied = service.upload(
        filename="denied.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes() + b"denied",
        title="denied",
        actor_id="usr_admin",
        request_id="req_denied",
    )
    assert allowed.external_llm_allowed is True
    assert denied.external_llm_allowed is False
    detail = service.get_detail(
        allowed.document_id, viewer_role="admin", request_id="req_detail"
    )
    assert detail["versions"][0]["external_llm_allowed"] is True
    assert "storage_key" not in detail["versions"][0]
