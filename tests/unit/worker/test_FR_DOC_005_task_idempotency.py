from __future__ import annotations

from pivot_worker.ingest import IngestRequest
from samples import pdf_with_text


def test_FR_DOC_005_duplicate_worker_message_does_not_duplicate_index(worker):
    request = IngestRequest(
        version_id="ver_1",
        kind="pdf",
        content=pdf_with_text(),
        message_id="msg_dup",
    )
    first = worker.run(request)
    second = worker.run(request)
    assert first == second
    vectors = worker._index.published_vectors(first["content"]["generation_id"])
    assert len(vectors) == len(first["content"]["chunk_ids"])
    assert {item.payload["version_id"] for item in vectors} == {"ver_1"}
