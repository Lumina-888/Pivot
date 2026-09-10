"""Runtime HTTP Embedding / bge rerank wiring. Not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.retrieval.bm25 import Bm25Retriever
from pivot.retrieval.fakes import HashingQueryEmbedder, ScriptedJsonHttpClient
from pivot.retrieval.models import ChunkRecord, RetrievalQuery
from pivot.retrieval.providers import HttpBgeReranker, HttpQueryEmbedder
from pivot.retrieval.vector import VectorStoreRetriever
from pivot.storage.adapters.qdrant import QdrantVectorStore

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "http-embedding-bge.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_PROVIDERS = _ROOT / "api" / "src" / "pivot" / "retrieval" / "providers.py"
_BOOTSTRAP = _ROOT / "api" / "src" / "pivot" / "http" / "bootstrap.py"


class _StoringQdrantClient:
    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.points: dict[str, dict[str, tuple[list[float], dict]]] = {}

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(self, collection_name: str, *, vector_size: int, distance: str) -> None:
        self.collections.add(collection_name)
        self.points.setdefault(collection_name, {})

    def upsert(self, collection_name: str, points) -> None:
        bucket = self.points.setdefault(collection_name, {})
        for point in points:
            bucket[str(point["id"])] = (list(point["vector"]), dict(point["payload"]))

    def search(self, collection_name, query_vector, limit=10, query_filter=None):
        query = list(query_vector)
        hits = []
        for pid, (vector, payload) in self.points.get(collection_name, {}).items():
            hits.append(
                SimpleNamespace(id=pid, score=_dot(query, vector), payload=payload)
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def delete(self, collection_name, points_selector=None) -> None:
        return None


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


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


def _qdrant_http_settings(**overrides: object) -> RuntimeSettings:
    return _settings(
        vector_store="qdrant",
        qdrant_endpoint="vectors.test:443",
        qdrant_collection="pivot-chunks",
        qdrant_ensure_collection=True,
        qdrant_vector_size=4,
        qdrant_distance="Cosine",
        vector_store_client=_StoringQdrantClient(),
        embedding="http",
        embedding_endpoint="https://embed.test/v1/embeddings",
        embedding_model="injected-embed-model",
        embedding_api_key="secret-embed-key",
        json_http_client=ScriptedJsonHttpClient(
            [{"data": [{"index": 0, "embedding": [1.0, 0.0, 0.0, 0.0]}]}]
        ),
        **overrides,
    )


def _policy_chunks() -> tuple[ChunkRecord, ChunkRecord]:
    return (
        ChunkRecord(
            chunk_id="chk_weak",
            version_id="ver_weak",
            document_id="doc_weak",
            text="迟到 报销发票",
            title="Travel",
            space="hr",
            ready=True,
            current=True,
            allowed=True,
            index_generation="gen_bge",
            embedding_model_version="http-embed-test",
            retrieval_config_version="runtime-injected",
        ),
        ChunkRecord(
            chunk_id="chk_strong",
            version_id="ver_strong",
            document_id="doc_strong",
            text="迟到三次记书面警告",
            title="Attendance Policy",
            space="hr",
            ready=True,
            current=True,
            allowed=True,
            index_generation="gen_bge",
            embedding_model_version="http-embed-test",
            retrieval_config_version="runtime-injected",
        ),
    )


def test_NFR_OBS_runtime_http_embedding_requires_endpoint_model_key():
    with pytest.raises(RuntimeError, match="PIVOT_EMBEDDING_ENDPOINT"):
        assemble_runtime(_settings(embedding="http"))


def test_NFR_OBS_runtime_http_embedding_requires_qdrant():
    with pytest.raises(RuntimeError, match="PIVOT_VECTOR_STORE=qdrant"):
        assemble_runtime(
            _settings(
                embedding="http",
                embedding_endpoint="https://embed.test/v1/embeddings",
                embedding_model="injected-embed-model",
                embedding_api_key="secret-embed-key",
            )
        )


def test_NFR_OBS_runtime_qdrant_http_embedder_wires():
    assembly = assemble_runtime(_qdrant_http_settings())
    assert isinstance(assembly.query_embedder, HttpQueryEmbedder)
    assert isinstance(assembly.retrieval._dense, VectorStoreRetriever)
    assert not isinstance(assembly.query_embedder, HashingQueryEmbedder)
    assert isinstance(assembly.vectors, QdrantVectorStore)


def test_FR_RAG_001_runtime_http_embedder_retrieve():
    assembly = assemble_runtime(_qdrant_http_settings())
    assembly.vectors.upsert(
        [
            {
                "vector": [1.0, 0.0, 0.0, 0.0],
                "version_id": "ver_policy",
                "chunk_id": "chk_policy",
                "document_id": "doc_policy",
                "text": "迟到三次以上记为旷工",
                "title": "Attendance Policy",
                "space": "hr",
                "ready": True,
                "current": True,
                "allowed": True,
                "index_generation": "gen_http",
                "embedding_model_version": "injected-embed-model",
                "retrieval_config_version": "runtime-injected",
            }
        ]
    )
    outcome = assembly.retrieval.retrieve(
        RetrievalQuery(text="迟到书面警告", principal_id="usr_admin")
    )
    assert outcome.status == "ok"
    assert outcome.evidence[0].chunk_id == "chk_policy"
    assert outcome.evidence[0].index_generation == "gen_http"


def test_NFR_OBS_runtime_bge_rerank_requires_endpoint_model_key():
    with pytest.raises(RuntimeError, match="PIVOT_RERANK_ENDPOINT"):
        assemble_runtime(_settings(rerank="bge"))


def test_FR_RAG_001_runtime_bge_rerank_reorders():
    def _score(url, payload, headers, timeout):
        del url, headers, timeout
        results = []
        for index, text in enumerate(payload["documents"]):
            score = 0.9 if "书面警告" in text else 0.1
            results.append({"index": index, "relevance_score": score})
        return {"results": results}

    assembly = assemble_runtime(
        _settings(
            bm25_k1=1.2,
            bm25_b=0.75,
            rerank="bge",
            rerank_endpoint="https://rerank.test/v1/rerank",
            rerank_model="injected-rerank-model",
            rerank_api_key="secret-rerank-key",
            json_http_client=ScriptedJsonHttpClient(handler=_score),
        )
    )
    assert isinstance(assembly.retrieval._reranker, HttpBgeReranker)
    assert isinstance(assembly.bm25, Bm25Retriever)
    assembly.bm25.add(_policy_chunks())
    outcome = assembly.retrieval.retrieve(
        RetrievalQuery(text="迟到", principal_id="usr_admin")
    )
    assert outcome.status == "ok"
    assert outcome.evidence[0].chunk_id == "chk_strong"


def test_GATE_P0_002_not_verified_by_http_embedding_bge():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    providers = _PROVIDERS.read_text(encoding="utf-8")
    bootstrap = _BOOTSTRAP.read_text(encoding="utf-8")
    assert "GATE-P0-002" in evidence
    assert "unverified" in evidence.lower()
    assert "siliconflow" not in providers.lower()
    assert "siliconflow" not in bootstrap.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-002" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
