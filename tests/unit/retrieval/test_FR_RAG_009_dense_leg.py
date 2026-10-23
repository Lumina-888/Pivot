"""FR-RAG-009: the LlamaIndex dense leg must actually return hits.

Regression guard for the defect found during line-three calibration:
_LlamaDense.search called index.as_retriever(node_ids=...), which
raises TypeError on llama-index-core 0.11.23 (duplicate node_ids), so
every dense search silently degraded to BM25-only while token-friendly
tests stayed green. These tests use controlled vectors where the
query shares no tokens with the target chunk, so only a live dense
leg can produce the expected evidence. Not GATE-P0 verified.
"""

from __future__ import annotations

import pytest

pytest.importorskip("llama_index.core")

from llama_index.core import VectorStoreIndex  # noqa: E402
from llama_index.core.embeddings import BaseEmbedding  # noqa: E402
from llama_index.core.schema import TextNode  # noqa: E402
from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever, _LlamaDense  # noqa: E402
from pivot.retrieval.models import RetrievalQuery  # noqa: E402
from pivot.retrieval.policy import RetrievalPolicy  # noqa: E402
from pivot.retrieval.tokenize import SimpleLexTokenizer  # noqa: E402

_VECTORS = {
    "zephyr quill lantern": [1.0, 0.0, 0.0],
    "magnet copper willow": [0.0, 1.0, 0.0],
    "harbor emblem": [1.0, 0.0, 0.0],
}


def _lookup(text: str) -> list[float]:
    # Node embedding input carries metadata ahead of the chunk text, so
    # match on the known chunk text the input contains.
    for known, vector in _VECTORS.items():
        if known in text:
            return vector
    raise KeyError(text)


class _DictEmbedding(BaseEmbedding):
    def _get_query_embedding(self, query: str) -> list[float]:
        return _lookup(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return _lookup(text)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embedding(text)


def _node(chunk_id: str, text: str, document_id: str) -> TextNode:
    return TextNode(
        id_=chunk_id,
        text=text,
        extra_info={
            "document_id": document_id,
            "version_id": f"version-{document_id}",
            "locator": "第一条",
            "ready": True,
            "current": True,
            "allowed": True,
            "expired": False,
            "deleted": False,
            "external_llm_allowed": True,
            "index_generation": "test-generation-1",
            "embedding_model_version": "dict-3",
            "retrieval_config_version": "test-hybrid-1",
        },
    )


def _retriever(cutoff: float) -> LlamaIndexRetriever:
    nodes = [
        _node("chunk-target", "zephyr quill lantern", "doc-target"),
        _node("chunk-other", "magnet copper willow", "doc-other"),
    ]
    index = VectorStoreIndex(nodes, embed_model=_DictEmbedding())
    return LlamaIndexRetriever(
        index,
        policy=RetrievalPolicy(dense_k=5, bm25_k=5, rrf_k=60, evidence_limit=5),
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=1.2,
        bm25_b=0.75,
        dense_score_cutoff=cutoff,
        authorize=lambda principal, document, version: True,
    )


def test_FR_RAG_009_dense_leg_returns_semantic_only_hit():
    result = _retriever(cutoff=0.5).retrieve(
        "harbor emblem",
        scope_type="global",
        scope_document_id=None,
        principal_id="user-1",
    )
    assert result.status == "found"
    assert [hit.chunk_id for hit in result.evidence] == ["chunk-target"]


def test_FR_RAG_009_dense_search_returns_scored_hits():
    retriever = _retriever(cutoff=0.0)
    query = RetrievalQuery("harbor emblem", "user-1", "global", None)
    nodes, _corpus = retriever._eligible_nodes(query)
    dense = _LlamaDense(retriever._index, nodes, retriever._cutoff)
    hits = dense.search("harbor emblem", 5)
    assert hits[0].chunk_id == "chunk-target"
    assert hits[0].score == pytest.approx(1.0)


def test_FR_RAG_009_zero_similarity_is_not_a_dense_candidate():
    result = _retriever(cutoff=0.0).retrieve(
        "harbor emblem",
        scope_type="global",
        scope_document_id=None,
        principal_id="user-1",
    )
    assert [hit.chunk_id for hit in result.evidence] == ["chunk-target"]


def test_FR_RAG_009_dense_ties_break_by_chunk_id(monkeypatch):
    # ANN traversal returns tied scores in arbitrary order; the dense
    # leg must emit a deterministic (score desc, chunk_id asc) order so
    # downstream fusion ranks do not depend on the traversal.
    import pivot.retrieval.llama_index_retriever as module

    class _Hit:
        def __init__(self, node_id: str, score: float) -> None:
            self.node = TextNode(id_=node_id, text="x")
            self.score = score

    class _FakeRetriever:
        def retrieve(self, query: str):
            return [_Hit("n-b", 0.5), _Hit("n-a", 0.5), _Hit("n-c", 0.9)]

    monkeypatch.setattr(
        module,
        "VectorIndexRetriever",
        lambda **kwargs: _FakeRetriever(),
    )
    dense = _LlamaDense(
        object(),
        {
            "chunk-a": TextNode(id_="n-a", text="x"),
            "chunk-b": TextNode(id_="n-b", text="x"),
            "chunk-c": TextNode(id_="n-c", text="x"),
        },
        0.0,
    )
    hits = dense.search("anything", 3)
    assert [(hit.chunk_id, hit.score) for hit in hits] == [
        ("chunk-c", 0.9),
        ("chunk-a", 0.5),
        ("chunk-b", 0.5),
    ]
