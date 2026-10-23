"""FR-RAG-008 relevance gate: strong-signal floor, rerank pool, per-doc cap.

Defaults keep every gate off (current behavior). With floors configured, a
candidate survives only on a strong signal (rerank score at or above the
rerank floor, or dense score at or above the dense floor); when nothing
survives, retrieval reports empty so callers refuse instead of answering
from irrelevant evidence. Not GATE-P0 verified.
"""

from __future__ import annotations

from corpus import chunk
from pivot.retrieval.models import RankedHit, RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService

_PRINCIPAL = "user-1"


class _StaticRetriever:
    def __init__(self, scores: dict[str, float], source: str) -> None:
        self._scores = scores
        self._source = source

    def search(self, query: str, k: int) -> tuple[RankedHit, ...]:
        ranked = sorted(self._scores.items(), key=lambda item: -item[1])
        return tuple(
            RankedHit(chunk_id, score, self._source) for chunk_id, score in ranked[:k]
        )


class _StaticReranker:
    def __init__(self, scores: dict[str, float]) -> None:
        self._scores = scores
        self.limits: list[int] = []

    def rerank(self, query, chunk_ids, texts, limit):
        self.limits.append(limit)
        ranked = sorted(
            (cid for cid in chunk_ids if cid in self._scores),
            key=lambda cid: -self._scores[cid],
        )
        return tuple(
            RankedHit(cid, self._scores[cid], "rerank") for cid in ranked[:limit]
        )


def _records():
    return (
        chunk(chunk_id="chk_strong", document_id="doc_strong", text="出差申请规则 强相关"),
        chunk(chunk_id="chk_weak", document_id="doc_weak", text="出差申请规则 弱相关诱饵"),
        chunk(chunk_id="chk_dense", document_id="doc_dense", text="出差申请规则 向量强重排弱"),
    )


def _service(policy: RetrievalPolicy, *, reranker=None, dense=None) -> RetrievalService:
    records = _records()
    return RetrievalService(
        corpus=records,
        dense=dense
        or _StaticRetriever(
            {"chk_strong": 0.9, "chk_weak": 0.2, "chk_dense": 0.85}, "dense"
        ),
        bm25=_StaticRetriever(
            {"chk_strong": 3.0, "chk_weak": 2.0, "chk_dense": 1.0}, "bm25"
        ),
        policy=policy,
        reranker=reranker,
    )


def _query() -> RetrievalQuery:
    return RetrievalQuery("出差申请规则", _PRINCIPAL, "global", None)


def _policy(**overrides) -> RetrievalPolicy:
    values = {"dense_k": 8, "bm25_k": 8, "rrf_k": 60, "evidence_limit": 5}
    values.update(overrides)
    return RetrievalPolicy(**values)


def test_FR_RAG_008_gates_default_off_keep_current_behavior():
    reranker = _StaticReranker({"chk_strong": 0.95, "chk_weak": 0.1, "chk_dense": 0.05})
    outcome = _service(_policy(), reranker=reranker).retrieve(_query())
    assert outcome.status == "ok"
    assert {item.chunk_id for item in outcome.evidence} == {
        "chk_strong",
        "chk_weak",
        "chk_dense",
    }


def test_FR_RAG_008_rerank_floor_filters_weak_candidates():
    reranker = _StaticReranker({"chk_strong": 0.95, "chk_weak": 0.1, "chk_dense": 0.05})
    outcome = _service(_policy(rerank_floor=0.5), reranker=reranker).retrieve(_query())
    assert outcome.status == "ok"
    assert [item.chunk_id for item in outcome.evidence] == ["chk_strong"]


def test_FR_RAG_008_dense_floor_rescues_low_rerank_candidate():
    reranker = _StaticReranker({"chk_strong": 0.95, "chk_weak": 0.1, "chk_dense": 0.05})
    outcome = _service(
        _policy(rerank_floor=0.5, dense_floor=0.8), reranker=reranker
    ).retrieve(_query())
    assert {item.chunk_id for item in outcome.evidence} == {"chk_strong", "chk_dense"}


def test_FR_RAG_008_all_filtered_returns_empty():
    reranker = _StaticReranker({"chk_strong": 0.3, "chk_weak": 0.1, "chk_dense": 0.05})
    outcome = _service(_policy(rerank_floor=0.5), reranker=reranker).retrieve(_query())
    assert outcome.status == "empty"
    assert outcome.evidence == ()


def test_FR_RAG_008_dense_floor_applies_without_reranker():
    outcome = _service(_policy(dense_floor=0.8)).retrieve(_query())
    assert {item.chunk_id for item in outcome.evidence} == {"chk_strong", "chk_dense"}


def test_FR_RAG_008_rerank_pool_widens_candidates_beyond_evidence_limit():
    records = tuple(
        chunk(chunk_id=f"chk_p{i}", document_id=f"doc_p{i}", text=f"出差申请规则 候选{i}")
        for i in range(4)
    )
    dense_scores = {f"chk_p{i}": 0.9 - i * 0.01 for i in range(4)}
    rerank_scores = {"chk_p0": 0.9, "chk_p1": 0.8, "chk_p2": 0.99, "chk_p3": 0.7}
    reranker = _StaticReranker(rerank_scores)
    service = RetrievalService(
        corpus=records,
        dense=_StaticRetriever(dense_scores, "dense"),
        bm25=_StaticRetriever(dense_scores, "bm25"),
        policy=_policy(evidence_limit=2, rerank_pool=4),
        reranker=reranker,
    )
    outcome = service.retrieve(_query())
    assert reranker.limits == [4]
    assert [item.chunk_id for item in outcome.evidence] == ["chk_p2", "chk_p0"]


def test_FR_RAG_008_per_document_cap_limits_final_selection():
    records = tuple(
        chunk(chunk_id=f"chk_m{i}", document_id="doc_multi", text=f"出差申请规则 同文档{i}")
        for i in range(3)
    ) + (chunk(chunk_id="chk_other", document_id="doc_other", text="出差申请规则 另一文档"),)
    scores = {"chk_m0": 0.95, "chk_m1": 0.9, "chk_m2": 0.85, "chk_other": 0.8}
    service = RetrievalService(
        corpus=records,
        dense=_StaticRetriever(scores, "dense"),
        bm25=_StaticRetriever(scores, "bm25"),
        policy=_policy(evidence_limit=5, per_doc_cap=1),
        reranker=_StaticReranker(scores),
    )
    outcome = service.retrieve(_query())
    assert {item.chunk_id for item in outcome.evidence} == {"chk_m0", "chk_other"}
