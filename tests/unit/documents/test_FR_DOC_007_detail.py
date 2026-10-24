from __future__ import annotations

import pytest
from fakes import (
    MemoryAudits,
    MemoryChunks,
    MemoryDocuments,
    MemoryObjects,
    MemoryTasks,
    MemoryVersions,
    pdf_bytes,
)
from pivot.documents.errors import DocumentError
from pivot.documents.service import DocumentService

ADMIN_LIBRARIES = frozenset({"pub", "unassigned", "dept_eng", "dept_art"})


def _service_with_store() -> tuple[DocumentService, MemoryDocuments]:
    store = MemoryDocuments()
    service = DocumentService(
        documents=store,
        versions=MemoryVersions(),
        chunks=MemoryChunks(),
        tasks=MemoryTasks(),
        objects=MemoryObjects(),
        audits=MemoryAudits(),
    )
    return service, store


def _set_library(store: MemoryDocuments, document_id: str, library_id: str) -> None:
    record = store.get(document_id)
    assert record is not None
    record.library_id = library_id
    store.save(record)


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
    detail = service.get_detail(
        version.document_id,
        viewer_role="admin",
        visible_libraries=ADMIN_LIBRARIES,
        request_id="req_d",
    )
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


def test_FR_RBAC_004_detail_hides_other_library_and_deleted_from_user():
    # S2 changed the authorization basis from space to library: a user
    # sees a document only when its library is in their visible set,
    # so this test now builds documents in distinct libraries instead
    # of relying on the space flag.
    service, store = _service_with_store()
    eng = _upload(service, title="eng", space="internal")
    _set_library(store, eng.document_id, "dept_eng")
    pub = _upload(service, title="pub", space="shared")
    _set_library(store, pub.document_id, "pub")
    live = _upload(service, title="live", space="shared")
    _set_library(store, live.document_id, "pub")
    service.request_delete(pub.document_id, "req_del", "usr_admin")
    with pytest.raises(DocumentError) as hidden:
        service.get_detail(
            eng.document_id,
            viewer_role="user",
            visible_libraries=frozenset({"pub"}),
            request_id="req_eng",
        )
    with pytest.raises(DocumentError) as deleted:
        service.get_detail(
            pub.document_id,
            viewer_role="user",
            visible_libraries=frozenset({"pub"}),
            request_id="req_del_d",
        )
    assert hidden.value.code == "RESOURCE_NOT_FOUND"
    assert deleted.value.code == "RESOURCE_NOT_FOUND"
    seen = service.get_detail(
        live.document_id,
        viewer_role="user",
        visible_libraries=frozenset({"pub"}),
        request_id="req_live",
    )
    assert seen["document_id"] == live.document_id
    admin = service.get_detail(
        pub.document_id,
        viewer_role="admin",
        visible_libraries=ADMIN_LIBRARIES,
        request_id="req_admin",
    )
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
