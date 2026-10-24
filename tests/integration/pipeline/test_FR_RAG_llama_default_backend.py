"""FR-RAG-008: the LlamaIndex backend is the default (L4 switch).

Covers the default flip itself, the native path as the rollback option,
the non-Qdrant assembly rule, and the worker-side collection sync that
makes the default work with celery ingest.
"""

from __future__ import annotations

import pytest
from pivot.http import RuntimeSettings, assemble_runtime
from pivot_worker.assembly import assemble_ingest_runtime
from pivot_worker.runtime import DocumentIngestRunner
from test_FR_DOC_006_worker_qdrant_publish import (
    POLICY_TEXT,
    _FakeMinioClient,
    _seed_user,
    _StoringQdrantClient,
    _worker_settings,
    policy_pdf,
)
from test_FR_RAG_llama_qdrant_backend import (
    CHUNK_TEXT,
    QUESTION,
    _Client,
    _db_url,
    _memory_qdrant_client,
    _retrieve,
    _seed_admin_user,
    _seed_facts,
    _seed_payloads,
)


def _settings(db_url: str, client: _Client, raw_client, **overrides: object) -> RuntimeSettings:
    # No retrieval_backend key on purpose: these tests exercise the
    # dataclass default, which is the production default since L4.
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
        "bm25_k1": 1.2,
        "bm25_b": 0.75,
    }
    values.update(overrides)
    return RuntimeSettings(**values)


def test_FR_RAG_008_default_backend_is_llama(tmp_path):
    pytest.importorskip("llama_index.core")
    from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever

    client = _Client()
    _seed_payloads(client)
    assembly = assemble_runtime(_settings(_db_url(tmp_path), client, _memory_qdrant_client()))
    _seed_admin_user(assembly)
    _seed_facts(assembly)
    assert isinstance(assembly.qa_retriever, LlamaIndexRetriever)
    result = _retrieve(assembly)
    assert result.status == "found"
    assert [hit.chunk_id for hit in result.evidence] == ["chunk-l3"]


def test_FR_RAG_008_native_backend_remains_available_for_rollback(tmp_path):
    pytest.importorskip("llama_index.core")
    client = _Client()
    _seed_payloads(client)
    assembly = assemble_runtime(
        _settings(
            _db_url(tmp_path),
            client,
            _memory_qdrant_client(),
            retrieval_backend="native",
        )
    )
    _seed_admin_user(assembly)
    _seed_facts(assembly)
    result = _retrieve(assembly)
    assert result.status == "ok"
    assert [hit.chunk_id for hit in result.evidence] == ["chunk-l3"]


def test_FR_RAG_008_default_backend_without_qdrant_keeps_bridge(tmp_path):
    pytest.importorskip("llama_index.core")
    from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever

    assembly = assemble_runtime(
        _settings(
            _db_url(tmp_path),
            _Client(),
            _memory_qdrant_client(),
            vector_store="memory",
        )
    )
    assert not isinstance(assembly.qa_retriever, LlamaIndexRetriever)


def test_FR_RAG_008_worker_ingest_syncs_llama_collection(tmp_path):
    pytest.importorskip("llama_index.core")
    url = _db_url(tmp_path)
    _seed_user(url)
    shared_minio = _FakeMinioClient()
    shared_qdrant = _StoringQdrantClient()
    raw = _memory_qdrant_client()
    worker = assemble_ingest_runtime(
        _worker_settings(
            url,
            shared_minio,
            shared_qdrant,
            create_schema=False,
            retrieval_backend="llama",
            llama_qdrant_client=raw,
        )
    )
    assert not isinstance(worker.runner, DocumentIngestRunner)
    version = worker.documents.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=policy_pdf(),
        title="Attendance Policy",
        actor_id="usr_admin",
        request_id="req_l4_worker_up",
        space="hr",
    )
    result = worker.runner(version.id, "req_l4_worker_ingest", "usr_admin")
    assert result["status"] == "ok"
    synced = raw.count(collection_name="pivot-chunks__llama")
    assert synced.count >= 1

    # A freshly started API process (the celery deployment shape) serves
    # the worker-synced collection under the default backend.
    assembly = assemble_runtime(
        _settings(url, shared_qdrant, raw, create_schema=False)
    )
    found = assembly.qa_retriever.retrieve(
        POLICY_TEXT,
        scope_type="global",
        scope_document_id=None,
        principal_id="usr_admin",
    )
    assert found.status == "found"
    assert found.evidence
    assert found.evidence[0].document_id == version.document_id


def test_FR_RAG_008_chunk_text_fixture_is_stable():
    # Guards the shared fixtures this module borrows from the L3 tests.
    assert CHUNK_TEXT and QUESTION
