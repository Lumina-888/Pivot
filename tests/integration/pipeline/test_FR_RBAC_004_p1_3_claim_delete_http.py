"""S5: HTTP claim interlock, delete-cancel, todo titles, and orphan
self-heal for FR-RBAC-004 (ADR-019 D4, D6).

Claim refuses pending-request documents through the route, delete
closes both pending kinds with audit events, the todo queues carry
document titles, and a repeat upload heals an orphan pending version
(a version left without its request) by creating the missing request.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline, policy_pdf
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.approvals import ApprovalService
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.moves import MoveService
from pivot.auth.ports import Library as _Library
from pivot.auth.ports import Membership, Principal, UserAccount
from pivot.documents.ports import DocumentRecord, VersionRecord
from pivot.http import create_app
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)
FRANK = Principal(user_id="usr_frank", username="frank", role="user", token_version=1)


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
    pipeline.resources.memberships["usr_alice"] = (
        Membership(
            user_id="usr_alice", dept_id="dept_eng", dept_role="dept_admin",
            granted_by="usr_admin",
        ),
    )
    pipeline.resources.memberships["usr_frank"] = (
        Membership(
            user_id="usr_frank", dept_id="dept_eng", dept_role="editor",
            granted_by="usr_admin",
        ),
    )
    pipeline.users.save(
        UserAccount(
            id="usr_frank",
            username="frank",
            password_hash=pipeline.hasher.hash("frank-password"),
            role="user",
            status="active",
            token_version=1,
        )
    )
    departments = DepartmentAdminService(
        store=pipeline.resources,
        documents=pipeline.doc_store,
        users=pipeline.users,
        access=AccessControl(pipeline.resources),
        audits=audits,
        clock=pipeline.clock,
    )
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
    )
    departments.bind_pending_request_checks(
        pending_approval_for=approvals.pending_request_for,
        pending_move_for=moves.pending_request_for,
    )
    client = TestClient(
        create_app(
            auth=pipeline.auth,
            audits=audits,
            departments=departments,
            approvals=approvals,
            moves=moves,
            documents=pipeline.documents,
        ),
        base_url="https://testserver",
    )
    return client, pipeline, departments, approvals, moves, audits


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


def _upload(client, token, *, target=None, request_id, filename="handbook.pdf"):
    data = {"title": "handbook"}
    if target is not None:
        data["target_library_id"] = target
    return client.post(
        "/api/v1/documents",
        data=data,
        files={"file": (filename, policy_pdf(), "application/pdf")},
        headers=_headers(token, request_id),
    )


def _audit_actions(audits, action: str) -> list[dict]:
    return [
        event.to_info() for event in audits.events() if event.action == action
    ]


def test_FR_RBAC_004_p1_3_http_claim_refuses_pending_approval() -> None:
    client, pipeline, _, _, _, _ = _assembly()
    frank = _login(client, "frank", "frank-password")
    admin = _login(client, "admin", "admin-password")
    alice = _login(client, "alice", "correct-password")
    uploaded = _upload(client, frank, target="dept_eng", request_id="req_up")
    assert uploaded.status_code == 201
    doc_id = uploaded.json()["document_id"]
    # The owning department's admin and the super admin are both
    # refused: the pending document goes through its queue only.
    for token in (alice, admin):
        refused = client.post(
            f"/api/v1/admin/documents/{doc_id}/claim",
            json={"library_id": "dept_eng"},
            headers=_headers(token, "req_claim"),
        )
        assert refused.status_code == 403
        assert refused.json()["code"] == "RESOURCE_FORBIDDEN"
    assert pipeline.doc_store.get(doc_id).library_id == "unassigned"


def test_FR_RBAC_004_p1_3_http_delete_cancels_pending_requests() -> None:
    client, pipeline, _, approvals, moves, audits = _assembly()
    frank = _login(client, "frank", "frank-password")
    admin = _login(client, "admin", "admin-password")
    uploaded = _upload(client, frank, target="dept_eng", request_id="req_up")
    pending_doc = uploaded.json()["document_id"]
    pipeline.doc_store.save(
        DocumentRecord(
            id="doc_moving", title="moving", space="shared",
            created_by="usr_frank", library_id="dept_eng",
        )
    )
    proposed = client.post(
        "/api/v1/moves",
        json={"document_id": "doc_moving", "target_library_id": "pub"},
        headers=_headers(admin, "req_mv"),
    )
    assert proposed.status_code == 200
    deleted = client.post(
        f"/api/v1/documents/{pending_doc}/delete",
        headers=_headers(admin, "req_del1"),
    )
    assert deleted.status_code == 202
    assert approvals.pending_request_for(pending_doc) is None
    assert len(_audit_actions(audits, "doc.approval.cancelled")) == 1
    # O4 anchor: the pending version's state is NOT force-transitioned.
    version = pipeline.versions.get(uploaded.json()["version_id"])
    assert version.state == "pending_approval"
    assert version.current is False
    deleted = client.post(
        "/api/v1/documents/doc_moving/delete",
        headers=_headers(admin, "req_del2"),
    )
    assert deleted.status_code == 202
    assert moves.pending_request_for("doc_moving") is None
    assert len(_audit_actions(audits, "doc.move.cancelled")) == 1


def test_FR_RBAC_004_p1_3_http_delete_published_version_state() -> None:
    client, pipeline, _, _, _, _ = _assembly()
    admin = _login(client, "admin", "admin-password")
    pipeline.doc_store.save(
        DocumentRecord(
            id="doc_pub", title="pub", space="shared",
            created_by="usr_frank", library_id="dept_eng",
        )
    )
    pipeline.versions.save(
        VersionRecord(
            id="ver_pub", document_id="doc_pub", content_sha256="sha",
            storage_key="quarantine/doc_pub/ver_pub",
            state="ready", current=True,
        )
    )
    deleted = client.post(
        "/api/v1/documents/doc_pub/delete",
        headers=_headers(admin, "req_del"),
    )
    assert deleted.status_code == 202
    version = pipeline.versions.get("ver_pub")
    assert version.state == "delete_pending"
    assert version.current is False


def test_FR_RBAC_004_p1_3_http_todo_queues_carry_document_title() -> None:
    client, pipeline, _, _, _, _ = _assembly()
    frank = _login(client, "frank", "frank-password")
    admin = _login(client, "admin", "admin-password")
    alice = _login(client, "alice", "correct-password")
    uploaded = _upload(client, frank, target="dept_eng", request_id="req_up")
    assert uploaded.status_code == 201
    queue = client.get(
        "/api/v1/approvals/pending", headers=_headers(alice, "req_q1")
    )
    assert queue.status_code == 200
    items = queue.json()["items"]
    assert len(items) == 1
    assert items[0]["document_id"] == uploaded.json()["document_id"]
    assert items[0]["document_title"] == "handbook"
    assert items[0]["proposer"] == "usr_frank"
    assert items[0]["target_library_id"] == "dept_eng"
    assert items[0]["status"] == "pending"
    pipeline.doc_store.save(
        DocumentRecord(
            id="doc_moving", title="moving", space="shared",
            created_by="usr_frank", library_id="dept_eng",
        )
    )
    proposed = client.post(
        "/api/v1/moves",
        json={"document_id": "doc_moving", "target_library_id": "pub"},
        headers=_headers(admin, "req_mv"),
    )
    assert proposed.status_code == 200
    queue = client.get(
        "/api/v1/moves/pending", headers=_headers(admin, "req_q2")
    )
    assert queue.status_code == 200
    items = queue.json()["items"]
    assert len(items) == 1
    assert items[0]["document_title"] == "moving"
    assert items[0]["source_library_id"] == "dept_eng"


def test_FR_RBAC_004_p1_3_http_repeat_upload_heals_orphan_pending_version() -> None:
    client, pipeline, _, approvals, _, audits = _assembly()
    frank = _login(client, "frank", "frank-password")
    # Seed the orphan directly: a pending version with no request,
    # as if the first upload's request creation failed midway.
    orphan = pipeline.documents.upload(
        filename="handbook.pdf",
        declared_mime="application/pdf",
        content=policy_pdf(),
        title="handbook",
        actor_id="usr_frank",
        request_id="req_seed",
        target_library_id="dept_eng",
    )
    assert orphan.state == "pending_approval"
    assert approvals.pending_request_for(orphan.document_id) is None
    # The repeat upload returns the same version (content duplicate)
    # and heals the orphan by creating the missing request.
    response = _upload(client, frank, target="dept_eng", request_id="req_heal")
    assert response.status_code == 201
    body = response.json()
    assert body["version_id"] == orphan.id
    assert body["approval_request_id"]
    healed = approvals.pending_request_for(orphan.document_id)
    assert healed is not None
    assert healed.id == body["approval_request_id"]
    # A third upload does not duplicate the request.
    again = _upload(client, frank, target="dept_eng", request_id="req_again")
    assert again.json()["approval_request_id"] == healed.id
    assert len(_audit_actions(audits, "doc.approval.requested")) == 1
