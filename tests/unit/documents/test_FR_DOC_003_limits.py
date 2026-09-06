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
from pivot.documents.ports import ResourceLimits
from pivot.documents.service import DocumentService


def test_FR_DOC_003_resource_limit_is_injected_not_frozen():
    service = DocumentService(
        documents=MemoryDocuments(),
        versions=MemoryVersions(),
        chunks=MemoryChunks(),
        tasks=MemoryTasks(),
        objects=MemoryObjects(),
        audits=MemoryAudits(),
        limits=ResourceLimits(max_bytes=8),
    )
    with pytest.raises(DocumentError) as error:
        service.upload(
            filename="a.pdf",
            declared_mime="application/pdf",
            content=pdf_bytes(),
            title="a",
            actor_id="usr_admin",
            request_id="req_lim",
        )
    assert error.value.code == "RESOURCE_LIMIT"


def test_FR_DOC_004_failed_version_is_not_searchable(service):
    version = service.upload(
        filename="a.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes(),
        title="a",
        actor_id="usr_admin",
        request_id="req_up",
    )
    service.enqueue(version.id, "req_en")
    service.worker_started(version.id, "task_1", "req_ws")
    failed = service.parse_error(version.id, "ENCRYPTED_FILE", "req_err")
    assert failed.state == "parse_failed"
    assert failed.current is False
    assert failed.id not in service.searchable_version_ids()
