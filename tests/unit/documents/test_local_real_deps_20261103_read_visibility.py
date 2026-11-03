"""2026-11-03 local-real-deps defect 3: document reads honour folders
and exceptions, not just library membership.

Before the fix, list/detail/versions/preview/download checked only
library_id, so a folder restriction never hid a document and a
document-level exception never opened one, while /search and
export/citation went through AccessControl.authorize_document. These
tests pin the unified channels on DocumentService: exception opens,
restricted folder hides, default folder (None) stays open, and
omitting both sets keeps the legacy library-only behaviour.
"""

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


def _service_with_store():
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


def _upload(service, *, title: str):
    return service.upload(
        filename=f"{title}.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes() + title.encode("ascii"),
        title=title,
        actor_id="usr_admin",
        request_id="req_up",
    )


def _set_location(store, document_id, *, library_id, folder_id=None):
    record = store.get(document_id)
    assert record is not None
    record.library_id = library_id
    record.folder_id = folder_id
    store.save(record)


def test_read_hides_document_in_restricted_folder():
    service, store = _service_with_store()
    version = _upload(service, title="folder-doc")
    _set_location(store, version.document_id, library_id="dept_eng", folder_id="folder_9")
    with pytest.raises(DocumentError) as exc:
        service.get_detail(
            version.document_id,
            viewer_role="user",
            visible_libraries=frozenset({"dept_eng"}),
            request_id="req_det",
            visible_folder_ids=frozenset({"folder_1"}),
        )
    assert exc.value.code == "RESOURCE_NOT_FOUND"
    assert service.list_library(
        viewer_role="user",
        visible_libraries=frozenset({"dept_eng"}),
        visible_folder_ids=frozenset({"folder_1"}),
    ) == ()


def test_read_opens_document_via_exception_inside_restricted_folder():
    service, store = _service_with_store()
    version = _upload(service, title="exception-doc")
    _set_location(store, version.document_id, library_id="dept_eng", folder_id="folder_9")
    detail = service.get_detail(
        version.document_id,
        viewer_role="user",
        visible_libraries=frozenset({"dept_eng"}),
        request_id="req_det",
        visible_folder_ids=frozenset({"folder_1"}),
        exception_document_ids=frozenset({version.document_id}),
    )
    assert detail["document_id"] == version.document_id
    items = service.list_library(
        viewer_role="user",
        visible_libraries=frozenset({"dept_eng"}),
        visible_folder_ids=frozenset({"folder_1"}),
        exception_document_ids=frozenset({version.document_id}),
    )
    assert [item["document_id"] for item in items] == [version.document_id]


def test_read_keeps_default_folder_open_and_legacy_callers_library_only():
    service, store = _service_with_store()
    version = _upload(service, title="default-doc")
    _set_location(store, version.document_id, library_id="dept_eng", folder_id=None)
    detail = service.get_detail(
        version.document_id,
        viewer_role="user",
        visible_libraries=frozenset({"dept_eng"}),
        request_id="req_det",
        visible_folder_ids=frozenset({"folder_1"}),
    )
    assert detail["document_id"] == version.document_id
    # Legacy caller passing neither set: library-only, as before.
    legacy = service.get_detail(
        version.document_id,
        viewer_role="user",
        visible_libraries=frozenset({"dept_eng"}),
        request_id="req_det",
    )
    assert legacy["document_id"] == version.document_id
