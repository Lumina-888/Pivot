"""S3: project collections in retrieval for FR-RBAC-004 (ADR-018 D4).

Project libraries are ordinary library collections
({native}__llama__{project_id}), created lazily on first reconcile
like department collections, so no retriever change is needed: the
selection follows visible_libraries, which S3 extends to joined
projects and owning-department projects. These tests pin that
selection and the end-to-end retrieve path: members and
owning-department admins find project chunks, outsiders find none,
and an exception grant still opens its document.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pivot.auth.errors import AuthError
from pivot.auth.ports import (
    DocumentAuthz,
    Library,
    Membership,
    Principal,
)
from pivot.http.memory import InMemoryResources
from pivot.security.rbac import AccessControl

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)
CHUNK_PROJECT = "项目周报需要每周五下午提交给项目负责人。"
CHUNK_DEPT = "部门例会每周一上午召开，缺席需要请假。"
QUESTION = "项目周报"


def _payload(chunk_id, version_id, document_id, text, library_id):
    return {
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


def _payloads():
    return [
        _payload("chunk-p0", "ver-p0", "doc-proj", CHUNK_PROJECT, "proj_x"),
        _payload("chunk-d0", "ver-d0", "doc-dept", CHUNK_DEPT, "dept_eng"),
    ]


def _resources():
    resources = InMemoryResources()
    resources.libraries = {
        "pub": Library(id="pub", name="公共库", kind="public"),
        "dept_eng": Library(
            id="dept_eng", name="技术部", kind="department", dept_id="dept_eng"
        ),
        "proj_x": Library(
            id="proj_x", name="跨部门项目", kind="project", dept_id="dept_eng"
        ),
    }
    resources.memberships = {
        "usr_alice": (
            Membership(
                user_id="usr_alice", dept_id="dept_eng",
                dept_role="dept_admin", granted_by="usr_admin",
            ),
        ),
        "usr_erin": (
            Membership(
                user_id="usr_erin", dept_id="proj_x",
                dept_role="project_lead", granted_by="usr_alice",
            ),
        ),
    }
    resources.documents = {
        "doc-proj": DocumentAuthz(
            id="doc-proj", deleted=False, shared_visible=False,
            export_allowed=False, library_id="proj_x",
        ),
        "doc-dept": DocumentAuthz(
            id="doc-dept", deleted=False, shared_visible=False,
            export_allowed=False, library_id="dept_eng",
        ),
    }
    return resources


def _client():
    pytest.importorskip("llama_index.core")
    qdrant_client = pytest.importorskip("qdrant_client")
    return qdrant_client.QdrantClient(location=":memory:")


def _embed():
    from pivot.retrieval.fakes import HashingQueryEmbedder
    from pivot.retrieval.llama_embeddings import PivotEmbedding

    return PivotEmbedding(
        HashingQueryEmbedder(4), model_name="hash-embedding", dimension=4
    )


def _open_set(client, payloads):
    from pivot.retrieval.llama_qdrant_index import LlamaLibraryIndexSet

    return LlamaLibraryIndexSet.open(
        client=client,
        native_collection="pivot-chunks",
        embed_model=_embed(),
        vector_size=4,
        distance="Cosine",
        native_payloads=payloads,
        external_llm_allowed=lambda version_id: True,
    )


def _retriever(holders, access):
    from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
    from pivot.retrieval.policy import RetrievalPolicy
    from pivot.retrieval.tokenize import SimpleLexTokenizer

    def principal_for(user_id):
        return Principal(
            user_id=user_id, username=user_id,
            role="admin" if user_id == "usr_admin" else "user",
            token_version=1,
        )

    def authorize(principal_id, document_id, version_id):
        try:
            access.authorize_document(
                principal_for(principal_id), document_id, "req_auth"
            )
        except AuthError:
            return False
        return True

    return LlamaIndexRetriever(
        indexes=holders.indexes,
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=60, evidence_limit=4),
        tokenizer=SimpleLexTokenizer(),
        bm25_k1=1.2,
        bm25_b=0.75,
        dense_score_cutoff=-1.0,
        authorize=authorize,
        visible_libraries_for=lambda uid: tuple(
            sorted(access.visible_libraries(principal_for(uid)))
        ),
        exception_documents_for=lambda uid: tuple(
            sorted(access.exception_document_ids(principal_for(uid)))
        ),
        folder_indexes=holders.folder_indexes,
        visible_folders_for=lambda uid: tuple(
            sorted(access.visible_folder_ids(principal_for(uid)))
        ),
    )


def test_FR_RBAC_004_p1_4_project_retriever_selects_project_index() -> None:
    client = _client()
    holders = _open_set(client, _payloads())
    access = AccessControl(_resources())
    retriever = _retriever(holders, access)
    selected = retriever._selected_indexes("usr_erin")
    assert "proj_x" in selected
    assert "dept_eng" not in selected
    selected_admin = retriever._selected_indexes("usr_alice")
    assert "proj_x" in selected_admin
    assert "dept_eng" in selected_admin
    selected_out = retriever._selected_indexes("usr_ghost")
    assert "proj_x" not in selected_out
    assert "dept_eng" not in selected_out


def test_FR_RBAC_004_p1_4_project_retriever_retrieve_path() -> None:
    client = _client()
    holders = _open_set(client, _payloads())
    access = AccessControl(_resources())
    retriever = _retriever(holders, access)
    found_member = [
        h.chunk_id
        for h in retriever.retrieve(
            QUESTION, scope_type="global", scope_document_id=None,
            principal_id="usr_erin",
        ).evidence
    ]
    assert "chunk-p0" in found_member
    assert "chunk-d0" not in found_member
    found_admin = [
        h.chunk_id
        for h in retriever.retrieve(
            QUESTION, scope_type="global", scope_document_id=None,
            principal_id="usr_alice",
        ).evidence
    ]
    assert "chunk-p0" in found_admin
    found_out = [
        h.chunk_id
        for h in retriever.retrieve(
            QUESTION, scope_type="global", scope_document_id=None,
            principal_id="usr_ghost",
        ).evidence
    ]
    assert found_out == []
