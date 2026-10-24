from __future__ import annotations

from fakes import (
    MemoryAudits,
    MemoryChunks,
    MemoryDocuments,
    MemoryObjects,
    MemoryTasks,
    MemoryVersions,
    pdf_bytes,
)
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


def test_FR_DOC_007_list_library_excludes_tombstone(service):
    kept = _upload(service, title="kept")
    removed = _upload(service, title="removed")
    service.request_delete(removed.document_id, "req_del", "usr_admin")
    items = service.list_library(viewer_role="admin", visible_libraries=ADMIN_LIBRARIES)
    ids = {item["document_id"] for item in items}
    assert kept.document_id in ids
    assert removed.document_id not in ids


def test_FR_DOC_001_list_library_uploaded_has_null_current_version(service):
    version = _upload(service, title="draft")
    items = service.list_library(viewer_role="admin", visible_libraries=ADMIN_LIBRARIES)
    assert len(items) == 1
    assert items[0]["document_id"] == version.document_id
    assert items[0]["title"] == "draft"
    assert items[0]["current_version"] is None
    assert items[0]["created_at"]
    assert "storage_key" not in items[0]


def test_FR_RBAC_004_list_library_user_sees_only_visible_libraries():
    # S2 changed the authorization basis from space to library. The
    # unassigned document below keeps the fail-closed default library
    # even though its space is "shared": under the old rule a user
    # would have enumerated it, under the library rule they must not.
    service, store = _service_with_store()
    pub_doc = _upload(service, title="pub-doc", space="shared")
    _set_library(store, pub_doc.document_id, "pub")
    eng_doc = _upload(service, title="eng-doc", space="internal")
    _set_library(store, eng_doc.document_id, "dept_eng")
    _upload(service, title="unassigned-doc", space="shared")
    user_ids = {
        item["document_id"]
        for item in service.list_library(
            viewer_role="user", visible_libraries=frozenset({"pub", "dept_eng"})
        )
    }
    admin_ids = {
        item["document_id"]
        for item in service.list_library(
            viewer_role="admin", visible_libraries=ADMIN_LIBRARIES
        )
    }
    assert user_ids == {pub_doc.document_id, eng_doc.document_id}
    assert len(admin_ids) == 3
