"""Runtime retrieval backend switch: QA via native path or LlamaIndex adapter.

Both assemblies share one sqlite fact store and one fake Qdrant client, so the
document/version facts and the published payloads are identical; only the QA
retrieval backend differs. Document search keeps using RetrievalService.
Not GATE-P0 verified.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pivot.documents.ports import DocumentRecord, VersionRecord
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.retrieval.fakes import HashingQueryEmbedder
from pivot.storage.adapters.qdrant import QdrantVectorStore

CHUNK_TEXT = "一个月内累计迟到三次，视为旷工一天。"
QUESTION = "迟到三次怎么处理？"


def _memory_qdrant_client():
    """A real in-memory Qdrant client for the LlamaIndex collection."""
    qdrant_client = pytest.importorskip("qdrant_client")
    return qdrant_client.QdrantClient(location=":memory:")


class _Client:
    """In-memory Qdrant client double with scroll, shaped like the SDK wrapper."""

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

    def scroll(self, collection_name, *, limit, offset=None):
        items = sorted(self.points.get(collection_name, {}).items())
        start = int(offset) if offset is not None else 0
        page = items[start:start + limit]
        next_offset = start + limit
        return (
            [SimpleNamespace(id=pid, payload=payload) for pid, (_, payload) in page],
            str(next_offset) if next_offset < len(items) else None,
        )


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


def _seed_payloads(client: _Client) -> None:
    store = QdrantVectorStore(
        client,
        collection="pivot-chunks",
        ensure_collection=True,
        vector_size=4,
        distance="Cosine",
    )
    vector = HashingQueryEmbedder(4).embed([CHUNK_TEXT])[0]
    store.upsert(
        [
            {
                "vector": vector,
                "chunk_id": "chunk-l1",
                "version_id": "ver-l1",
                "document_id": "doc-l1",
                "text": CHUNK_TEXT,
                "title": "考勤制度",
                "space": "shared",
                "tags": [],
                "ready": True,
                "current": True,
                "allowed": True,
                "expired": False,
                "deleted": False,
                "index_generation": "gen-l1",
                "embedding_model_version": "hash-embed-test",
                "retrieval_config_version": "cfg-l1",
                "locator": "第一条",
            }
        ]
    )


def _settings(db_url: str, client: _Client, **overrides: object) -> RuntimeSettings:
    values: dict[str, object] = {
        "storage": "postgres",
        "database_url": db_url,
        "create_schema": True,
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
        "vector_store_client": client,
        "llama_qdrant_client": _memory_qdrant_client(),
        "retrieval_backend": "native",
        "bm25_k1": 1.2,
        "bm25_b": 0.75,
    }
    values.update(overrides)
    return RuntimeSettings(**values)


def _seed_facts(assembly) -> None:
    assembly.document_rows.save(
        DocumentRecord(
            id="doc-l1", title="考勤制度", space="shared", created_by="admin"
        )
    )
    assembly.version_rows.save(
        VersionRecord(
            id="ver-l1",
            document_id="doc-l1",
            content_sha256="sha-l1",
            storage_key="key-l1",
            state="ready",
            current=True,
            external_llm_allowed=True,
        )
    )


def _retrieve(assembly, **kwargs):
    args = {"scope_type": "global", "scope_document_id": None, "principal_id": "usr_admin"}
    args.update(kwargs)
    return assembly.qa_retriever.retrieve(QUESTION, **args)


def _db_url(tmp_path) -> str:
    return f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"


def test_FR_RAG_006_native_backend_is_default_and_answers(tmp_path):
    client = _Client()
    _seed_payloads(client)
    assembly = assemble_runtime(_settings(_db_url(tmp_path), client))
    _seed_facts(assembly)
    result = _retrieve(assembly)
    assert result.status == "ok"
    assert [hit.chunk_id for hit in result.evidence] == ["chunk-l1"]
    hit = result.evidence[0]
    assert (hit.document_id, hit.version_id, hit.text) == ("doc-l1", "ver-l1", CHUNK_TEXT)
    assert hit.external_llm_allowed is True


def test_FR_RAG_006_llama_backend_returns_same_evidence(tmp_path):
    pytest.importorskip("llama_index.core")
    client = _Client()
    _seed_payloads(client)
    url = _db_url(tmp_path)
    native = assemble_runtime(_settings(url, client))
    _seed_facts(native)
    native_result = _retrieve(native)
    llama = assemble_runtime(_settings(url, client, retrieval_backend="llama"))
    result = _retrieve(llama)
    assert result.status == "found"
    assert [hit.chunk_id for hit in result.evidence] == [
        hit.chunk_id for hit in native_result.evidence
    ]
    hit = result.evidence[0]
    assert (hit.document_id, hit.version_id, hit.text) == ("doc-l1", "ver-l1", CHUNK_TEXT)
    assert hit.locator == "第一条"
    assert hit.external_llm_allowed is True
    assert hit.index_generation == "gen-l1"
    assert hit.embedding_model_version == "hash-embed-test"
    assert hit.retrieval_config_version == "cfg-l1"


def test_FR_RAG_006_llama_backend_filters_scope_like_native(tmp_path):
    pytest.importorskip("llama_index.core")
    client = _Client()
    _seed_payloads(client)
    url = _db_url(tmp_path)
    native = assemble_runtime(_settings(url, client))
    _seed_facts(native)
    llama = assemble_runtime(_settings(url, client, retrieval_backend="llama"))
    scoped = {"scope_type": "document", "scope_document_id": "doc-other"}
    assert _retrieve(native, **scoped).evidence == ()
    assert _retrieve(llama, **scoped).evidence == ()


def test_FR_RAG_006_llama_backend_rechecks_live_facts(tmp_path):
    pytest.importorskip("llama_index.core")
    client = _Client()
    _seed_payloads(client)
    llama = assemble_runtime(
        _settings(_db_url(tmp_path), client, retrieval_backend="llama")
    )
    _seed_facts(llama)
    assert _retrieve(llama).status == "found"
    llama.version_rows.save(
        VersionRecord(
            id="ver-l1",
            document_id="doc-l1",
            content_sha256="sha-l1",
            storage_key="key-l1",
            state="ready",
            current=False,
            external_llm_allowed=True,
        )
    )
    result = _retrieve(llama)
    assert result.status == "empty"
    assert result.evidence == ()


def test_FR_RAG_006_llama_backend_requires_qdrant_store(tmp_path):
    with pytest.raises(RuntimeError):
        assemble_runtime(
            _settings(
                _db_url(tmp_path),
                _Client(),
                vector_store="memory",
                retrieval_backend="llama",
                retrieval_backend_explicit=True,
            )
        )


def test_FR_RAG_006_llama_backend_requires_bm25_settings(tmp_path):
    with pytest.raises(RuntimeError):
        assemble_runtime(
            _settings(
                _db_url(tmp_path),
                _Client(),
                retrieval_backend="llama",
                bm25_k1=None,
                bm25_b=None,
            )
        )


def test_FR_RAG_006_unknown_retrieval_backend_rejected(tmp_path):
    with pytest.raises(RuntimeError):
        _settings(_db_url(tmp_path), _Client(), retrieval_backend="bogus")


def test_FR_RAG_006_llama_backend_without_extra_fails_fast(tmp_path):
    try:
        import llama_index.core  # noqa: F401
    except ImportError:
        pass
    else:
        pytest.skip("llama-index extra is installed in this environment")
    client = _Client()
    _seed_payloads(client)
    with pytest.raises(RuntimeError):
        assemble_runtime(
            _settings(_db_url(tmp_path), client, retrieval_backend="llama")
        )
