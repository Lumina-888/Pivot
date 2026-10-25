"""S2: retriever folder selection and node filtering (ADR-018 D3, D2).

The retriever queries only the caller's visible folder collections
plus their visible library collections; the default folder is the
library collection itself, never a separate index. Department admins
see every folder in their departments, so their selection covers all
folder indexes. Exceptions widen the folder selection too, because an
exception document's folder is not derivable from its id, and the
per-node authorize hook (exception-aware) still filters every node
before it reaches the corpus. A folder resolver failure drops folder
indexes only; a library resolver failure still denies everything.
"""

from __future__ import annotations

import pytest
from pivot.retrieval.fakes import HashingQueryEmbedder

CHUNK_DEFAULT = "一个月内累计迟到三次，视为旷工一天。"
CHUNK_FOLDER = "员工出差需要提前三天提交出差申请单。"
CHUNK_OTHER_FOLDER = "出差申请单需要部门负责人签字。"
QUESTION = "出差申请单"

DOC_FOLDER = {
    "doc-default": None,
    "doc-folder": "fld_a",
    "doc-other": "fld_b",
}
DOC_LIBRARY = {
    "doc-default": "dept_eng",
    "doc-folder": "dept_eng",
    "doc-other": "dept_eng",
}


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
    from pivot.retrieval.llama_qdrant_index import LlamaLibraryIndexSet

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


def _retriever(indexes, folder_indexes, visible_libs, visible_folders,
               exceptions, authorize=None):
    from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
    from pivot.retrieval.policy import RetrievalPolicy
    from pivot.retrieval.tokenize import SimpleLexTokenizer

    if authorize is None:
        def authorize(principal_id, document_id, version_id):
            library = DOC_LIBRARY.get(document_id)
            folder = DOC_FOLDER.get(document_id)
            if library in visible_libs and (
                folder is None or folder in visible_folders
            ):
                return True
            return document_id in exceptions

    return LlamaIndexRetriever(
        indexes=indexes,
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=60, evidence_limit=4),
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=1.2,
        bm25_b=0.75,
        dense_score_cutoff=-1.0,
        authorize=authorize,
        visible_libraries_for=lambda principal_id: visible_libs,
        exception_documents_for=lambda principal_id: exceptions,
        folder_indexes=folder_indexes,
        visible_folders_for=lambda principal_id: visible_folders,
    )


def _payloads():
    return [
        _payload("chunk-d0", "ver-d0", "doc-default", CHUNK_DEFAULT, "dept_eng"),
        _payload(
            "chunk-f1", "ver-f1", "doc-folder", CHUNK_FOLDER, "dept_eng",
            folder_id="fld_a",
        ),
        _payload(
            "chunk-f2", "ver-f2", "doc-other", CHUNK_OTHER_FOLDER, "dept_eng",
            folder_id="fld_b",
        ),
    ]


def _args():
    return {
        "scope_type": "global",
        "scope_document_id": None,
        "principal_id": "usr_dave",
    }


def test_FR_RBAC_004_folder_retriever_selects_only_visible_folders() -> None:
    client = _client()
    holders = _open_set(client, _payloads())
    retriever = _retriever(
        holders.indexes, holders.folder_indexes,
        ("dept_eng",), ("fld_a",), (),
    )
    selected = retriever._selected_indexes("usr_dave")
    assert "dept_eng" in selected
    assert "fld_a" in selected
    assert "fld_b" not in selected
    found = [h.chunk_id for h in retriever.retrieve(QUESTION, **_args()).evidence]
    assert "chunk-d0" in found
    assert "chunk-f1" in found
    assert "chunk-f2" not in found


def test_FR_RBAC_004_folder_retriever_dept_admin_selects_all_folders() -> None:
    client = _client()
    holders = _open_set(client, _payloads())
    # A department admin's visible folder set covers every folder in
    # their departments, so selection covers all folder indexes.
    retriever = _retriever(
        holders.indexes, holders.folder_indexes,
        ("dept_eng",), ("fld_a", "fld_b"), (),
    )
    selected = retriever._selected_indexes("usr_alice")
    assert "fld_a" in selected
    assert "fld_b" in selected
    found = [h.chunk_id for h in retriever.retrieve(QUESTION, **_args()).evidence]
    assert "chunk-f1" in found
    assert "chunk-f2" in found


def test_FR_RBAC_004_folder_retriever_exception_widens_folder_selection() -> None:
    client = _client()
    holders = _open_set(client, _payloads())
    # The caller sees no folder, but holds an exception on a document
    # inside fld_b: selection widens to every folder index, and the
    # hook lets exactly the granted document through.
    retriever = _retriever(
        holders.indexes, holders.folder_indexes,
        ("dept_eng",), (), ("doc-other",),
    )
    selected = retriever._selected_indexes("usr_dave")
    assert "fld_a" in selected
    assert "fld_b" in selected
    found = [h.chunk_id for h in retriever.retrieve(QUESTION, **_args()).evidence]
    assert "chunk-f2" in found
    assert "chunk-f1" not in found


def test_FR_RBAC_004_folder_retriever_folder_resolver_failure_drops_folders() -> None:
    from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
    from pivot.retrieval.policy import RetrievalPolicy
    from pivot.retrieval.tokenize import SimpleLexTokenizer

    client = _client()
    holders = _open_set(client, _payloads())

    def _boom(principal_id):
        raise RuntimeError("catalog down")

    retriever = LlamaIndexRetriever(
        indexes=holders.indexes,
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=60, evidence_limit=4),
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=1.2,
        bm25_b=0.75,
        dense_score_cutoff=-1.0,
        authorize=lambda p, d, v: True,
        visible_libraries_for=lambda principal_id: ("dept_eng",),
        exception_documents_for=lambda principal_id: (),
        folder_indexes=holders.folder_indexes,
        visible_folders_for=_boom,
    )
    selected = retriever._selected_indexes("usr_dave")
    assert "dept_eng" in selected
    assert "fld_a" not in selected
    assert "fld_b" not in selected


def test_FR_RBAC_004_folder_retriever_library_resolver_failure_denies_all() -> None:
    from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
    from pivot.retrieval.policy import RetrievalPolicy
    from pivot.retrieval.tokenize import SimpleLexTokenizer

    client = _client()
    holders = _open_set(client, _payloads())

    def _boom(principal_id):
        raise RuntimeError("catalog down")

    retriever = LlamaIndexRetriever(
        indexes=holders.indexes,
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=60, evidence_limit=4),
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=1.2,
        bm25_b=0.75,
        dense_score_cutoff=-1.0,
        authorize=lambda p, d, v: True,
        visible_libraries_for=_boom,
        exception_documents_for=lambda principal_id: (),
        folder_indexes=holders.folder_indexes,
        visible_folders_for=lambda principal_id: ("fld_a",),
    )
    assert retriever._selected_indexes("usr_dave") == {}


def test_FR_RBAC_004_folder_retriever_without_folder_indexes_is_unchanged() -> None:
    client = _client()
    holders = _open_set(client, _payloads())
    # Pre-folder callers pass no folder_indexes: selection is exactly
    # the library selection, and the folder collections are untouched.
    retriever = _retriever(
        holders.indexes, None, ("dept_eng",), ("fld_a",), ()
    )
    selected = retriever._selected_indexes("usr_dave")
    assert set(selected) == {"dept_eng"}
