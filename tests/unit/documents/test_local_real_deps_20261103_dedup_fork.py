"""2026-11-03 local-real-deps defect 4: content dedup must not
silently drop the target library, bypass approval, or leak an
unreadable document id.

Before the fix, upload() returned any sha-matching version, so a
targeted upload echoed the requested target_library_id while the
returned document stayed in its old library, and a reader-less
uploader received an existing document id. After the fix: a targeted
upload forks a fresh pending_approval version unless the old version
is still pending_approval for the same target (the S3 repeat); an
untargeted upload forks when the old document is invisible under the
same library/folder/exception channels as the read endpoints; the
plain same-document repeat (no target, visible) still returns the
existing version.
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


def _upload(service, *, target_library_id=None, viewer=None, pending_target_matches=None):
    kwargs = {}
    if viewer is not None:
        kwargs["viewer_role"] = viewer[0]
        kwargs["visible_libraries"] = viewer[1]
    if pending_target_matches is not None:
        kwargs["pending_target_matches"] = pending_target_matches
    return service.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes(),
        title="policy",
        actor_id="usr_a",
        request_id="req_up",
        target_library_id=target_library_id,
        **kwargs,
    )


def _set_library(store, document_id, library_id):
    record = store.get(document_id)
    assert record is not None
    record.library_id = library_id
    store.save(record)


def test_targeted_upload_forks_instead_of_returning_decided_version():
    service, _ = _service_with_store()
    first = _upload(service)
    assert first.state == "uploaded"
    second = _upload(service, target_library_id="dept_eng")
    assert second.id != first.id
    assert second.document_id != first.document_id
    assert second.state == "pending_approval"


def test_targeted_repeat_of_pending_same_target_returns_existing():
    service, _ = _service_with_store()
    first = _upload(service, target_library_id="dept_eng")
    assert first.state == "pending_approval"
    second = _upload(
        service,
        target_library_id="dept_eng",
        pending_target_matches=lambda document_id: True,
    )
    assert second.id == first.id
    assert second.state == "pending_approval"


def test_targeted_upload_forks_when_pending_request_targets_elsewhere():
    service, _ = _service_with_store()
    first = _upload(service, target_library_id="dept_eng")
    assert first.state == "pending_approval"
    second = _upload(
        service,
        target_library_id="dept_art",
        pending_target_matches=lambda document_id: False,
    )
    assert second.id != first.id
    assert second.document_id != first.document_id
    assert second.state == "pending_approval"


def test_untargeted_upload_forks_when_old_document_invisible():
    service, store = _service_with_store()
    first = _upload(service)
    _set_library(store, first.document_id, "dept_eng")
    second = _upload(service, viewer=("user", frozenset({"pub"})))
    assert second.id != first.id
    assert second.document_id != first.document_id
    assert second.state == "uploaded"


def test_same_document_repeat_still_returns_existing_version():
    service, store = _service_with_store()
    first = _upload(service)
    _set_library(store, first.document_id, "dept_eng")
    second = _upload(service, viewer=("user", frozenset({"dept_eng"})))
    assert second.id == first.id
    assert second.document_id == first.document_id
