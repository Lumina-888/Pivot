"""Runtime retrieval consumes Qdrant VectorStore. Not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.retrieval.fakes import HashingQueryEmbedder, KeywordRetriever
from pivot.retrieval.models import RetrievalQuery
from pivot.retrieval.vector import VectorStoreRetriever
from pivot.storage.adapters.qdrant import QdrantVectorStore

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "qdrant-retrieval.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_VECTOR_SRC = _ROOT / "api" / "src" / "pivot" / "retrieval" / "vector.py"
_BOOTSTRAP_SRC = _ROOT / "api" / "src" / "pivot" / "http" / "bootstrap.py"


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
            if not _payload_matches(payload, query_filter):
                continue
            hits.append(SimpleNamespace(id=pid, score=_cosine(query, vector), payload=payload))
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def delete(self, collection_name, points_selector=None) -> None:
        return None


def _payload_matches(payload: dict, selector: dict | None) -> bool:
    if not selector:
        return True
    for condition in selector.get("must", ()):
        if payload.get(condition["key"]) != condition["match"]["value"]:
            return False
    return True


def _cosine(left: list[float], right: list[float]) -> float:
    score = sum(a * b for a, b in zip(left, right, strict=False))
    norm_left = sum(value * value for value in left) ** 0.5
    norm_right = sum(value * value for value in right) ** 0.5
    if norm_left == 0 or norm_right == 0:
        return 0.0
    return score / (norm_left * norm_right)


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
        "vector_store": "qdrant",
        "qdrant_endpoint": "vectors.test:443",
        "qdrant_collection": "pivot-chunks",
        "qdrant_ensure_collection": True,
        "qdrant_vector_size": 4,
        "qdrant_distance": "Cosine",
        "vector_store_client": _StoringQdrantClient(),
    }
    values.update(overrides)
    return RuntimeSettings(**values)


def _upsert_policy(assembly, *, ready: bool = True, chunk_id: str = "chk_policy") -> None:
    embedder = assembly.query_embedder
    assert embedder is not None
    text = "late three times written warning."
    assembly.vectors.upsert(
        [
            {
                "vector": embedder.embed([text])[0],
                "version_id": f"ver_{chunk_id}",
                "chunk_id": chunk_id,
                "document_id": f"doc_{chunk_id}",
                "text": text,
                "title": "Attendance Policy",
                "space": "hr",
                "ready": ready,
                "current": ready,
                "allowed": True,
                "index_generation": "gen_runtime",
                "embedding_model_version": "hash-embed-test",
                "retrieval_config_version": "runtime-injected",
            }
        ]
    )


def test_NFR_OBS_runtime_qdrant_retrieval_requires_vector_size():
    client = _StoringQdrantClient()
    client.collections.add("pivot-chunks")
    with pytest.raises(RuntimeError, match="PIVOT_QDRANT_VECTOR_SIZE"):
        assemble_runtime(
            _settings(
                vector_store_client=client,
                qdrant_ensure_collection=False,
                qdrant_vector_size=None,
                qdrant_distance=None,
            )
        )


def test_NFR_OBS_runtime_qdrant_wires_dense_retriever():
    assembly = assemble_runtime(_settings())
    assert assembly.vector_store == "qdrant"
    assert isinstance(assembly.vectors, QdrantVectorStore)
    assert isinstance(assembly.query_embedder, HashingQueryEmbedder)
    assert isinstance(assembly.retrieval._dense, VectorStoreRetriever)
    assert isinstance(assembly.retrieval._bm25, KeywordRetriever)


def test_FR_SEARCH_001_runtime_qdrant_search_roundtrip():
    assembly = assemble_runtime(_settings())
    _upsert_policy(assembly)
    client = TestClient(assembly.app, base_url="https://testserver")
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_qdrant_login"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    response = client.get(
        "/api/v1/search",
        params={"q": "late three times written warning."},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_qdrant_search"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("pagination") is None
    assert body["items"]
    hit = body["items"][0]
    assert hit["document_id"] == "doc_chk_policy"
    assert hit["title"] == "Attendance Policy"
    assert "late three times" in hit["snippet"]
    dumped = str(body).lower() + str(response.headers).lower()
    assert "vectors.test" not in dumped
    assert "qdrant" not in dumped


def test_FR_RAG_001_runtime_qdrant_retrieve_evidence():
    assembly = assemble_runtime(_settings())
    _upsert_policy(assembly)
    outcome = assembly.retrieval.retrieve(
        RetrievalQuery(text="late three times written warning.", principal_id="usr_admin")
    )
    assert outcome.status == "ok"
    assert outcome.evidence[0].chunk_id == "chk_policy"
    assert outcome.evidence[0].index_generation == "gen_runtime"


def test_FR_RAG_002_runtime_qdrant_excludes_not_ready_payload():
    assembly = assemble_runtime(_settings())
    _upsert_policy(assembly, ready=True, chunk_id="chk_ready")
    _upsert_policy(assembly, ready=False, chunk_id="chk_draft")
    outcome = assembly.retrieval.retrieve(
        RetrievalQuery(text="late three times written warning.", principal_id="usr_admin")
    )
    ids = {item.chunk_id for item in outcome.evidence}
    assert "chk_ready" in ids
    assert "chk_draft" not in ids


def test_FR_RAG_001_runtime_qdrant_does_not_freeze_k_or_distance():
    vector_src = _VECTOR_SRC.read_text(encoding="utf-8")
    bootstrap_src = _BOOTSTRAP_SRC.read_text(encoding="utf-8")
    assert "top-50" not in vector_src
    assert "Cosine" not in vector_src
    assert "retrieval_k=50" not in bootstrap_src
    assert "dense_k=50" not in bootstrap_src


def test_GATE_P0_002_not_verified_by_qdrant_retrieval():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-002" in evidence
    assert "unverified" in evidence.lower()
    assert "fake" in evidence.lower() or "HashingQueryEmbedder" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-002" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
