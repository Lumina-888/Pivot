"""HTTP bge reranker. Limit/threshold stay injected or omitted, not frozen."""

from __future__ import annotations

from pathlib import Path

import pytest
from pivot.retrieval.fakes import FailingReranker, KeywordRetriever, ScriptedJsonHttpClient
from pivot.retrieval.models import ChunkRecord, RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.ports import RetrieverError
from pivot.retrieval.providers import HttpBgeReranker
from pivot.retrieval.service import RetrievalService

_SRC = Path(__file__).resolve().parents[3] / "api" / "src" / "pivot" / "retrieval"


def _chunk(chunk_id: str, text: str) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        version_id=f"ver_{chunk_id}",
        document_id=f"doc_{chunk_id}",
        text=text,
        title="Attendance Policy",
        space="hr",
        ready=True,
        current=True,
        allowed=True,
        index_generation="gen_bge",
        embedding_model_version="http-embed-test",
        retrieval_config_version="bge-test",
    )


def _reranker(client, **overrides) -> HttpBgeReranker:
    values = dict(
        endpoint="https://rerank.test/v1/rerank",
        model="injected-rerank-model",
        api_key="secret-rerank-key",
        timeout_seconds=2.5,
    )
    values.update(overrides)
    return HttpBgeReranker(client, **values)


def test_FR_RAG_001_bge_rerank_reorders_by_provider_score():
    client = ScriptedJsonHttpClient(
        [
            {
                "results": [
                    {"index": 1, "relevance_score": 0.91},
                    {"index": 0, "relevance_score": 0.12},
                ]
            }
        ]
    )
    ranked = _reranker(client).rerank(
        "迟到书面警告",
        ("chk_weak", "chk_strong"),
        {
            "chk_weak": "差旅报销发票",
            "chk_strong": "迟到三次记书面警告",
        },
        2,
    )
    assert [hit.chunk_id for hit in ranked] == ["chk_strong", "chk_weak"]
    assert ranked[0].source == "rerank"
    assert ranked[0].score >= ranked[1].score
    call = client.calls[0]
    assert call["url"] == "https://rerank.test/v1/rerank"
    assert call["payload"]["model"] == "injected-rerank-model"
    assert call["payload"]["query"] == "迟到书面警告"
    assert call["payload"]["documents"] == ["差旅报销发票", "迟到三次记书面警告"]
    assert call["headers"]["Authorization"] == "Bearer secret-rerank-key"
    assert call["timeout"] == 2.5


def test_FR_RAG_001_bge_rerank_uses_injected_limit():
    client = ScriptedJsonHttpClient(
        [
            {
                "results": [
                    {"index": 2, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.8},
                    {"index": 1, "relevance_score": 0.7},
                ]
            }
        ]
    )
    ranked = _reranker(client, timeout_seconds=None).rerank(
        "迟到",
        ("chk_a", "chk_b", "chk_c"),
        {"chk_a": "a", "chk_b": "b", "chk_c": "c"},
        1,
    )
    assert len(ranked) == 1
    assert ranked[0].chunk_id == "chk_c"


def test_FR_RAG_001_bge_rerank_does_not_freeze_threshold():
    src = (_SRC / "providers.py").read_text(encoding="utf-8")
    lowered = src.lower()
    assert "siliconflow" not in lowered
    assert "bge-reranker-v2-m3" not in lowered
    assert "top-5" not in src
    assert "top-8" not in src
    assert "threshold" not in lowered
    assert "0.5" not in src


def test_FR_RAG_001_bge_rerank_does_not_leak_api_key():
    client = ScriptedJsonHttpClient(error=RuntimeError("rerank 429"))
    with pytest.raises(RetrieverError) as caught:
        _reranker(client).rerank("迟到", ("chk_a",), {"chk_a": "迟到"}, 1)
    assert caught.value.code == "PROVIDER_TEMPORARY_ERROR"
    assert "secret-rerank-key" not in str(caught.value)
    assert "secret-rerank-key" not in repr(caught.value)


def test_FR_RAG_004_bge_rerank_failure_falls_back_to_fused():
    records = (
        _chunk("chk_policy", "迟到三次以上记为旷工"),
        _chunk("chk_other", "差旅报销需提供发票"),
    )
    service = RetrievalService(
        corpus=records,
        dense=KeywordRetriever(records, "dense"),
        bm25=KeywordRetriever(records, "bm25"),
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=4, evidence_limit=4),
        reranker=FailingReranker(),
    )
    outcome = service.retrieve(RetrievalQuery(text="迟到", principal_id="usr_alice"))
    assert outcome.status == "ok"
    assert "rerank_failed" in outcome.warnings
    assert outcome.evidence
    assert any(
        call.provider == "rerank" and call.status == "failed"
        for call in service.provider_calls
    )
