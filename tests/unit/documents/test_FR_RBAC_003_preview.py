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


def _upload(service, *, title: str, space: str = "shared", extra: bytes = b""):
    return service.upload(
        filename=f"{title}.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes() + extra,
        title=title,
        actor_id="usr_admin",
        request_id="req_up",
        space=space,
    )


def test_FR_RBAC_003_preview_returns_stored_bytes_without_storage_key():
    # The previewed document lives in the public library, which the
    # user may see; the mechanism assertions are unchanged.
    service, store = _service_with_store()
    content = pdf_bytes() + b"\npreview-body"
    version = service.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=content,
        title="Attendance Policy",
        actor_id="usr_admin",
        request_id="req_up",
    )
    _set_library(store, version.document_id, "pub")
    preview = service.open_content(
        version.document_id,
        viewer_role="user",
        visible_libraries=frozenset({"pub"}),
        request_id="req_preview",
        purpose="preview",
        actor_id="usr_alice",
    )
    assert preview.body == content
    assert preview.media_type == "application/pdf"
    assert preview.disposition == "inline"
    assert preview.filename.endswith(".pdf")
    assert "storage_key" not in preview.__dict__
    assert "quarantine/" not in preview.filename
    download = service.open_content(
        version.document_id,
        viewer_role="user",
        visible_libraries=frozenset({"pub"}),
        request_id="req_dl",
        purpose="download",
        actor_id="usr_alice",
    )
    assert download.disposition == "attachment"
    assert download.body == content


def test_FR_RBAC_003_user_cannot_preview_guessed_or_internal_id():
    # The "internal" document now lives in another department's
    # library; the space flag alone authorizes nothing (S2).
    service, store = _service_with_store()
    internal = _upload(service, title="secret", space="internal")
    _set_library(store, internal.document_id, "dept_art")
    with pytest.raises(DocumentError) as guessed:
        service.open_content(
            "doc_guessed",
            viewer_role="user",
            visible_libraries=frozenset({"pub"}),
            request_id="req_guess",
            purpose="preview",
            actor_id="usr_alice",
        )
    assert guessed.value.code == "RESOURCE_NOT_FOUND"
    with pytest.raises(DocumentError) as hidden:
        service.open_content(
            internal.document_id,
            viewer_role="user",
            visible_libraries=frozenset({"pub"}),
            request_id="req_hid",
            purpose="download",
            actor_id="usr_alice",
        )
    assert hidden.value.code == "RESOURCE_NOT_FOUND"
    allowed = service.open_content(
        internal.document_id,
        viewer_role="admin",
        visible_libraries=ADMIN_LIBRARIES,
        request_id="req_admin",
        purpose="preview",
        actor_id="usr_admin",
    )
    assert allowed.body.startswith(b"%PDF")


def _ready(service, title: str = "gone"):
    version = _upload(service, title=title, extra=title.encode("ascii"))
    service.enqueue(version.id, "req_en")
    service.worker_started(version.id, "task_1", "req_ws")
    service.parse_ok(version.id, "req_parse")
    service.apply_chunks(version.id, ["body"], "msg_1", "req_chunk")
    service.embedding_ok(version.id, "req_emb")
    return service.publish(version.id, "req_pub")


def test_FR_DOC_007_download_unavailable_after_cleanup(service):
    version = _ready(service)
    service.request_delete(version.document_id, "req_del", "usr_admin")
    with pytest.raises(DocumentError) as user_error:
        service.open_content(
            version.document_id,
            viewer_role="user",
            visible_libraries=frozenset({"pub"}),
            request_id="req_user",
            purpose="download",
            actor_id="usr_alice",
        )
    assert user_error.value.code == "RESOURCE_NOT_FOUND"
    still_there = service.open_content(
        version.document_id,
        viewer_role="admin",
        visible_libraries=ADMIN_LIBRARIES,
        request_id="req_admin",
        purpose="download",
        actor_id="usr_admin",
    )
    assert still_there.body.startswith(b"%PDF")
    service.cleanup_ok(version.id, "req_clean")
    with pytest.raises(DocumentError) as gone:
        service.open_content(
            version.document_id,
            viewer_role="admin",
            visible_libraries=ADMIN_LIBRARIES,
            request_id="req_gone",
            purpose="preview",
            actor_id="usr_admin",
        )
    assert gone.value.code == "RESOURCE_NOT_FOUND"


def test_NFR_SEC_015_download_filename_is_sanitized(service):
    version = service.upload(
        filename="ok.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes(),
        title="../../evil\\name.pdf",
        actor_id="usr_admin",
        request_id="req_up",
    )
    payload = service.open_content(
        version.document_id,
        viewer_role="admin",
        visible_libraries=ADMIN_LIBRARIES,
        request_id="req_name",
        purpose="download",
        actor_id="usr_admin",
    )
    assert ".." not in payload.filename
    assert "\\" not in payload.filename
    assert "/" not in payload.filename
    assert payload.filename.endswith(".pdf")
