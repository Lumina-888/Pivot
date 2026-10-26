"""S3: DocumentService.upload with a target library (FR-RBAC-004,
ADR-019 D1/D2).

A fresh targeted upload is born pending_approval with its bytes under
the quarantine key; an untargeted upload keeps the old uploaded state.
Idempotent repeats return the existing version untouched: a repeat
never flips state and therefore never spawns a second request (the
route's pending-request gate relies on this).
"""

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


def _service():
    objects = MemoryObjects()
    service = DocumentService(
        documents=MemoryDocuments(),
        versions=MemoryVersions(),
        chunks=MemoryChunks(),
        tasks=MemoryTasks(),
        objects=objects,
        audits=MemoryAudits(),
    )
    return service, objects


def _upload(service, content, *, target=None, key=None):
    return service.upload(
        filename="handbook.pdf",
        declared_mime="application/pdf",
        content=content,
        title="handbook",
        actor_id="usr_frank",
        request_id="req_up",
        idempotency_key=key,
        target_library_id=target,
    )


def test_FR_RBAC_004_p1_3_upload_target_born_pending_approval() -> None:
    service, objects = _service()
    content = pdf_bytes() + b"targeted"
    version = _upload(service, content, target="dept_eng")
    assert version.state == "pending_approval"
    assert version.storage_key == f"quarantine/{version.document_id}/{version.id}"
    assert objects.get(version.storage_key) == content
    # Pending versions never enter the pipeline, even if called.
    assert service.prepare_ingest(version.id, "req_ing", "usr_frank") is None


def test_FR_RBAC_004_p1_3_upload_without_target_stays_uploaded() -> None:
    service, _ = _service()
    version = _upload(service, pdf_bytes() + b"plain")
    assert version.state == "uploaded"
    assert service.prepare_ingest(version.id, "req_ing", "usr_frank") is not None


def test_FR_RBAC_004_p1_3_upload_repeat_never_flips_state() -> None:
    service, _ = _service()
    content = pdf_bytes() + b"repeat"
    first = _upload(service, content, target="dept_eng")
    assert first.state == "pending_approval"
    # Same bytes, retried with the same target: the existing version
    # comes back untouched, so the route creates no second request.
    again = _upload(service, content, target="dept_eng")
    assert again.id == first.id
    assert again.state == "pending_approval"
    # And a repeat without a target does not flip it back either.
    plain = _upload(service, content)
    assert plain.id == first.id
    assert plain.state == "pending_approval"
