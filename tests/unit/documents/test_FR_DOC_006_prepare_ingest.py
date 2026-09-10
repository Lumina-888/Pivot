from __future__ import annotations

from fakes import pdf_bytes


def test_FR_DOC_006_prepare_ingest_starts_from_uploaded(service):
    version = service.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes(),
        title="Attendance Policy",
        actor_id="usr_admin",
        request_id="req_up",
        space="hr",
    )
    prepared = service.prepare_ingest(version.id, "req_ingest", "usr_admin")
    assert prepared is not None
    assert prepared.version.id == version.id
    assert prepared.document.id == version.document_id
    assert prepared.document.title == "Attendance Policy"
    assert prepared.document.space == "hr"
    assert prepared.content.startswith(b"%PDF")
    assert prepared.kind == "pdf"
    assert prepared.task_id
    assert service._versions.get(version.id).state == "parsing"


def test_FR_DOC_006_prepare_ingest_skips_ready(service):
    version = service.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=pdf_bytes(),
        title="Attendance Policy",
        actor_id="usr_admin",
        request_id="req_up",
    )
    service.enqueue(version.id, "req_en")
    service.worker_started(version.id, "task_1", "req_ws")
    service.parse_ok(version.id, "req_parse")
    service.apply_chunks(version.id, ["late three times"], "msg_1", "req_chunk")
    service.embedding_ok(version.id, "req_emb")
    service.publish(version.id, "req_pub")
    assert service.prepare_ingest(version.id, "req_again", "usr_admin") is None
    assert service._versions.get(version.id).state == "ready"
