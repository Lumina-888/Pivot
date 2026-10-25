"""LlamaIndex Qdrant backend: persistence, ingest sync, startup validation.

The llama backend keeps its index in a dedicated Qdrant collection. These
tests run two assemblies over one in-memory Qdrant client and one sqlite
fact store to prove restart hydration, drive the real upload and delete
HTTP flows to prove ingest-time reconciliation, and pin the startup
health checks. Not GATE-P0 verified.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import pytest
from fastapi.testclient import TestClient
from pivot.auth.ports import UserAccount
from pivot.documents.ports import DocumentRecord, VersionRecord
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.retrieval.fakes import HashingQueryEmbedder, ScriptedJsonHttpClient
from pivot.retrieval.providers import HttpBgeReranker
from pivot.storage.adapters.qdrant import QdrantVectorStore

CHUNK_TEXT = "一个月内累计迟到三次，视为旷工一天。"
QUESTION = "迟到三次怎么处理？"
UPLOAD_TEXT = "business travel requires an application three days in advance."
UPLOAD_QUESTION = "business travel application three days"


def _pdf_bytes(text: str) -> bytes:
    """Minimal PDF fixture the built-in local parser can read."""
    return f"%PDF-1.4\n({text}) Tj\n%%EOF".encode()


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
        hits = [
            SimpleNamespace(id=pid, score=_dot(query, vector), payload=payload)
            for pid, (vector, payload) in self.points.get(collection_name, {}).items()
        ]
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def delete(self, collection_name, points_selector=None) -> None:
        return None

    def scroll(self, collection_name, *, limit, offset=None):
        items = sorted(self.points.get(collection_name, {}).items())
        start = int(offset) if offset is not None else 0
        page = items[start : start + limit]
        next_offset = start + limit
        return (
            [SimpleNamespace(id=pid, payload=payload) for pid, (_, payload) in page],
            str(next_offset) if next_offset < len(items) else None,
        )


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


def _memory_qdrant_client():
    qdrant_client = pytest.importorskip("qdrant_client")
    return qdrant_client.QdrantClient(location=":memory:")


def qdrant_runtime_keys() -> dict[str, object]:
    """Qdrant-backed assembly keys for tests that only need assembly to build.

    The native store uses the in-memory double; the llama index uses a real
    in-memory Qdrant client. No server is needed.
    """
    return {
        "vector_store": "qdrant",
        "qdrant_endpoint": "vectors.test:443",
        "qdrant_collection": "pivot-chunks",
        "qdrant_ensure_collection": True,
        "qdrant_vector_size": 4,
        "qdrant_distance": "Cosine",
        "vector_store_client": _Client(),
        "llama_qdrant_client": _memory_qdrant_client(),
        "bm25_k1": 1.2,
        "bm25_b": 0.75,
    }


def _settings(db_url: str, client: _Client, raw_client, **overrides: object) -> RuntimeSettings:
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
        "llama_qdrant_client": raw_client,
        "retrieval_backend": "llama",
        "bm25_k1": 1.2,
        "bm25_b": 0.75,
    }
    values.update(overrides)
    return RuntimeSettings(**values)


def _payload(chunk_id: str, version_id: str, text: str, **overrides: object) -> dict:
    payload: dict[str, object] = {
        "chunk_id": chunk_id,
        "version_id": version_id,
        "document_id": "doc-l3",
        "text": text,
        "title": "考勤制度",
        "space": "shared",
        "library_id": "unassigned",
        "tags": [],
        "ready": True,
        "current": True,
        "allowed": True,
        "expired": False,
        "deleted": False,
        "index_generation": "gen-l3",
        "embedding_model_version": "hash-embed-test",
        "retrieval_config_version": "cfg-l3",
        "locator": "第一条",
    }
    payload.update(overrides)
    return payload


def _seed_admin_user(assembly) -> None:
    """Seed the synthetic "usr_admin" principal as a real admin account.

    S2 resolves library visibility from live user facts, so retriever
    calls naming "usr_admin" need a real account. The username differs
    from the bootstrap "admin" user, so bootstrap creation still runs
    and bootstrap logins keep working.
    """
    assembly.users.save(
        UserAccount(
            id="usr_admin",
            username="usr_admin",
            password_hash="seeded-test-admin",
            role="admin",
            status="active",
            token_version=1,
        )
    )


def _seed_payloads(client: _Client) -> None:
    store = QdrantVectorStore(
        client,
        collection="pivot-chunks",
        ensure_collection=True,
        vector_size=4,
        distance="Cosine",
    )
    vector = HashingQueryEmbedder(4).embed([CHUNK_TEXT])[0]
    store.upsert([{"vector": vector, **_payload("chunk-l3", "ver-l3", CHUNK_TEXT)}])


def _seed_facts(assembly) -> None:
    assembly.document_rows.save(
        DocumentRecord(id="doc-l3", title="考勤制度", space="shared", created_by="admin")
    )
    assembly.version_rows.save(
        VersionRecord(
            id="ver-l3",
            document_id="doc-l3",
            content_sha256="sha-l3",
            storage_key="key-l3",
            state="ready",
            current=True,
            external_llm_allowed=True,
        )
    )


def _db_url(tmp_path, name: str = "pivot.db") -> str:
    return f"sqlite+pysqlite:///{(tmp_path / name).as_posix()}"


def _retrieve(assembly, question: str = QUESTION):
    return assembly.qa_retriever.retrieve(
        question, scope_type="global", scope_document_id=None, principal_id="usr_admin"
    )


def _login(assembly) -> str:
    client = TestClient(assembly.app, base_url="https://testserver")
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_l3_login"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_FR_RAG_007_point_id_mapping_matches_native_convention():
    pytest.importorskip("llama_index.core")
    from pivot.retrieval.llama_qdrant_index import llama_collection_name, point_id_for

    assert point_id_for("chunk-l3") == str(
        uuid5(NAMESPACE_URL, "pivot:chunk:chunk-l3")
    )
    assert llama_collection_name("pivot-chunks", "unassigned") == (
        "pivot-chunks__llama__unassigned"
    )


def test_FR_RAG_001_llama_runtime_bge_rerank_wires(tmp_path):
    pytest.importorskip("llama_index.core")
    client = _Client()
    raw = _memory_qdrant_client()
    _seed_payloads(client)
    assembly = assemble_runtime(
        _settings(
            _db_url(tmp_path),
            client,
            raw,
            rerank="bge",
            rerank_endpoint="https://rerank.test/v1/rerank",
            rerank_model="injected-rerank-model",
            rerank_api_key='runtime-rerank-key',
            json_http_client=ScriptedJsonHttpClient(
                [{"results": [{"index": 0, "relevance_score": 0.9}]}]
            ),
        )
    )
    assert isinstance(assembly.retrieval._reranker, HttpBgeReranker)
    assert isinstance(assembly.qa_retriever._reranker, HttpBgeReranker)


def test_FR_RAG_007_index_survives_restart_via_hydration(tmp_path):
    pytest.importorskip("llama_index.core")
    client = _Client()
    raw = _memory_qdrant_client()
    _seed_payloads(client)
    url = _db_url(tmp_path)
    first = assemble_runtime(_settings(url, client, raw))
    _seed_admin_user(first)
    _seed_facts(first)
    # Second assembly is built after the facts exist, so its startup build
    # resolves external_llm_allowed from them; the first assembly proves the
    # collection gets created and loaded.
    second = assemble_runtime(_settings(url, client, raw))
    result = _retrieve(second)
    assert result.status == "found"
    assert [hit.chunk_id for hit in result.evidence] == ["chunk-l3"]
    assert result.evidence[0].locator == "第一条"
    resolved = second.qa_retriever.resolve_evidence(
        "chunk-l3", scope_type="global", scope_document_id=None, principal_id="usr_admin"
    )
    assert resolved is not None and resolved.text == CHUNK_TEXT
    # A third assembly hydrates from the stored points (no rebuild): the
    # collection now exists, so open() validates and rehydrates instead.
    third = assemble_runtime(_settings(url, client, raw))
    assert _retrieve(third).status == "found"


def test_FR_RAG_007_ingest_and_delete_sync_the_index(tmp_path):
    pytest.importorskip("llama_index.core")
    client = _Client()
    raw = _memory_qdrant_client()
    url = _db_url(tmp_path)
    assembly = assemble_runtime(_settings(url, client, raw))
    _seed_admin_user(assembly)
    token = _login(assembly)
    http = TestClient(assembly.app, base_url="https://testserver")
    headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "req_l3"}
    upload = http.post(
        "/api/v1/documents",
        data={"title": "出差制度"},
        files={"file": ("travel.pdf", _pdf_bytes(UPLOAD_TEXT), "application/pdf")},
        headers=headers,
    )
    assert upload.status_code == 201
    document_id = upload.json()["document_id"]
    # The upload ran ingest synchronously; reconciliation must have made
    # the new document retrievable without a restart.
    result = _retrieve(assembly, UPLOAD_QUESTION)
    assert result.status == "found"
    chunk_id = result.evidence[0].chunk_id
    assert result.evidence[0].document_id == document_id
    # Delete through the real route; the delete hook reconciles.
    deleted = http.post(f"/api/v1/documents/{document_id}/delete", headers=headers)
    assert deleted.status_code == 202
    assert _retrieve(assembly, UPLOAD_QUESTION).evidence == ()
    # The nodes are physically gone: a fresh assembly over the same stores
    # cannot resolve the chunk either.
    restarted = assemble_runtime(_settings(url, client, raw))
    assert _retrieve(restarted, UPLOAD_QUESTION).evidence == ()
    assert (
        restarted.qa_retriever.resolve_evidence(
            chunk_id, scope_type="global", scope_document_id=None, principal_id="usr_admin"
        )
        is None
    )


def test_FR_RAG_007_reconcile_replaces_versions_and_drops_deleted():
    pytest.importorskip("llama_index.core")
    from pivot.retrieval.llama_embeddings import PivotEmbedding
    from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
    from pivot.retrieval.llama_qdrant_index import LlamaQdrantIndex
    from pivot.retrieval.policy import RetrievalPolicy
    from pivot.retrieval.tokenize import SimpleLexTokenizer

    raw = _memory_qdrant_client()
    embedder = HashingQueryEmbedder(4)
    holder = LlamaQdrantIndex.open(
        client=raw,
        native_collection="pivot-chunks",
        library_id="unassigned",
        embed_model=PivotEmbedding(embedder, model_name="hash-embedding", dimension=4),
        vector_size=4,
        distance="Cosine",
        native_payloads=[_payload("chunk-v1", "ver-v1", CHUNK_TEXT)],
        external_llm_allowed=lambda version_id: True,
    )
    retriever = LlamaIndexRetriever(
        holder.index,
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=60, evidence_limit=4),
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=1.2,
        bm25_b=0.75,
        dense_score_cutoff=-1.0,
        authorize=lambda principal_id, document_id, version_id: True,
    )
    args = {"scope_type": "global", "scope_document_id": None, "principal_id": "usr_admin"}
    assert [h.chunk_id for h in retriever.retrieve(QUESTION, **args).evidence] == ["chunk-v1"]
    # Version switch: v2 payloads replace v1 for the same document.
    new_text = "员工出差需要提前三天提交出差申请单。"
    holder.reconcile_document(
        "doc-l3",
        current_payloads=[_payload("chunk-v2", "ver-v2", new_text)],
        external_llm_allowed=lambda version_id: True,
    )
    result = retriever.retrieve("出差申请单", **args)
    assert [h.chunk_id for h in result.evidence] == ["chunk-v2"]
    assert retriever.resolve_evidence("chunk-v1", **args) is None
    # Deletion: reconcile with no current payloads empties the document.
    holder.reconcile_document(
        "doc-l3", current_payloads=[], external_llm_allowed=lambda version_id: True
    )
    assert retriever.retrieve("出差申请单", **args).evidence == ()


def test_FR_RAG_007_startup_rejects_wrong_vector_size_until_rebuild(tmp_path):
    pytest.importorskip("llama_index.core")
    from qdrant_client.http import models as rest

    client = _Client()
    raw = _memory_qdrant_client()
    _seed_payloads(client)
    raw.create_collection(
        collection_name="pivot-chunks__llama__unassigned",
        vectors_config=rest.VectorParams(size=9, distance=rest.Distance.COSINE),
    )
    url = _db_url(tmp_path)
    with pytest.raises(RuntimeError, match="PIVOT_LLAMA_INDEX_REBUILD"):
        assemble_runtime(_settings(url, client, raw))
    rebuilt = assemble_runtime(_settings(url, client, raw, llama_index_rebuild=True))
    _seed_admin_user(rebuilt)
    _seed_facts(rebuilt)
    again = assemble_runtime(_settings(url, client, raw))
    assert _retrieve(again).status == "found"


def test_FR_RAG_007_startup_rejects_stale_embedding_model(tmp_path):
    pytest.importorskip("llama_index.core")
    client = _Client()
    raw = _memory_qdrant_client()
    _seed_payloads(client)
    url = _db_url(tmp_path)
    first = assemble_runtime(_settings(url, client, raw))
    _seed_facts(first)
    # The native payloads now claim a different embedding model version
    # than the one baked into the LlamaIndex collection.
    bucket = client.points["pivot-chunks"]
    for pid, (vector, payload) in list(bucket.items()):
        changed = dict(payload)
        changed["embedding_model_version"] = "other-model"
        bucket[pid] = (vector, changed)
    with pytest.raises(RuntimeError, match="PIVOT_LLAMA_INDEX_REBUILD"):
        assemble_runtime(_settings(url, client, raw))


def test_FR_RAG_007_llama_backend_accepts_celery_ingest(tmp_path):
    # L4 supersedes the L3 guardrail: celery ingest is wired through the
    # worker-side collection sync, so the combination assembles. The
    # worker sync itself is covered by the L4 default-backend tests.
    pytest.importorskip("llama_index.core")
    client = _Client()
    raw = _memory_qdrant_client()
    assembly = assemble_runtime(
        _settings(
            _db_url(tmp_path),
            client,
            raw,
            ingest_backend="celery",
            parse_queue="parse",
            online_queue="online",
            worker_concurrency=1,
            celery_broker="memory://",
        )
    )
    assert assembly.app is not None


def test_FR_RAG_007_refresh_picks_up_worker_synced_documents():
    pytest.importorskip("llama_index.core")
    from pivot.retrieval.llama_embeddings import PivotEmbedding
    from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
    from pivot.retrieval.llama_qdrant_index import CollectionRefresher, LlamaQdrantIndex
    from pivot.retrieval.policy import RetrievalPolicy
    from pivot.retrieval.tokenize import SimpleLexTokenizer

    raw = _memory_qdrant_client()
    embedder = HashingQueryEmbedder(4)
    embed = PivotEmbedding(embedder, model_name="hash-embedding", dimension=4)
    api_holder = LlamaQdrantIndex.open(
        client=raw,
        native_collection="pivot-chunks",
        library_id="unassigned",
        embed_model=embed,
        vector_size=4,
        distance="Cosine",
        native_payloads=[_payload("chunk-v1", "ver-v1", CHUNK_TEXT)],
        external_llm_allowed=lambda version_id: True,
    )
    retriever = LlamaIndexRetriever(
        api_holder.index,
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=60, evidence_limit=4),
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=1.2,
        bm25_b=0.75,
        dense_score_cutoff=-1.0,
        authorize=lambda principal_id, document_id, version_id: True,
        refresher=CollectionRefresher(api_holder, interval_seconds=0),
    )
    args = {"scope_type": "global", "scope_document_id": None, "principal_id": "usr_admin"}
    assert [h.chunk_id for h in retriever.retrieve(QUESTION, **args).evidence] == ["chunk-v1"]
    # A separate worker process syncs a new document straight into the
    # collection; the API process never restarts and never reconciles it.
    new_text = "员工出差需要提前三天提交出差申请单。"
    worker_holder = LlamaQdrantIndex.open_for_sync(
        client=raw,
        native_collection="pivot-chunks",
        library_id="unassigned",
        embed_model=embed,
        vector_size=4,
        distance="Cosine",
        native_payloads=[
            _payload("chunk-v1", "ver-v1", CHUNK_TEXT),
            _payload("chunk-u2", "ver-u2", new_text, document_id="doc-u2"),
        ],
        external_llm_allowed=lambda version_id: True,
    )
    worker_holder.reconcile_document(
        "doc-u2",
        current_payloads=[_payload("chunk-u2", "ver-u2", new_text, document_id="doc-u2")],
        external_llm_allowed=lambda version_id: True,
    )
    result = retriever.retrieve("出差申请单", **args)
    # The requirement is visibility without restart, not an exact
    # evidence list: with the dense leg live (FR-RAG-009) the older
    # chunk may also be returned by hybrid fusion.
    assert "chunk-u2" in [h.chunk_id for h in result.evidence]
    # The worker then deletes the first document at collection level; the
    # API snapshot must drop it on the next refresh as well.
    worker_holder.reconcile_document(
        "doc-l3", current_payloads=[], external_llm_allowed=lambda version_id: True
    )
    remaining = retriever.retrieve(QUESTION, **args).evidence
    assert "chunk-v1" not in [h.chunk_id for h in remaining]
    assert retriever.resolve_evidence("chunk-v1", **args) is None


def test_FR_RAG_007_refresher_respects_interval_and_retries_after_failure():
    from pivot.retrieval.llama_qdrant_index import CollectionRefresher

    class _Holder:
        def __init__(self) -> None:
            self.calls = 0
            self.fail = False

        def refresh_from_collection(self):
            self.calls += 1
            if self.fail:
                raise RuntimeError("qdrant unavailable")
            return (0, 0)

    now = [100.0]
    holder = _Holder()
    refresher = CollectionRefresher(holder, interval_seconds=5.0, clock=lambda: now[0])
    refresher.maybe_refresh()
    assert holder.calls == 1
    refresher.maybe_refresh()
    assert holder.calls == 1
    now[0] += 5.0
    refresher.maybe_refresh()
    assert holder.calls == 2
    holder.fail = True
    now[0] += 5.0
    refresher.maybe_refresh()
    assert holder.calls == 3
    # A failed refresh is swallowed and does not advance the timestamp,
    # so the next retrieve retries instead of serving stale data silently
    # for a whole interval.
    refresher.maybe_refresh()
    assert holder.calls == 4
    holder.fail = False
    refresher.maybe_refresh()
    assert holder.calls == 5


def test_FR_RAG_007_celery_assembly_wires_collection_refresher(tmp_path):
    pytest.importorskip("llama_index.core")
    client = _Client()
    raw = _memory_qdrant_client()
    assembly = assemble_runtime(
        _settings(
            _db_url(tmp_path),
            client,
            raw,
            ingest_backend="celery",
            parse_queue="parse",
            online_queue="online",
            worker_concurrency=1,
            celery_broker="memory://",
        )
    )
    assert assembly.qa_retriever._refresher is not None
    sync_assembly = assemble_runtime(_settings(_db_url(tmp_path, "sync.db"), client, raw))
    assert sync_assembly.qa_retriever._refresher is None
