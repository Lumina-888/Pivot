from __future__ import annotations

from pivot.qa.ports import EvidenceHit, RetrievalResult


class StaticRetriever:
    def __init__(self, result: RetrievalResult) -> None:
        self.result = result
        self.calls: list[dict] = []

    def retrieve(self, question, *, scope_type, scope_document_id, principal_id):
        self.calls.append(
            {
                "question": question,
                "scope_type": scope_type,
                "scope_document_id": scope_document_id,
                "principal_id": principal_id,
            }
        )
        return self.result


HIT_A = EvidenceHit(
    chunk_id="chk_a",
    document_id="doc_a",
    version_id="ver_a",
    text="迟到三次以上记为旷工",
    locator="page=1",
)


def ok_retriever() -> StaticRetriever:
    return StaticRetriever(RetrievalResult(status="ok", evidence=(HIT_A,)))


def empty_retriever() -> StaticRetriever:
    return StaticRetriever(RetrievalResult(status="empty", evidence=()))
