"""P1-1 S3: Qdrant collections partitioned by library (FR-RBAC-004).

The llama backend keeps one Qdrant collection per library, named
{native}__llama__{library_id}. Collection selection is library
enforcement: a caller only ever queries the collections of libraries
it may see, and the authorize hook stays as defense in depth.
"""

from __future__ import annotations

import pytest
from pivot.retrieval.fakes import HashingQueryEmbedder

CHUNK_PUB = "一个月内累计迟到三次，视为旷工一天。"
CHUNK_DEPT = "员工出差需要提前三天提交出差申请单。"
QUESTION_PUB = "迟到三次怎么处理？"
QUESTION_DEPT = "出差申请单"


def _payload(chunk_id, version_id, document_id, text, library_id="sentinel-missing"):
    payload = {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "version_id": version_id,
        "text": text,
        "title": "制度",
        "space": "shared",
        "tags": [],
        "ready": True,
        "current": True,
        "allowed": True,
        "expired": False,
        "deleted": False,
        "index_generation": "gen-1",
        "embedding_model_version": "hash-embed-test",
        "retrieval_config_version": "cfg-1",
        "locator": "第一条",
    }
    if library_id != "sentinel-missing":
        payload["library_id"] = library_id
    return payload


def _client():
    pytest.importorskip("llama_index.core")
    qdrant_client = pytest.importorskip("qdrant_client")
    return qdrant_client.QdrantClient(location=":memory:")


def _embed():
    from pivot.retrieval.llama_embeddings import PivotEmbedding

    return PivotEmbedding(
        HashingQueryEmbedder(4), model_name="hash-embedding", dimension=4
    )


def _open_set(client, payloads, **overrides):
    from pivot.retrieval.llama_qdrant_index import LlamaLibraryIndexSet

    kwargs = {
        "client": client,
        "native_collection": "pivot-chunks",
        "embed_model": _embed(),
        "vector_size": 4,
        "distance": "Cosine",
        "native_payloads": payloads,
        "external_llm_allowed": lambda version_id: True,
    }
    kwargs.update(overrides)
    return LlamaLibraryIndexSet.open(**kwargs)


def _points(client, collection):
    from llama_index.core.vector_stores.utils import metadata_dict_to_node

    points, _ = client.scroll(
        collection_name=collection, limit=256, with_payload=True, with_vectors=False
    )
    found = []
    for point in points:
        node = metadata_dict_to_node(dict(point.payload or {}))
        found.append(
            (str(point.id), node.metadata.get("version_id"), node.metadata.get("library_id"))
        )
    return sorted(found)


def _retriever(indexes, visible):
    from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
    from pivot.retrieval.policy import RetrievalPolicy
    from pivot.retrieval.tokenize import SimpleLexTokenizer

    return LlamaIndexRetriever(
        indexes=indexes,
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=60, evidence_limit=4),
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=1.2,
        bm25_b=0.75,
        dense_score_cutoff=-1.0,
        authorize=lambda principal_id, document_id, version_id: True,
        visible_libraries_for=lambda principal_id: visible,
    )


def test_FR_RBAC_004_collection_name_includes_library():
    pytest.importorskip("llama_index.core")
    from pivot.retrieval.llama_qdrant_index import llama_collection_name

    assert llama_collection_name("pivot-chunks", "pub") == "pivot-chunks__llama__pub"
    assert (
        llama_collection_name("pivot-chunks", "dept_eng")
        == "pivot-chunks__llama__dept_eng"
    )
    assert (
        llama_collection_name("pivot-chunks", "unassigned")
        == "pivot-chunks__llama__unassigned"
    )


def test_FR_RBAC_004_open_partitions_mixed_payloads_by_library():
    client = _client()
    payloads = [
        _payload("chunk-p1", "ver-p1", "doc-pub", CHUNK_PUB, "pub"),
        _payload("chunk-d1", "ver-d1", "doc-dept", CHUNK_DEPT, "dept_eng"),
    ]
    holders = _open_set(client, payloads)
    assert set(holders.indexes) == {"pub", "dept_eng"}
    assert client.collection_exists(collection_name="pivot-chunks__llama__pub")
    assert client.collection_exists(collection_name="pivot-chunks__llama__dept_eng")
    # The legacy single collection is never created by the per-library open.
    assert not client.collection_exists(collection_name="pivot-chunks__llama")
    pub_points = _points(client, "pivot-chunks__llama__pub")
    dept_points = _points(client, "pivot-chunks__llama__dept_eng")
    assert [version for _, version, _ in pub_points] == ["ver-p1"]
    assert [version for _, version, _ in dept_points] == ["ver-d1"]
    # Every node in a library collection carries that library in metadata.
    assert {library for _, _, library in pub_points} == {"pub"}
    assert {library for _, _, library in dept_points} == {"dept_eng"}


def test_FR_RBAC_004_payload_without_resolvable_library_is_skipped():
    client = _client()
    payloads = [
        _payload("chunk-p1", "ver-p1", "doc-pub", CHUNK_PUB, "pub"),
        _payload("chunk-x1", "ver-x1", "doc-x", "无归属文本。"),
    ]
    holders = _open_set(client, payloads)
    assert set(holders.indexes) == {"pub"}
    assert _points(client, "pivot-chunks__llama__pub") != []
    # Nothing was created for the unresolvable payload, and it is not
    # served from any collection: fail closed, no silent mis-filing.
    assert not client.collection_exists(collection_name="pivot-chunks__llama__unassigned")


def test_FR_RBAC_004_live_facts_win_over_stale_payload_library():
    client = _client()
    payloads = [
        _payload("chunk-m1", "ver-m1", "doc-moved", CHUNK_DEPT, "dept_old"),
    ]
    holders = _open_set(
        client, payloads, library_id_for=lambda version_id: "dept_new"
    )
    assert set(holders.indexes) == {"dept_new"}
    assert not client.collection_exists(collection_name="pivot-chunks__llama__dept_old")
    points = _points(client, "pivot-chunks__llama__dept_new")
    assert [version for _, version, _ in points] == ["ver-m1"]
    assert {library for _, _, library in points} == {"dept_new"}


def test_FR_RBAC_004_unresolvable_facts_fall_back_to_payload_library():
    client = _client()
    payloads = [
        _payload("chunk-f1", "ver-f1", "doc-f", CHUNK_DEPT, "dept_eng"),
    ]
    holders = _open_set(
        client, payloads, library_id_for=lambda version_id: None
    )
    assert set(holders.indexes) == {"dept_eng"}
    points = _points(client, "pivot-chunks__llama__dept_eng")
    assert [version for _, version, _ in points] == ["ver-f1"]


def test_FR_RBAC_004_reconcile_scoped_to_document_library():
    client = _client()
    payloads = [
        _payload("chunk-p1", "ver-p1", "doc-pub", CHUNK_PUB, "pub"),
        _payload("chunk-d1", "ver-d1", "doc-dept", CHUNK_DEPT, "dept_eng"),
    ]
    holders = _open_set(client, payloads)
    dept_before = _points(client, "pivot-chunks__llama__dept_eng")
    # Update the pub document: only the pub collection changes.
    holders.reconcile_document(
        "doc-pub",
        library_id="pub",
        current_payloads=[
            _payload("chunk-p2", "ver-p2", "doc-pub", "迟到一次警告。", "pub"),
        ],
        external_llm_allowed=lambda version_id: True,
    )
    assert [version for _, version, _ in _points(client, "pivot-chunks__llama__pub")] == [
        "ver-p2"
    ]
    assert _points(client, "pivot-chunks__llama__dept_eng") == dept_before
    # Delete the pub document: only the pub collection is emptied.
    holders.reconcile_document(
        "doc-pub",
        library_id="pub",
        current_payloads=[],
        external_llm_allowed=lambda version_id: True,
    )
    assert _points(client, "pivot-chunks__llama__pub") == []
    assert _points(client, "pivot-chunks__llama__dept_eng") == dept_before


def test_FR_RBAC_004_rebuild_one_library_leaves_other_intact():
    from pivot.retrieval.llama_qdrant_index import LlamaQdrantIndex

    client = _client()
    payloads = [
        _payload("chunk-p1", "ver-p1", "doc-pub", CHUNK_PUB, "pub"),
        _payload("chunk-d1", "ver-d1", "doc-dept", CHUNK_DEPT, "dept_eng"),
    ]
    _open_set(client, payloads)
    dept_before = _points(client, "pivot-chunks__llama__dept_eng")
    LlamaQdrantIndex.open(
        client=client,
        native_collection="pivot-chunks",
        library_id="pub",
        embed_model=_embed(),
        vector_size=4,
        distance="Cosine",
        native_payloads=payloads,
        external_llm_allowed=lambda version_id: True,
        rebuild=True,
    )
    assert [version for _, version, _ in _points(client, "pivot-chunks__llama__pub")] == [
        "ver-p1"
    ]
    assert _points(client, "pivot-chunks__llama__dept_eng") == dept_before


def test_FR_RBAC_004_lazy_holder_created_on_first_sync():
    client = _client()
    holders = _open_set(
        client, [_payload("chunk-p1", "ver-p1", "doc-pub", CHUNK_PUB, "pub")]
    )
    assert set(holders.indexes) == {"pub"}
    holders.reconcile_document(
        "doc-dept",
        library_id="dept_new",
        current_payloads=[
            _payload("chunk-d1", "ver-d1", "doc-dept", CHUNK_DEPT, "dept_new"),
        ],
        external_llm_allowed=lambda version_id: True,
    )
    assert client.collection_exists(collection_name="pivot-chunks__llama__dept_new")
    assert [version for _, version, _ in _points(client, "pivot-chunks__llama__dept_new")] == [
        "ver-d1"
    ]
    assert [version for _, version, _ in _points(client, "pivot-chunks__llama__pub")] == [
        "ver-p1"
    ]


def test_FR_RBAC_004_drop_unknown_document_is_noop():
    client = _client()
    payloads = [
        _payload("chunk-p1", "ver-p1", "doc-pub", CHUNK_PUB, "pub"),
        _payload("chunk-d1", "ver-d1", "doc-dept", CHUNK_DEPT, "dept_eng"),
    ]
    holders = _open_set(client, payloads)
    pub_before = _points(client, "pivot-chunks__llama__pub")
    dept_before = _points(client, "pivot-chunks__llama__dept_eng")
    holders.drop_document("doc-gone")
    holders.reconcile_document(
        "doc-gone",
        library_id=None,
        current_payloads=[],
        external_llm_allowed=lambda version_id: True,
    )
    assert _points(client, "pivot-chunks__llama__pub") == pub_before
    assert _points(client, "pivot-chunks__llama__dept_eng") == dept_before


def test_FR_RBAC_004_orphan_scan_covers_library_collections():
    from pivot.retrieval.llama_qdrant_index import scroll_library_version_ids

    client = _client()
    payloads = [
        _payload("chunk-p1", "ver-p1", "doc-pub", CHUNK_PUB, "pub"),
        _payload("chunk-d1", "ver-d1", "doc-dept", CHUNK_DEPT, "dept_eng"),
    ]
    _open_set(client, payloads)
    found = scroll_library_version_ids(client, "pivot-chunks", ["pub", "dept_eng"])
    assert found == {"pub": ("ver-p1",), "dept_eng": ("ver-d1",)}
    # A legacy single collection is never scanned: only named libraries are.
    from qdrant_client.http import models as rest

    client.create_collection(
        collection_name="pivot-chunks__llama",
        vectors_config=rest.VectorParams(size=4, distance=rest.Distance.COSINE),
    )
    found_again = scroll_library_version_ids(client, "pivot-chunks", ["pub", "dept_eng"])
    assert found_again == found


def test_FR_RBAC_004_retriever_queries_visible_libraries_only():
    client = _client()
    payloads = [
        _payload("chunk-p1", "ver-p1", "doc-pub", CHUNK_PUB, "pub"),
        _payload("chunk-d1", "ver-d1", "doc-dept", CHUNK_DEPT, "dept_eng"),
    ]
    holders = _open_set(client, payloads)
    args = {"scope_type": "global", "scope_document_id": None, "principal_id": "user-1"}
    pub_only = _retriever(holders.indexes, ("pub",))
    assert [h.chunk_id for h in pub_only.retrieve(QUESTION_PUB, **args).evidence] == [
        "chunk-p1"
    ]
    # The dept question may still match the visible pub chunk poorly;
    # the property under test is that no dept chunk ever leaks out.
    assert "chunk-d1" not in [
        h.chunk_id for h in pub_only.retrieve(QUESTION_DEPT, **args).evidence
    ]
    assert pub_only.resolve_evidence("chunk-d1", **args) is None
    both = _retriever(holders.indexes, ("pub", "dept_eng"))
    assert "chunk-d1" in [
        h.chunk_id for h in both.retrieve(QUESTION_DEPT, **args).evidence
    ]
    assert both.resolve_evidence("chunk-d1", **args) is not None


def test_FR_RBAC_004_unassigned_has_its_own_collection():
    client = _client()
    holders = _open_set(
        client,
        [_payload("chunk-u1", "ver-u1", "doc-u", "未分配文档文本。", "unassigned")],
    )
    assert set(holders.indexes) == {"unassigned"}
    assert client.collection_exists(collection_name="pivot-chunks__llama__unassigned")
    points = _points(client, "pivot-chunks__llama__unassigned")
    assert [version for _, version, _ in points] == ["ver-u1"]
    assert {library for _, _, library in points} == {"unassigned"}
