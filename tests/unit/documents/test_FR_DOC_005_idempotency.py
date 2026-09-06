from __future__ import annotations

from fakes import pdf_bytes


def _upload(service, key=None):
    return service.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes(),
        title="policy",
        actor_id="usr_admin",
        request_id="req_up",
        idempotency_key=key,
    )


def test_FR_DOC_005_duplicate_sha_returns_existing_version(service):
    first = _upload(service)
    second = _upload(service)
    assert first.id == second.id
    assert first.document_id == second.document_id


def test_FR_DOC_005_idempotency_key_replay_returns_same_version(service):
    first = _upload(service, key="idem-1")
    second = _upload(service, key="idem-1")
    assert first.id == second.id


def test_FR_DOC_005_duplicate_worker_message_does_not_duplicate_chunks(service):
    version = _upload(service)
    service.enqueue(version.id, "req_en")
    service.worker_started(version.id, "task_1", "req_ws")
    service.parse_ok(version.id, "req_parse")
    first = service.apply_chunks(version.id, ["alpha", "beta"], "msg_1", "req_chunk")
    second = service.apply_chunks(version.id, ["alpha", "beta"], "msg_1", "req_chunk2")
    third = service.apply_chunks(version.id, ["alpha", "beta"], "msg_2", "req_chunk3")
    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
    assert [chunk.id for chunk in first] == [chunk.id for chunk in third]
    assert len(first) == 2
