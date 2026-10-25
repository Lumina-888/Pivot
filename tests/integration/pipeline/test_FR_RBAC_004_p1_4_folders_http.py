"""S2: HTTP folder endpoints and search recheck (ADR-018 D3, D2).

Folder routes follow the department router shape: create/list/get/
rename/delete, member add/set/remove/list, and the move endpoint,
which reuses the claim-sync dispatcher after a move that actually
changed the folder. The search route derives folder scope
server-side from the Principal and rechecks every hit against live
facts when an authorize_hit is wired: a moved document's stale
payload scope cannot over-serve its title and snippet.
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from harness import Pipeline
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.ports import (
    Folder,
    FolderMembership,
    Membership,
    Principal,
)
from pivot.auth.ports import (
    Library as _Library,
)
from pivot.documents.ports import DocumentRecord
from pivot.http import create_app
from pivot.retrieval.models import ChunkRecord
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)


def _assembly(claim_sync=None, retrieval=None, authorize_hit=None):
    pipeline = Pipeline()
    audits = AuditService(AppendOnlyAuditStore(), pipeline.clock)
    pipeline.resources.libraries["pub"] = _Library(
        id="pub", name="公共库", kind="public"
    )
    pipeline.resources.libraries["unassigned"] = _Library(
        id="unassigned", name="未分配", kind="system"
    )
    service = DepartmentAdminService(
        store=pipeline.resources,
        documents=pipeline.doc_store,
        users=pipeline.users,
        access=AccessControl(pipeline.resources),
        audits=audits,
        clock=pipeline.clock,
    )
    service.create_department(ADMIN, "dept_eng", "技术部", "req_seed_eng")
    pipeline.resources.memberships["usr_alice"] = (
        Membership(
            user_id="usr_alice", dept_id="dept_eng", dept_role="dept_admin",
            granted_by="usr_admin",
        ),
    )
    pipeline.resources.memberships["usr_bob"] = (
        Membership(
            user_id="usr_bob", dept_id="dept_eng", dept_role="editor",
            granted_by="usr_admin",
        ),
    )
    pipeline.doc_store.save(
        DocumentRecord(
            id="doc_eng", title="技术文档", space="shared",
            created_by="usr_admin", library_id="dept_eng",
        )
    )
    client = TestClient(
        create_app(
            auth=pipeline.auth, audits=audits, departments=service,
            claim_sync=claim_sync, retrieval=retrieval,
            authorize_hit=authorize_hit,
        ),
        base_url="https://testserver",
    )
    return client, pipeline, service


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"X-Request-ID": "req_login"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _headers(token: str, request_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Request-ID": request_id}


def _create_folder(client, token, folder_id="fld_a"):
    response = client.post(
        "/api/v1/admin/departments/dept_eng/folders",
        json={"folder_id": folder_id, "name": "文件夹 A"},
        headers=_headers(token, "req_folder"),
    )
    assert response.status_code in (200, 201)
    return response.json()


def test_FR_RBAC_004_folder_http_crud_and_members() -> None:
    client, _, _ = _assembly()
    alice_token = _login(client, "alice", "correct-password")
    bob_token = _login(client, "bob", "bob-password")
    created = _create_folder(client, alice_token)
    assert created["folder_id"] == "fld_a"
    assert created["library_id"] == "dept_eng"
    # Re-create is idempotent (200, same row).
    again = client.post(
        "/api/v1/admin/departments/dept_eng/folders",
        json={"folder_id": "fld_a", "name": "文件夹 A"},
        headers=_headers(alice_token, "req_folder2"),
    )
    assert again.status_code == 200
    # An editor cannot create folders: department admin act only.
    denied = client.post(
        "/api/v1/admin/departments/dept_eng/folders",
        json={"folder_id": "fld_b", "name": "文件夹 B"},
        headers=_headers(bob_token, "req_folder3"),
    )
    assert denied.status_code == 404
    # Member add / list / role set / remove.
    added = client.post(
        "/api/v1/admin/departments/dept_eng/folders/fld_a/members",
        json={"user_id": "usr_bob", "folder_role": "reader"},
        headers=_headers(alice_token, "req_add"),
    )
    assert added.status_code == 201
    assert added.json()["folder_role"] == "reader"
    members = client.get(
        "/api/v1/admin/departments/dept_eng/folders/fld_a/members",
        headers=_headers(alice_token, "req_list"),
    )
    assert [item["user_id"] for item in members.json()["items"]] == ["usr_bob"]
    # A folder member cannot list members: managers only.
    forbidden_list = client.get(
        "/api/v1/admin/departments/dept_eng/folders/fld_a/members",
        headers=_headers(bob_token, "req_list2"),
    )
    assert forbidden_list.status_code == 403
    renamed_role = client.patch(
        "/api/v1/admin/departments/dept_eng/folders/fld_a/members/usr_bob",
        json={"folder_role": "full"},
        headers=_headers(alice_token, "req_set"),
    )
    assert renamed_role.status_code == 200
    assert renamed_role.json()["folder_role"] == "full"
    # A full member renames the folder; the admin token is not needed.
    renamed = client.patch(
        "/api/v1/admin/departments/dept_eng/folders/fld_a",
        json={"name": "新名字"},
        headers=_headers(bob_token, "req_rename"),
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "新名字"
    removed = client.delete(
        "/api/v1/admin/departments/dept_eng/folders/fld_a/members/usr_bob",
        headers=_headers(alice_token, "req_remove"),
    )
    assert removed.status_code == 204
    # A non-empty folder cannot be deleted; empty it first via a move
    # is covered below, so here the folder holds no documents and the
    # delete succeeds.
    deleted = client.delete(
        "/api/v1/admin/departments/dept_eng/folders/fld_a",
        headers=_headers(alice_token, "req_delete"),
    )
    assert deleted.status_code == 204
    gone = client.get(
        "/api/v1/admin/departments/dept_eng/folders/fld_a",
        headers=_headers(alice_token, "req_get"),
    )
    assert gone.status_code == 404


def test_FR_RBAC_004_folder_http_move_dispatches_reconcile() -> None:
    dispatched: list[tuple] = []
    client, _, _ = _assembly(
        claim_sync=lambda *args: dispatched.append(args)
    )
    alice_token = _login(client, "alice", "correct-password")
    _create_folder(client, alice_token)
    moved = client.post(
        "/api/v1/admin/departments/dept_eng/documents/doc_eng/folder",
        json={"folder_id": "fld_a"},
        headers=_headers(alice_token, "req_move"),
    )
    assert moved.status_code == 200
    assert moved.json()["folder_id"] == "fld_a"
    assert moved.json()["moved"] is True
    assert dispatched == [("doc_eng", "dept_eng", "req_move", "usr_alice")]
    # A no-op move dispatches nothing.
    noop = client.post(
        "/api/v1/admin/departments/dept_eng/documents/doc_eng/folder",
        json={"folder_id": "fld_a"},
        headers=_headers(alice_token, "req_move2"),
    )
    assert noop.status_code == 200
    assert noop.json()["moved"] is False
    assert len(dispatched) == 1
    # Back to the default folder clears folder_id.
    back = client.post(
        "/api/v1/admin/departments/dept_eng/documents/doc_eng/folder",
        json={"folder_id": None},
        headers=_headers(alice_token, "req_move3"),
    )
    assert back.status_code == 200
    assert back.json()["folder_id"] is None
    assert len(dispatched) == 2


def test_FR_RBAC_004_folder_http_delete_nonempty_is_forbidden() -> None:
    client, _, _ = _assembly()
    alice_token = _login(client, "alice", "correct-password")
    _create_folder(client, alice_token)
    client.post(
        "/api/v1/admin/departments/dept_eng/documents/doc_eng/folder",
        json={"folder_id": "fld_a"},
        headers=_headers(alice_token, "req_move"),
    )
    denied = client.delete(
        "/api/v1/admin/departments/dept_eng/folders/fld_a",
        headers=_headers(alice_token, "req_delete"),
    )
    assert denied.status_code == 403


def _search_service():
    def chunk(chunk_id, document_id, folder_id):
        return ChunkRecord(
            chunk_id=chunk_id,
            version_id="ver-1",
            document_id=document_id,
            text="出差申请单需要提前提交。",
            title="制度",
            space="shared",
            library_id="dept_eng",
            folder_id=folder_id,
        )

    corpus = (
        chunk("c-a", "doc-a", "fld_a"),
        chunk("c-b", "doc-b", "fld_b"),
        chunk("c-c", "doc-c", None),
        chunk("c-x", "doc-exc", "fld_b"),
    )
    return RetrievalService(
        corpus=corpus,
        dense=SimpleNamespace(search=lambda text, k: ()),
        bm25=SimpleNamespace(search=lambda text, k: ()),
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=60, evidence_limit=4),
    )


def _search_assembly(authorize_hit=None):
    client, pipeline, _ = _assembly(
        retrieval=_search_service(), authorize_hit=authorize_hit
    )
    pipeline.resources.folders = {
        "fld_a": Folder(id="fld_a", library_id="dept_eng", name="文件夹 A"),
        "fld_b": Folder(id="fld_b", library_id="dept_eng", name="文件夹 B"),
    }
    pipeline.resources.folder_memberships["usr_bob"] = (
        FolderMembership(
            folder_id="fld_a", user_id="usr_bob", folder_role="reader",
            granted_by="usr_admin",
        ),
    )
    from pivot.auth.ports import DocumentException

    pipeline.resources.exceptions["exc_1"] = DocumentException(
        id="exc_1", document_id="doc-exc",
        target_user_id="usr_bob", granted_by="usr_admin",
    )
    return client, pipeline


def _search(client, token):
    response = client.get(
        "/api/v1/search",
        params={"q": "出差"},
        headers=_headers(token, "req_search"),
    )
    assert response.status_code == 200
    return {item["document_id"] for item in response.json()["items"]}


def test_FR_RBAC_004_folder_http_search_folder_scope() -> None:
    client, _ = _search_assembly()
    bob_token = _login(client, "bob", "bob-password")
    found = _search(client, bob_token)
    # Visible folder + default folder pass; the invisible folder is
    # blocked by the derived folder scope, while the exception
    # document inside it still passes.
    assert found == {"doc-a", "doc-c", "doc-exc"}


def test_FR_RBAC_004_folder_http_search_live_recheck_drops_stale_hit() -> None:
    def authorize_hit(principal_id, document_id, version_id):
        # Live facts deny doc-a (moved away since ingest) and raise
        # for doc-c (facts unavailable): both drop, fail closed.
        if document_id == "doc-a":
            return False
        if document_id == "doc-c":
            raise RuntimeError("facts down")
        return True

    client, _ = _search_assembly(authorize_hit=authorize_hit)
    bob_token = _login(client, "bob", "bob-password")
    found = _search(client, bob_token)
    assert found == {"doc-exc"}


def test_FR_RBAC_004_folder_http_search_without_recheck_keeps_legacy() -> None:
    # With no authorize_hit wired, the search keeps its previous
    # payload-scope behavior (folder scope still applies to chunks
    # that carry a folder fact).
    client, _ = _search_assembly()
    bob_token = _login(client, "bob", "bob-password")
    found = _search(client, bob_token)
    assert "doc-a" in found
    assert "doc-b" not in found
