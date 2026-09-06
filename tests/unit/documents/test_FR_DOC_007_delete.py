from __future__ import annotations

import pytest
from fakes import pdf_bytes
from pivot.documents.errors import DocumentError
from pivot.domain.document_state import next_state


def _ready(service):
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
    service.parse_ok(version.id, "req_parse")
    service.apply_chunks(version.id, ["body"], "msg_1", "req_chunk")
    service.embedding_ok(version.id, "req_emb")
    return service.publish(version.id, "req_pub")


def test_FR_DOC_007_delete_unpublishes_before_cleanup(service):
    version = _ready(service)
    assert version.id in service.searchable_version_ids()
    document = service.request_delete(version.document_id, "req_del", "usr_admin")
    assert document.deleted_at is not None
    assert service.visible_in_library(document.id) is False
    assert version.id not in service.searchable_version_ids()
    pending = service._versions.get(version.id)
    assert pending.state == "delete_pending"
    assert pending.current is False


def test_FR_DOC_007_cleanup_failure_can_retry(service):
    version = _ready(service)
    service.request_delete(version.document_id, "req_del", "usr_admin")
    failed = service.cleanup_error(version.id, "req_fail")
    assert failed.state == "delete_failed"
    retried = service.retry_cleanup(version.id, "req_retry")
    assert retried.state == "delete_pending"
    deleted = service.cleanup_ok(version.id, "req_ok")
    assert deleted.state == "deleted"
    with pytest.raises(DocumentError):
        next_state("deleted", "validation_ok", "req_revive")
