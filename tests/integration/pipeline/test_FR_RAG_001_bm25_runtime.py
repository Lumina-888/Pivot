"""Runtime BM25/rerank wiring. Not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path

import pytest
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.retrieval.bm25 import Bm25Reranker, Bm25Retriever
from pivot.retrieval.fakes import KeywordRetriever, OverlapReranker
from pivot.retrieval.models import ChunkRecord, RetrievalQuery

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "bm25-rerank.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_BOOTSTRAP = _ROOT / "api" / "src" / "pivot" / "http" / "bootstrap.py"


def _settings(**overrides: object) -> RuntimeSettings:
    values: dict[str, object] = {
        "storage": "memory",
        "token_secret": "runtime-test-secret",
        "access_ttl": 60,
        "refresh_ttl": 3600,
        "export_ttl": 3600,
        "download_ttl": 300,
        "export_public_base": "https://files.pivot.test",
        "bootstrap_username": "admin",
        "bootstrap_password": "runtime-admin-password",
        "retrieval_k": 4,
        "argon2_time_cost": 1,
        "argon2_memory_cost": 8,
        "argon2_parallelism": 1,
    }
    values.update(overrides)
    return RuntimeSettings(**values)


def _policy_chunk() -> ChunkRecord:
    return ChunkRecord(
        chunk_id="chk_policy",
        version_id="ver_policy",
        document_id="doc_policy",
        text="迟到三次以上记为旷工",
        title="Attendance Policy",
        space="hr",
        ready=True,
        current=True,
        allowed=True,
        index_generation="gen_bm25",
        embedding_model_version="hash-embed-test",
        retrieval_config_version="runtime-injected",
    )


def test_NFR_OBS_runtime_bm25_requires_both_params():
    with pytest.raises(RuntimeError, match="PIVOT_BM25_K1"):
        assemble_runtime(_settings(bm25_k1=1.2))


def test_NFR_OBS_runtime_rejects_unwired_rerank():
    with pytest.raises(RuntimeError, match="unsupported PIVOT_RERANK"):
        assemble_runtime(_settings(rerank="openai"))


def test_NFR_OBS_runtime_bm25_wires_retriever():
    assembly = assemble_runtime(_settings(bm25_k1=1.2, bm25_b=0.75))
    assert isinstance(assembly.bm25, Bm25Retriever)
    assert isinstance(assembly.retrieval._bm25, Bm25Retriever)
    defaulted = assemble_runtime(_settings())
    assert isinstance(defaulted.bm25, KeywordRetriever)


def test_FR_RAG_001_runtime_bm25_retrieve_after_add():
    assembly = assemble_runtime(_settings(bm25_k1=1.2, bm25_b=0.75, rerank="bm25"))
    assert isinstance(assembly.retrieval._reranker, Bm25Reranker)
    assembly.bm25.add((_policy_chunk(),))
    outcome = assembly.retrieval.retrieve(
        RetrievalQuery(text="迟到", principal_id="usr_admin")
    )
    assert outcome.status == "ok"
    assert outcome.evidence[0].chunk_id == "chk_policy"
    hits = assembly.retrieval.search_documents(
        RetrievalQuery(text="迟到", principal_id="usr_admin")
    )
    assert hits[0].document_id == "doc_policy"


def test_FR_RAG_001_runtime_overlap_rerank_wires():
    assembly = assemble_runtime(_settings(rerank="overlap"))
    assert isinstance(assembly.retrieval._reranker, OverlapReranker)


def test_GATE_P0_002_not_verified_by_bm25_rerank():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    bootstrap = _BOOTSTRAP.read_text(encoding="utf-8")
    bm25_src = (_ROOT / "api" / "src" / "pivot" / "retrieval" / "bm25.py").read_text(
        encoding="utf-8"
    )
    assert "GATE-P0-002" in evidence
    assert "unverified" in evidence.lower()
    assert "jieba" not in bootstrap.lower() or "not jieba" in bootstrap.lower()
    assert "bge-reranker" not in bm25_src
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-002" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
