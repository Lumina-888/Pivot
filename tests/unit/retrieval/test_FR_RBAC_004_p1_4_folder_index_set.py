"""S2: folder collections in the library index set (ADR-018 D3).

Startup partitions each library's payloads by folder: payloads with
no folder fact stay in the library collection (the default folder),
each restricted folder gets its own collection. Reconcile routes by
(library, folder) and sweeps every other holder, so a moved document
leaves its old folder's collection exactly when the reconcile runs.
Dropping a folder collection is a no-op when the folder never held a
document, deletes the collection when it did, and keeps the holder
registered when the delete fails so the folder keeps serving.
"""

from __future__ import annotations

import pytest
from pivot.retrieval.fakes import HashingQueryEmbedder
from pivot.retrieval.llama_qdrant_index import (
    LlamaLibraryIndexSet,
    llama_folder_collection_name,
    point_id_for,
)


def _payload(chunk_id, version_id, document_id, text, library_id, folder_id=None):
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
        "library_id": library_id,
    }
    if folder_id is not None:
        payload["folder_id"] = folder_id
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


def _open_set(client, payloads, folder_id_for=None):
    return LlamaLibraryIndexSet.open(
        client=client,
        native_collection="pivot-chunks",
        embed_model=_embed(),
        vector_size=4,
        distance="Cosine",
        native_payloads=payloads,
        external_llm_allowed=lambda version_id: True,
        folder_id_for=folder_id_for,
    )


def _points(client, collection):
    points, _ = client.scroll(
        collection_name=collection, limit=100,
        with_payload=True, with_vectors=False,
    )
    return points


def _doc_ids(client, collection):
    docs = set()
    for point in _points(client, collection):
        payload = point.payload or {}
        if payload.get("document_id"):
            docs.add(payload["document_id"])
    return docs


def test_FR_RBAC_004_folder_index_set_startup_partitions_by_folder() -> None:
    client = _client()
    payloads = [
        _payload("chunk-d0", "ver-d0", "doc-default", "默认文档。", "dept_eng"),
        _payload(
            "chunk-f1", "ver-f1", "doc-folder", "文件夹文档。", "dept_eng",
            folder_id="fld_a",
        ),
    ]
    holders = _open_set(client, payloads)
    assert set(holders.holders) == {"dept_eng"}
    assert set(holders.folder_holders) == {"fld_a"}
    assert set(holders.folder_indexes) == {"fld_a"}
    assert _doc_ids(client, "pivot-chunks__llama__dept_eng") == {"doc-default"}
    assert _doc_ids(
        client, "pivot-chunks__llama__dept_eng__fld_a"
    ) == {"doc-folder"}
    # Nodes in a folder collection carry the folder in metadata.
    point = _points(client, "pivot-chunks__llama__dept_eng__fld_a")[0]
    assert point.payload["folder_id"] == "fld_a"
    assert point.payload["library_id"] == "dept_eng"


def test_FR_RBAC_004_folder_index_set_startup_uses_live_folder_facts() -> None:
    client = _client()
    # Native payloads carry no folder field; the live resolver places
    # the document in its current folder anyway.
    payloads = [
        _payload("chunk-f1", "ver-f1", "doc-folder", "文件夹文档。", "dept_eng"),
    ]
    holders = _open_set(
        client, payloads, folder_id_for=lambda version_id: "fld_a",
    )
    assert set(holders.folder_holders) == {"fld_a"}
    assert set(holders.holders) == set()
    assert _doc_ids(
        client, "pivot-chunks__llama__dept_eng__fld_a"
    ) == {"doc-folder"}


def test_FR_RBAC_004_folder_index_set_reconcile_moves_across_collections() -> None:
    client = _client()
    payloads = [
        _payload("chunk-d0", "ver-d0", "doc-a", "文档内容。", "dept_eng"),
    ]
    holders = _open_set(client, payloads)
    assert _doc_ids(client, "pivot-chunks__llama__dept_eng") == {"doc-a"}
    # Move into a folder: the folder collection gains the document and
    # the library collection is swept. The folder holder is created
    # lazily by this reconcile, not at startup.
    holders.reconcile_document(
        "doc-a",
        library_id="dept_eng",
        folder_id="fld_a",
        current_payloads=payloads,
        external_llm_allowed=lambda version_id: True,
    )
    assert "fld_a" in holders.folder_holders
    assert _doc_ids(
        client, "pivot-chunks__llama__dept_eng__fld_a"
    ) == {"doc-a"}
    assert _doc_ids(client, "pivot-chunks__llama__dept_eng") == set()
    # Move back to the default folder: the folder collection is swept
    # and the library collection holds the document again.
    holders.reconcile_document(
        "doc-a",
        library_id="dept_eng",
        folder_id=None,
        current_payloads=payloads,
        external_llm_allowed=lambda version_id: True,
    )
    assert _doc_ids(client, "pivot-chunks__llama__dept_eng") == {"doc-a"}
    assert _doc_ids(
        client, "pivot-chunks__llama__dept_eng__fld_a"
    ) == set()


def test_FR_RBAC_004_folder_index_set_reconcile_sweeps_other_folders() -> None:
    client = _client()
    payloads = [
        _payload("chunk-d0", "ver-d0", "doc-a", "文档内容。", "dept_eng"),
    ]
    holders = _open_set(client, payloads)
    holders.reconcile_document(
        "doc-a",
        library_id="dept_eng",
        folder_id="fld_a",
        current_payloads=payloads,
        external_llm_allowed=lambda version_id: True,
    )
    holders.reconcile_document(
        "doc-a",
        library_id="dept_eng",
        folder_id="fld_b",
        current_payloads=payloads,
        external_llm_allowed=lambda version_id: True,
    )
    assert _doc_ids(
        client, "pivot-chunks__llama__dept_eng__fld_b"
    ) == {"doc-a"}
    assert _doc_ids(
        client, "pivot-chunks__llama__dept_eng__fld_a"
    ) == set()
    assert _doc_ids(client, "pivot-chunks__llama__dept_eng") == set()


def test_FR_RBAC_004_folder_index_set_drop_collection() -> None:
    client = _client()
    payloads = [
        _payload("chunk-f1", "ver-f1", "doc-a", "文档内容。", "dept_eng",
                 folder_id="fld_a"),
    ]
    holders = _open_set(client, payloads)
    collection = llama_folder_collection_name(
        "pivot-chunks", "dept_eng", "fld_a"
    )
    assert client.collection_exists(collection_name=collection) is True
    holders.drop_folder_collection("dept_eng", "fld_a")
    assert client.collection_exists(collection_name=collection) is False
    assert "fld_a" not in holders.folder_holders
    # A folder that never held a document has no collection: no-op.
    holders.drop_folder_collection("dept_eng", "fld_never")
    # A later reconcile recreates the collection lazily.
    holders.reconcile_document(
        "doc-a",
        library_id="dept_eng",
        folder_id="fld_a",
        current_payloads=payloads,
        external_llm_allowed=lambda version_id: True,
    )
    assert client.collection_exists(collection_name=collection) is True


def test_FR_RBAC_004_folder_index_set_drop_failure_keeps_holder() -> None:
    client = _client()
    payloads = [
        _payload("chunk-f1", "ver-f1", "doc-a", "文档内容。", "dept_eng",
                 folder_id="fld_a"),
    ]
    holders = _open_set(client, payloads)
    collection = llama_folder_collection_name(
        "pivot-chunks", "dept_eng", "fld_a"
    )
    real_delete = client.delete_collection

    def _boom(*args, **kwargs):
        raise RuntimeError("qdrant down")

    client.delete_collection = _boom
    try:
        with pytest.raises(RuntimeError):
            holders.drop_folder_collection("dept_eng", "fld_a")
    finally:
        client.delete_collection = real_delete
    # The holder stays registered, so the folder keeps serving from its
    # intact collection instead of going dark on a failed delete.
    assert "fld_a" in holders.folder_holders
    assert client.collection_exists(collection_name=collection) is True


def test_FR_RBAC_004_folder_index_set_refresh_covers_folder_holders() -> None:
    client = _client()
    payloads = [
        _payload("chunk-f1", "ver-f1", "doc-a", "文档内容。", "dept_eng",
                 folder_id="fld_a"),
    ]
    holders = _open_set(client, payloads)
    collection = llama_folder_collection_name(
        "pivot-chunks", "dept_eng", "fld_a"
    )
    # Remove one point behind the set's back: refresh must report it,
    # which proves the folder holder is inside the refresh loop.
    client.delete(
        collection_name=collection,
        points_selector=[point_id_for("chunk-f1")],
    )
    added, removed = holders.refresh_from_collection()
    assert (added, removed) == (0, 1)
