from __future__ import annotations

from fakes import ooxml, pdf_bytes


def _pipeline_to(service, version, stage):
    service.enqueue(version.id, "req_en")
    service.worker_started(version.id, "task_1", "req_ws")
    if stage == "parse_failed":
        return service.parse_error(version.id, "CORRUPTED_FILE", "req_err")
    service.parse_ok(version.id, "req_parse")
    service.apply_chunks(version.id, ["chunk-a"], "msg_1", "req_chunk")
    if stage == "embed_failed":
        return service.embedding_error(version.id, "req_emb_err")
    service.embedding_ok(version.id, "req_emb")
    if stage == "indexed":
        return service._versions.get(version.id)
    return service.publish(version.id, "req_pub")


def test_FR_DOC_006_failed_new_version_does_not_replace_current(service):
    first = service.upload(
        filename="v1.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes(),
        title="v1",
        actor_id="usr_admin",
        request_id="req_1",
    )
    published = _pipeline_to(service, first, "ready")
    assert published.current is True
    assert published.state == "ready"
    second = service.upload(
        filename="v2.docx",
        declared_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content=ooxml("docx"),
        title="v2",
        actor_id="usr_admin",
        request_id="req_2",
    )
    failed = _pipeline_to(service, second, "parse_failed")
    assert failed.current is False
    assert failed.state == "parse_failed"
    assert service._versions.get(first.id).current is True
    assert first.id in service.searchable_version_ids()
    assert second.id not in service.searchable_version_ids()


def test_FR_DOC_006_successful_publish_makes_single_current(service):
    first = service.upload(
        filename="a.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes(),
        title="a",
        actor_id="usr_admin",
        request_id="req_1",
    )
    _pipeline_to(service, first, "ready")
    second = service.upload(
        filename="b.docx",
        declared_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content=ooxml("docx"),
        title="b",
        actor_id="usr_admin",
        request_id="req_2",
    )
    # Same SHA would be idempotent; different content so new version on new document.
    # Publish second independently then attach as new version of first by publishing
    # after copying document_id in this unit: simulate new version on same document.
    second.document_id = first.document_id
    service._versions.save(second)
    published = _pipeline_to(service, second, "ready")
    assert published.current is True
    assert service._versions.get(first.id).current is False
    assert service.searchable_version_ids() == (second.id,)
