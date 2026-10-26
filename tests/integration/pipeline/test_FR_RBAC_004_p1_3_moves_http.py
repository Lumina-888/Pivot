"""S4: HTTP move approvals for FR-RBAC-004 (ADR-019 D3, D6).

End-to-end through /api/v1/moves: propose scope and target
fail-closed semantics, single-sided target approval, approve order
(library rewritten before reconcile fires), queue scope, and
withdraw by the proposer.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.approvals import ApprovalService
from pivot.auth.moves import MoveService
from pivot.auth.ports import Library as _Library
from pivot.auth.ports import Membership, UserAccount
from pivot.documents.ports import DocumentRecord
from pivot.http import create_app
from pivot.security.rbac import AccessControl


def _assembly():
    pipeline = Pipeline()
    audits = AuditService(AppendOnlyAuditStore(), pipeline.clock)
    pipeline.resources.libraries["pub"] = _Library(
        id="pub", name="公共库", kind="public"
    )
    pipeline.resources.libraries["unassigned"] = _Library(
        id="unassigned", name="未分配", kind="system"
    )
    pipeline.resources.libraries["dept_eng"] = _Library(
        id="dept_eng", name="技术部", kind="department", dept_id="dept_eng"
    )
    pipeline.resources.libraries["dept_art"] = _Library(
        id="dept_art", name="美术部", kind="department", dept_id="dept_art"
    )
    pipeline.resources.libraries["proj_x"] = _Library(
        id="proj_x", name="跨部门项目", kind="project", dept_id="dept_eng"
    )
    pipeline.resources.memberships["usr_alice"] = (
        Membership(
            user_id="usr_alice", dept_id="dept_eng", dept_role="dept_admin",
            granted_by="usr_admin",
        ),
    )
    pipeline.resources.memberships["usr_carol"] = (
        Membership(
            user_id="usr_carol", dept_id="dept_art", dept_role="dept_admin",
            granted_by="usr_admin",
        ),
    )
    pipeline.resources.memberships["usr_bob"] = (
        Membership(
            user_id="usr_bob", dept_id="dept_eng", dept_role="editor",
            granted_by="usr_admin",
        ),
    )
    pipeline.users.save(
        UserAccount(
            id="usr_carol",
            username="carol",
            password_hash=pipeline.hasher.hash("carol-password"),
            role="user",
            status="active",
            token_version=1,
        )
    )
    pipeline.doc_store.save(
        DocumentRecord(
            id="doc_eng", title="doc_eng", space="shared",
            created_by="usr_frank", library_id="dept_eng",
            folder_id="fld_eng",
        )
    )
    dispatched: list = []

    def _reconcile(document_id, library_id, request_id, actor_id):
        # Snapshot the library at dispatch time: approve() must have
        # already rewritten it to the target, never the old library.
        doc = pipeline.doc_store.get(document_id)
        dispatched.append((document_id, doc.library_id, actor_id))

    approvals = ApprovalService(
        store=pipeline.resources,
        documents=pipeline.doc_store,
        versions=pipeline.versions,
        objects=pipeline.doc_objects,
        access=AccessControl(pipeline.resources),
        audits=audits,
        clock=pipeline.clock,
    )
    moves = MoveService(
        store=pipeline.resources,
        documents=pipeline.doc_store,
        access=AccessControl(pipeline.resources),
        audits=audits,
        clock=pipeline.clock,
        approvals=approvals,
        reconcile=_reconcile,
    )
    client = TestClient(
        create_app(
            auth=pipeline.auth,
            audits=audits,
            approvals=approvals,
            moves=moves,
        ),
        base_url="https://testserver",
    )
    return client, pipeline, moves, audits, dispatched


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


def _audit_actions(audits, action: str) -> list[dict]:
    return [
        event.to_info() for event in audits.events()
        if event.action == action
    ]


def test_FR_RBAC_004_p1_3_move_http_propose_approve() -> None:
    client, pipeline, _, audits, dispatched = _assembly()
    admin = _login(client, "admin", "admin-password")
    carol = _login(client, "carol", "carol-password")
    proposed = client.post(
        "/api/v1/moves",
        json={"document_id": "doc_eng", "target_library_id": "dept_art"},
        headers=_headers(admin, "req_p1"),
    )
    assert proposed.status_code == 200
    body = proposed.json()
    assert body["status"] == "pending"
    assert body["source_library_id"] == "dept_eng"
    assert body["target_library_id"] == "dept_art"
    assert body["reconcile_status"] == "pending"
    # A second proposal for the same document is refused.
    again = client.post(
        "/api/v1/moves",
        json={"document_id": "doc_eng", "target_library_id": "pub"},
        headers=_headers(admin, "req_p2"),
    )
    assert again.status_code == 403
    # The source admin takes no part in the decision (Q3).
    alice = _login(client, "alice", "correct-password")
    denied = client.post(
        f"/api/v1/moves/{body['request_id']}/approve",
        headers=_headers(alice, "req_a0"),
    )
    assert denied.status_code == 404
    decided = client.post(
        f"/api/v1/moves/{body['request_id']}/approve",
        headers=_headers(carol, "req_a1"),
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"
    row = pipeline.doc_store.get("doc_eng")
    assert row.library_id == "dept_art"
    assert row.folder_id is None
    assert dispatched == [("doc_eng", "dept_art", "usr_carol")]
    events = _audit_actions(audits, "authz.library.move")
    assert len(events) == 1
    assert events[0]["metadata"]["approver"] == "usr_carol"


def test_FR_RBAC_004_p1_3_move_http_scope_and_queue() -> None:
    client, _, _, _, _ = _assembly()
    admin = _login(client, "admin", "admin-password")
    alice = _login(client, "alice", "correct-password")
    carol = _login(client, "carol", "carol-password")
    bob = _login(client, "bob", "bob-password")
    # A department admin cannot target another department's library:
    # invisible reads as not_found.
    invisible = client.post(
        "/api/v1/moves",
        json={"document_id": "doc_eng", "target_library_id": "dept_art"},
        headers=_headers(alice, "req_p1"),
    )
    assert invisible.status_code == 404
    # A visible-but-unpowered editor hears forbidden.
    forbidden = client.post(
        "/api/v1/moves",
        json={"document_id": "doc_eng", "target_library_id": "pub"},
        headers=_headers(bob, "req_p2"),
    )
    assert forbidden.status_code == 403
    # The proposer sees their own queue item; the source admin
    # (non-proposer) and outsiders see nothing of it.
    proposed = client.post(
        "/api/v1/moves",
        json={"document_id": "doc_eng", "target_library_id": "pub"},
        headers=_headers(alice, "req_p3"),
    )
    assert proposed.status_code == 200
    request_id = proposed.json()["request_id"]
    assert [item["request_id"] for item in client.get(
        "/api/v1/moves/pending", headers=_headers(alice, "req_q1")
    ).json()["items"]] == [request_id]
    assert [item["request_id"] for item in client.get(
        "/api/v1/moves/pending", headers=_headers(admin, "req_q2")
    ).json()["items"]] == [request_id]
    assert client.get(
        "/api/v1/moves/pending", headers=_headers(carol, "req_q3")
    ).json()["items"] == []
    # Withdraw belongs to the proposer only.
    withdrawn = client.post(
        f"/api/v1/moves/{request_id}/withdraw",
        headers=_headers(alice, "req_w1"),
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
