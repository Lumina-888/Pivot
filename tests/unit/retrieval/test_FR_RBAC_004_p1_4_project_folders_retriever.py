"""S4: project-folder retrieval selection (ADR-018 D4, D3).

The retriever's folder selection is driven by the real AccessControl
visible set, not a stub: a project lead's selection covers the
project folder index with no folder row, the owning department
admin's selection covers it through the S4 branch, and a project
member without a folder row selects neither the folder index nor
its evidence, while the default folder (the library collection)
still serves them.
"""

from __future__ import annotations

import pytest
from pivot.auth.errors import AuthError
from pivot.auth.ports import (
    DocumentAuthz,
    Folder,
    FolderMembership,
    Library,
    Membership,
    Principal,
)
from pivot.http.memory import InMemoryResources
from pivot.retrieval.fakes import HashingQueryEmbedder
from pivot.security.rbac import AccessControl

CHUNK_DEFAULT = "一个月内累计迟到三次，视为旷工一天。"
CHUNK_FOLDER = "员工出差需要提前三天提交出差申请单。"
CHUNK_OTHER = "出差申请单需要部门负责人签字。"
QUESTION = "出差申请单"

DOC_FOLDER = {
    "doc-default": None,
    "doc-folder": "fld_px",
    "doc-other": "fld_py",
}
DOC_LIBRARY = {
    "doc-default": "proj_x",
    "doc-folder": "proj_x",
    "doc-other": "proj_y",
}

PRINCIPALS = {
    "usr_admin": Principal(user_id="usr_admin", username="admin", role="admin", token_version=1),
    "usr_alice": Principal(user_id="usr_alice", username="alice", role="user", token_version=1),
    "usr_bob": Principal(user_id="usr_bob", username="bob", role="user", token_version=1),
    "usr_dave": Principal(user_id="usr_dave", username="dave", role="user", token_version=1),
    "usr_erin": Principal(user_id="usr_erin", username="erin", role="user", token_version=1),
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
        "proj_y": Library(
            id="proj_y", name="另一项目", kind="project", dept_id="dept_art"
        ),
        "unassigned": Library(id="unassigned", name="未分配", kind="system"),
    }
    resources.memberships = {
        "usr_alice": (
            Membership(
                user_id="usr_alice", dept_id="dept_eng", dept_role="dept_admin",
                granted_by="usr_admin",
            ),
        ),
        "usr_bob": (
            Membership(
                user_id="usr_bob", dept_id="proj_x", dept_role="project_lead",
                granted_by="usr_alice",
            ),
        ),
        "usr_dave": (
            Membership(
                user_id="usr_dave", dept_id="proj_x", dept_role="editor",
                granted_by="usr_bob",
            ),
        ),
        "usr_erin": (
            Membership(
                user_id="usr_erin", dept_id="proj_x", dept_role="reader",
                granted_by="usr_bob",
            ),
        ),
    }
    resources.folders = {
        "fld_px": Folder(id="fld_px", library_id="proj_x", name="项目文件夹"),
        "fld_py": Folder(id="fld_py", library_id="proj_y", name="另一文件夹"),
    }
    resources.folder_memberships = {
        "usr_dave": (
            FolderMembership(
                folder_id="fld_px", user_id="usr_dave", folder_role="reader",
                granted_by="usr_admin",
            ),
        ),
    }
    resources.documents = {
        "doc-default": DocumentAuthz(
            id="doc-default", deleted=False, shared_visible=False,
            export_allowed=False, library_id="proj_x", folder_id=None,
        ),
        "doc-folder": DocumentAuthz(
            id="doc-folder", deleted=False, shared_visible=False,
            export_allowed=False, library_id="proj_x", folder_id="fld_px",
        ),
        "doc-other": DocumentAuthz(
            id="doc-other", deleted=False, shared_visible=False,
            export_allowed=False, library_id="proj_y", folder_id="fld_py",
        ),
    }
    return resources


def _retriever(holders, access):
    from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
    from pivot.retrieval.policy import RetrievalPolicy
    from pivot.retrieval.tokenize import SimpleLexTokenizer

    def authorize(principal_id, document_id, version_id):
        try:
            access.authorize_document(
                PRINCIPALS[principal_id], document_id, "req_authz"
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
        visible_libraries_for=lambda pid: access.visible_libraries(PRINCIPALS[pid]),
        exception_documents_for=lambda pid: access.exception_document_ids(PRINCIPALS[pid]),
        folder_indexes=holders.folder_indexes,
        visible_folders_for=lambda pid: access.visible_folder_ids(PRINCIPALS[pid]),
    )


def _payloads():
    return [
        _payload("chunk-d0", "ver-d0", "doc-default", CHUNK_DEFAULT, "proj_x"),
        _payload(
            "chunk-f1", "ver-f1", "doc-folder", CHUNK_FOLDER, "proj_x",
            folder_id="fld_px",
        ),
        _payload(
            "chunk-f2", "ver-f2", "doc-other", CHUNK_OTHER, "proj_y",
            folder_id="fld_py",
        ),
    ]


def _open(client):
    from pivot.retrieval.llama_qdrant_index import LlamaLibraryIndexSet

    return LlamaLibraryIndexSet.open(
        client=client,
        native_collection="pivot-chunks",
        embed_model=_embed(),
        vector_size=4,
        distance="Cosine",
        native_payloads=_payloads(),
        external_llm_allowed=lambda version_id: True,
    )


def _args(principal_id):
    return {
        "scope_type": "global",
        "scope_document_id": None,
        "principal_id": principal_id,
    }


def test_FR_RBAC_004_project_retriever_lead_selects_project_folder() -> None:
    client = _client()
    holders = _open(client)
    access = AccessControl(_resources())
    retriever = _retriever(holders, access)
    selected = retriever._selected_indexes("usr_bob")
    assert "fld_px" in selected
    assert "fld_py" not in selected
    found = [h.chunk_id for h in retriever.retrieve(QUESTION, **_args("usr_bob")).evidence]
    assert "chunk-f1" in found
    assert "chunk-f2" not in found


def test_FR_RBAC_004_project_retriever_owning_admin_selects_project_folder() -> None:
    client = _client()
    holders = _open(client)
    access = AccessControl(_resources())
    retriever = _retriever(holders, access)
    selected = retriever._selected_indexes("usr_alice")
    assert "fld_px" in selected
    assert "fld_py" not in selected
    found = [h.chunk_id for h in retriever.retrieve(QUESTION, **_args("usr_alice")).evidence]
    assert "chunk-f1" in found
    assert "chunk-f2" not in found


def test_FR_RBAC_004_project_retriever_member_without_folder_row_gets_default_only() -> None:
    client = _client()
    holders = _open(client)
    access = AccessControl(_resources())
    retriever = _retriever(holders, access)
    selected = retriever._selected_indexes("usr_erin")
    assert "fld_px" not in selected
    found = [h.chunk_id for h in retriever.retrieve(QUESTION, **_args("usr_erin")).evidence]
    assert "chunk-f1" not in found
    assert "chunk-f2" not in found
