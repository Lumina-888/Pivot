from __future__ import annotations

import pytest
from fakes import pdf_bytes
from pivot.documents.errors import DocumentError


def _upload(service, *, title: str, space: str = "shared"):
    return service.upload(
        filename=f"{title}.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes() + title.encode("ascii"),
        title=title,
        actor_id="usr_admin",
        request_id="req_up",
        space=space,
    )


def test_FR_DOC_007_detail_includes_versions_without_storage_key(service):
    version = _upload(service, title="policy")
    detail = service.get_detail(version.document_id, viewer_role="admin", request_id="req_d")
    assert detail["document_id"] == version.document_id
    assert detail["title"] == "policy"
    assert detail["created_by"] == "usr_admin"
    assert detail["deleted_at"] is None
    assert detail["versions"][0]["version_id"] == version.id
    assert detail["versions"][0]["state"] == "uploaded"
    assert detail["versions"][0]["current"] is False
    assert "storage_key" not in detail
    assert "storage_key" not in detail["versions"][0]
    assert "quarantine/" not in str(detail)


def test_FR_RBAC_004_detail_hides_non_shared_and_deleted_from_user(service):
    internal = _upload(service, title="internal", space="internal")
    shared = _upload(service, title="shared", space="shared")
    service.request_delete(shared.document_id, "req_del", "usr_admin")
    with pytest.raises(DocumentError) as hidden:
        service.get_detail(internal.document_id, viewer_role="user", request_id="req_int")
    with pytest.raises(DocumentError) as deleted:
        service.get_detail(shared.document_id, viewer_role="user", request_id="req_del_d")
    assert hidden.value.code == "RESOURCE_NOT_FOUND"
    assert deleted.value.code == "RESOURCE_NOT_FOUND"
    admin = service.get_detail(shared.document_id, viewer_role="admin", request_id="req_admin")
    assert admin["deleted_at"] is not None


def test_FR_DOC_006_retry_document_requeues_failed_version(service):
    version = _upload(service, title="broken")
    service.enqueue(version.id, "req_en")
    service.worker_started(version.id, "task_1", "req_ws")
    service.parse_error(version.id, "CORRUPTED_FILE", "req_err")
    retried = service.retry_document(version.document_id, "req_retry", "usr_admin")
    assert retried.id == version.id
    assert retried.state == "queued"
    assert retried.current is False
