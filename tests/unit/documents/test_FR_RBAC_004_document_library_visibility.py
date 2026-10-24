"""Document endpoints enforce library visibility (FR-RBAC-004, S2 gap A).

The retrieval and Agent paths already filter by library, but the
document endpoints used to authorize on the legacy space flag: a
non-admin could enumerate any "shared"-space document and open it,
including documents the library rules hide (notably fresh uploads,
which default to space "shared" and library "unassigned"). These
tests pin the library rule on all three read endpoints: list,
detail/versions, and preview/download. Unauthorized documents are
RESOURCE_NOT_FOUND, never a leak that they exist.
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

ADMIN_LIBRARIES = frozenset({"pub", "unassigned", "dept_eng", "dept_art"})
PUB_ONLY = frozenset({"pub"})
ENG_USER = frozenset({"pub", "dept_eng"})
MULTI_USER = frozenset({"pub", "dept_eng", "dept_art"})


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


def _set_library(store: MemoryDocuments, document_id: str, library_id: str) -> None:
    record = store.get(document_id)
    assert record is not None
    record.library_id = library_id
    store.save(record)


def _seed(service, store):
    pub_doc = _upload(service, title="pub-doc", space="shared")
    _set_library(store, pub_doc.document_id, "pub")
    eng_doc = _upload(service, title="eng-doc", space="internal")
    _set_library(store, eng_doc.document_id, "dept_eng")
    art_doc = _upload(service, title="art-doc", space="internal")
    _set_library(store, art_doc.document_id, "dept_art")
    # The dangerous combination: shared space, unassigned library.
    unassigned_doc = _upload(service, title="unassigned-doc", space="shared")
    return pub_doc, eng_doc, art_doc, unassigned_doc


def test_FR_RBAC_004_list_hides_shared_space_unassigned_document_from_user():
    service, store = _service_with_store()
    _, _, _, unassigned_doc = _seed(service, store)
    user_ids = {
        item["document_id"]
        for item in service.list_library(viewer_role="user", visible_libraries=PUB_ONLY)
    }
    admin_ids = {
        item["document_id"]
        for item in service.list_library(
            viewer_role="admin", visible_libraries=ADMIN_LIBRARIES
        )
    }
    assert unassigned_doc.document_id not in user_ids
    assert unassigned_doc.document_id in admin_ids


def test_FR_RBAC_004_list_union_for_multi_department_user():
    service, store = _service_with_store()
    pub_doc, eng_doc, art_doc, _ = _seed(service, store)
    multi_ids = {
        item["document_id"]
        for item in service.list_library(viewer_role="user", visible_libraries=MULTI_USER)
    }
    single_ids = {
        item["document_id"]
        for item in service.list_library(viewer_role="user", visible_libraries=ENG_USER)
    }
    assert multi_ids == {
        pub_doc.document_id,
        eng_doc.document_id,
        art_doc.document_id,
    }
    assert single_ids == {pub_doc.document_id, eng_doc.document_id}


def test_FR_RBAC_004_space_filter_still_applies_within_visible_libraries():
    service, store = _service_with_store()
    pub_doc, eng_doc, _, _ = _seed(service, store)
    internal_ids = {
        item["document_id"]
        for item in service.list_library(
            viewer_role="user", visible_libraries=ENG_USER, space="internal"
        )
    }
    shared_ids = {
        item["document_id"]
        for item in service.list_library(
            viewer_role="user", visible_libraries=ENG_USER, space="shared"
        )
    }
    assert internal_ids == {eng_doc.document_id}
    assert shared_ids == {pub_doc.document_id}


def test_FR_RBAC_004_detail_and_versions_hide_other_library():
    service, store = _service_with_store()
    pub_doc, _, art_doc, _ = _seed(service, store)
    with pytest.raises(DocumentError) as detail:
        service.get_detail(
            art_doc.document_id,
            viewer_role="user",
            visible_libraries=ENG_USER,
            request_id="req_detail",
        )
    assert detail.value.code == "RESOURCE_NOT_FOUND"
    with pytest.raises(DocumentError) as versions:
        service.list_versions(
            art_doc.document_id,
            viewer_role="user",
            visible_libraries=ENG_USER,
            request_id="req_versions",
        )
    assert versions.value.code == "RESOURCE_NOT_FOUND"
    seen = service.get_detail(
        pub_doc.document_id,
        viewer_role="user",
        visible_libraries=ENG_USER,
        request_id="req_pub",
    )
    assert seen["document_id"] == pub_doc.document_id


def test_FR_RBAC_004_preview_and_download_hide_unassigned_and_other_library():
    service, store = _service_with_store()
    _, _, art_doc, unassigned_doc = _seed(service, store)
    for document_id in (art_doc.document_id, unassigned_doc.document_id):
        for purpose in ("preview", "download"):
            with pytest.raises(DocumentError) as error:
                service.open_content(
                    document_id,
                    viewer_role="user",
                    visible_libraries=ENG_USER,
                    request_id="req_open",
                    purpose=purpose,
                    actor_id="usr_alice",
                )
            assert error.value.code == "RESOURCE_NOT_FOUND"
    admin_preview = service.open_content(
        unassigned_doc.document_id,
        viewer_role="admin",
        visible_libraries=ADMIN_LIBRARIES,
        request_id="req_admin",
        purpose="preview",
        actor_id="usr_admin",
    )
    assert admin_preview.body.startswith(b"%PDF")


def test_FR_RBAC_004_admin_sees_unassigned_and_other_library():
    service, store = _service_with_store()
    _, _, art_doc, unassigned_doc = _seed(service, store)
    for document_id in (art_doc.document_id, unassigned_doc.document_id):
        detail = service.get_detail(
            document_id,
            viewer_role="admin",
            visible_libraries=ADMIN_LIBRARIES,
            request_id="req_admin",
        )
        assert detail["document_id"] == document_id
