"""Runtime ingest publishes to Qdrant VectorStore. Not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from harness import POLICY_TEXT, FixturePdfParser, policy_pdf
from pivot.chunking import ChunkingPolicy, ChunkSplitter
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.parsing.registry import ParserRegistry
from pivot.retrieval.fakes import HashingQueryEmbedder
from pivot.retrieval.models import RetrievalQuery
from pivot.retrieval.vector import VectorStoreRetriever
from pivot.storage.adapters.qdrant import QdrantVectorStore
from pivot_worker.index import IndexPublisher
from pivot_worker.ingest import IngestRequest, IngestWorker

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "ingest-qdrant.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"


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
            hits.append(SimpleNamespace(id=pid, score=_dot(query, vector), payload=payload))
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


def _ingest(assembly) -> dict:
    assert assembly.index is not None
    assert assembly.ingest_embedding is not None
    worker = IngestWorker(
        parsers=ParserRegistry({"pdf": FixturePdfParser()}),
        splitter=ChunkSplitter(ChunkingPolicy(max_chars=80, overlap_chars=8)),
        embedding=assembly.ingest_embedding,
        index=assembly.index,
        dimension=4,
    )
    return worker.run(
        IngestRequest(
            version_id="ver_policy",
            document_id="doc_policy",
            kind="pdf",
            content=policy_pdf(),
            message_id="msg_runtime_ingest",
            title="Attendance Policy",
            space="hr",
            embedding_model_version="hash-embed-test",
            retrieval_config_version="runtime-injected",
        )
    )


def test_NFR_OBS_runtime_qdrant_wires_index_publisher():
    assembly = assemble_runtime(_settings())
    assert assembly.vector_store == "qdrant"
    assert isinstance(assembly.vectors, QdrantVectorStore)
    assert isinstance(assembly.index, IndexPublisher)
    assert isinstance(assembly.ingest_embedding, HashingQueryEmbedder)
    assert assembly.ingest_embedding is assembly.query_embedder
    assert isinstance(assembly.retrieval._dense, VectorStoreRetriever)


def test_FR_DOC_006_runtime_ingest_qdrant_search_roundtrip():
    assembly = assemble_runtime(_settings())
    result = _ingest(assembly)
    assert result["status"] == "ok"
    client = TestClient(assembly.app, base_url="https://testserver")
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_ingest_login"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    response = client.get(
        "/api/v1/search",
        params={"q": "late three times written warning."},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_ingest_search"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("pagination") is None
    assert body["items"]
    hit = body["items"][0]
    assert hit["document_id"] == "doc_policy"
    assert hit["title"] == "Attendance Policy"
    assert "late three times" in hit["snippet"]
    dumped = str(body).lower() + str(response.headers).lower()
    assert "vectors.test" not in dumped
    assert "qdrant" not in dumped


def test_FR_RAG_006_runtime_ingest_qdrant_index_generation():
    assembly = assemble_runtime(_settings())
    result = _ingest(assembly)
    generation_id = result["content"]["generation_id"]
    outcome = assembly.retrieval.retrieve(
        RetrievalQuery(text=POLICY_TEXT, principal_id="usr_admin")
    )
    assert outcome.status == "ok"
    assert outcome.evidence
    assert outcome.evidence[0].document_id == "doc_policy"
    assert outcome.evidence[0].index_generation == generation_id
    assert outcome.evidence[0].embedding_model_version == "hash-embed-test"
    assert outcome.evidence[0].retrieval_config_version == "runtime-injected"


def test_GATE_P0_003_not_verified_by_ingest_qdrant():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "fake" in evidence.lower() or "memory" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
