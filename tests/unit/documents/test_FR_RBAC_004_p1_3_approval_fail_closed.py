"""S2: fail-closed proof for pending documents (ADR-019 D1, risk section).

Four layers, each tested: (1) the version state is not searchable
and prepare_ingest refuses it; (2) no published chunks exist for it;
(3) its library stays unassigned, so every non-admin visibility
check refuses it; (4) the library list shows no current ready
version for it. Retrieval, citation, preview, download, and list all
route through these layers; the pending document reaches none of
them.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pivot.documents.errors import DocumentError
from pivot.documents.ports import DocumentRecord, VersionRecord
from pivot.documents.service import DocumentService
from pivot.domain.document_state import is_searchable
from tests.unit.documents.fakes import (
    MemoryAudits,
    MemoryChunks,
    MemoryDocuments,
    MemoryObjects,
    MemoryTasks,
    MemoryVersions,
)

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)


def _service():
    documents = MemoryDocuments()
    versions = MemoryVersions()
    chunks = MemoryChunks()
    objects = MemoryObjects()
    documents.save(
        DocumentRecord(
            id="doc_pending", title="待批文档", space="shared",
            created_by="usr_frank", library_id="unassigned",
        )
    )
    versions.save(
        VersionRecord(
            id="ver_pending", document_id="doc_pending",
            content_sha256="sha",
            storage_key="quarantine/doc_pending/ver_pending",
            state="pending_approval",
        )
    )
    objects.put("quarantine/doc_pending/ver_pending", b"original-bytes")
    service = DocumentService(
        documents=documents,
        versions=versions,
        chunks=chunks,
        tasks=MemoryTasks(),
        objects=objects,
        audits=MemoryAudits(),
    )
    return service, versions, chunks


def _code(excinfo) -> str:
    return excinfo.value.code


def test_FR_RBAC_004_p1_3_pending_state_not_searchable() -> None:
    # Layer 1: the state machine itself excludes pending versions.
    assert not is_searchable("pending_approval", True, False)
    assert not is_searchable("rejected", True, False)


def test_FR_RBAC_004_p1_3_pending_version_prepare_ingest_refused() -> None:
    service, _, _ = _service()
    # Layer 1 (pipeline gate): prepare_ingest only accepts
    # uploaded/queued, so a pending version yields no task and no
    # worker pickup, even when called directly.
    assert service.prepare_ingest("ver_pending", "req_ingest", "usr_frank") is None


def test_FR_RBAC_004_p1_3_pending_document_has_no_published_chunks() -> None:
    _, _, chunks = _service()
    # Layer 2: no chunks were ever published for the pending version
    # (ingest never ran), so citation and retrieval have nothing to
    # serve even if a caller bypassed the state check.
    assert chunks.list_for_version("ver_pending") == ()


def test_FR_RBAC_004_p1_3_pending_document_invisible_to_non_admin() -> None:
    service, _, _ = _service()
    # Layer 3: the library stays unassigned, so a non-admin whose
    # visible set is {pub} cannot reach the document through detail
    # or content paths; the failure is not_found, never a leak.
    with pytest.raises(DocumentError) as excinfo:
        service.get_detail(
            "doc_pending", viewer_role="user", visible_libraries=frozenset({"pub"}),
            request_id="req_detail",
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(DocumentError) as excinfo:
        service.open_content(
            "doc_pending", viewer_role="user", visible_libraries=frozenset({"pub"}),
            request_id="req_open", purpose="preview", actor_id="usr_frank",
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_p1_3_pending_document_list_shows_no_current_version() -> None:
    service, _, _ = _service()
    # Layer 4: the list only surfaces a current AND ready version;
    # a pending version is never current-ready, so the item carries
    # no current version for anyone who can see the row at all
    # (super admins see unassigned rows; members do not).
    items = service.list_library(
        viewer_role="admin", visible_libraries=frozenset({"pub", "unassigned"})
    )
    assert [item["document_id"] for item in items] == ["doc_pending"]
    assert items[0]["current_version"] is None
    items = service.list_library(
        viewer_role="user", visible_libraries=frozenset({"pub"})
    )
    assert items == ()
