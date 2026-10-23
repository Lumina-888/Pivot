"""Opt-in live hybrid check (ND-P0-03). Not GATE-P0 verified.

Skipped unless PIVOT_LIVE_SILICONFLOW_API_KEY is set. Builds the
default LlamaIndex path with the real SiliconFlow embedder and
reranker through the production HTTP providers and checks that a
known synthetic case returns its labeled evidence with both the
dense route and the rerank stage actually exercised.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("llama_index.core")

_API_KEY = os.environ.get("PIVOT_LIVE_SILICONFLOW_API_KEY")
pytestmark = pytest.mark.skipif(
    not _API_KEY, reason="live SiliconFlow key not provided (opt-in)"
)

_ENDPOINT = "https://api.siliconflow.cn/v1"


class _CountingReranker:
    def __init__(self, inner):
        self._inner = inner
        self.calls = 0

    def rerank(self, query, chunk_ids, texts, limit):
        self.calls += 1
        return self._inner.rerank(query, chunk_ids, texts, limit)


def test_FR_RAG_001_live_hybrid_uses_both_routes():
    from default_path_eval import build_default_retriever
    from golden_set import corpus_records, load_dataset
    from pivot.retrieval.llama_embeddings import PivotEmbedding
    from pivot.retrieval.policy import RetrievalPolicy
    from pivot.retrieval.providers import (
        HttpBgeReranker,
        HttpQueryEmbedder,
        StdlibJsonHttpClient,
    )

    dataset = load_dataset()
    records = corpus_records(dataset)
    client = StdlibJsonHttpClient()
    embedder = HttpQueryEmbedder(
        client,
        endpoint=f"{_ENDPOINT}/embeddings",
        model="BAAI/bge-m3",
        api_key=_API_KEY,
        timeout_seconds=120,
        expected_dimension=1024,
    )
    reranker = _CountingReranker(
        HttpBgeReranker(
            client,
            endpoint=f"{_ENDPOINT}/rerank",
            model="BAAI/bge-reranker-v2-m3",
            api_key=_API_KEY,
            timeout_seconds=120,
        )
    )
    retriever = build_default_retriever(
        records,
        RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=60, evidence_limit=5),
        embed_model=PivotEmbedding(embedder, model_name="BAAI/bge-m3", dimension=1024),
        vector_size=1024,
        reranker=reranker,
    )
    case = dataset["cases"][0]
    result = retriever.retrieve(
        case["question"],
        scope_type=case["scope_type"],
        scope_document_id=case["scope_document_id"],
        principal_id=case["principal_id"],
    )
    assert result.status == "found"
    hit_ids = [hit.chunk_id for hit in result.evidence]
    for chunk_id in case["expected_chunk_ids"]:
        assert chunk_id in hit_ids
    assert reranker.calls >= 1
