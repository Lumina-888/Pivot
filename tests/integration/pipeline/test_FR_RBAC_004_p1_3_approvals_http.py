"""S2: HTTP approval endpoints for FR-RBAC-004 (ADR-019 D1, D6).

Approval routes mirror the department router shape: queue listing
scoped by role, approve/reject/withdraw/resubmit decisions, and the
dedicated review read. Queue scope, decision audit metadata, and
the delegated marker are asserted through the audit store; the
fail-closed list/detail/preview refusal for pending documents is
asserted through the documents routes on the same app.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.approvals import ApprovalService
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.ports import ApprovalRequest, Membership, Principal, UserAccount
from pivot.auth.ports import Library as _Library
from pivot.documents.ports import DocumentRecord, VersionRecord
from pivot.http import create_app
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)


def _assembly(dispatched=None):
    pipeline = Pipeline()
    audits = AuditService(AppendOnlyAuditStore(), pipeline.clock)
    pipeline.resources.libraries["pub"] = _Library(
        id="pub", name="公共库", kind="public"
    )
    pipeline.resources.libraries["unassigned"] = _Library(
        id="unassigned", name="未分配", kind="system"
    )
    departments = DepartmentAdminService(
        store=pipeline.resources,
        documents=pipeline.doc_store,
        users=pipeline.users,
        access=AccessControl(pipeline.resources),
        audits=audits,
        clock=pipeline.clock,
    )
    departments.create_department(ADMIN, "dept_eng", "技术部", "req_seed_eng")
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
    approvals = ApprovalService(
        store=pipeline.resources,
        documents=pipeline.doc_store,
        versions=pipeline.versions,
        objects=pipeline.doc_objects,
        access=AccessControl(pipeline.resources),
        audits=audits,
        clock=pipeline.clock,
        ingest=dispatched,
    )
    client = TestClient(
        create_app(
            auth=pipeline.auth,
            audits=audits,
            departments=departments,
            approvals=approvals,
            documents=pipeline.documents,
        ),
        base_url="https://testserver",
    )
    return client, pipeline, approvals, audits


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


def _seed_request(pipeline, request_id, doc_id, version_id, target, proposer):
    pipeline.doc_store.save(
        DocumentRecord(
            id=doc_id, title=doc_id, space="shared",
            created_by=proposer, library_id="unassigned",
        )
    )
    pipeline.versions.save(
        VersionRecord(
            id=version_id, document_id=doc_id, content_sha256="sha",
            storage_key=f"quarantine/{doc_id}/{version_id}",
            state="pending_approval",
        )
    )
    pipeline.doc_objects.put(
        f"quarantine/{doc_id}/{version_id}", b"original-" + doc_id.encode()
    )
    pipeline.resources.approval_requests[request_id] = ApprovalRequest(
        id=request_id, document_id=doc_id, version_id=version_id,
        target_library_id=target, proposer=proposer, status="pending",
    )


def _audit_actions(audits, action: str) -> list[dict]:
    return [
        event.to_info() for event in audits.events()
        if event.action == action
    ]


def test_FR_RBAC_004_p1_3_approval_http_queue_and_approve() -> None:
    dispatched: list = []
    client, pipeline, _, audits = _assembly(
        dispatched=lambda vid, rid, actor: dispatched.append((vid, actor))
    )
    _seed_request(pipeline, "req_eng", "doc_eng", "ver_eng", "dept_eng", "usr_bob")
    alice = _login(client, "alice", "correct-password")
    bob = _login(client, "bob", "bob-password")
    admin = _login(client, "admin", "admin-password")

    # Queue scope: the proposer sees his own submission, the dept
    # admin sees the department target queue, the super admin sees
    # everything.
    bob_queue = client.get(
        "/api/v1/approvals/pending", headers=_headers(bob, "req_q1")
    )
    assert [item["request_id"] for item in bob_queue.json()["items"]] == ["req_eng"]
    alice_queue = client.get(
        "/api/v1/approvals/pending", headers=_headers(alice, "req_q2")
    )
    assert [item["request_id"] for item in alice_queue.json()["items"]] == ["req_eng"]
    admin_queue = client.get(
        "/api/v1/approvals/pending", headers=_headers(admin, "req_q3")
    )
    assert [item["request_id"] for item in admin_queue.json()["items"]] == ["req_eng"]

    # Approve: decision, library rewrite, version transition, audit
    # metadata, and ingest dispatch by the approver.
    approved = client.post(
        "/api/v1/approvals/req_eng/approve", headers=_headers(alice, "req_appr")
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["decided_by"] == "usr_alice"
    assert pipeline.doc_store.get("doc_eng").library_id == "dept_eng"
    assert pipeline.versions.get("ver_eng").state == "uploaded"
    assert dispatched == [("ver_eng", "usr_alice")]
    events = _audit_actions(audits, "authz.approval.approved")
    assert len(events) == 1
    assert events[0]["metadata"]["dept_id"] == "dept_eng"
    assert events[0]["metadata"]["target_library_id"] == "dept_eng"
    assert events[0]["actor"] == "usr_alice"

    # Decided requests leave the queue but stay visible to proposer
    # and approver via the detail route.
    bob_queue = client.get(
        "/api/v1/approvals/pending", headers=_headers(bob, "req_q4")
    )
    assert bob_queue.json()["items"] == []
    got = client.get(
        "/api/v1/approvals/req_eng", headers=_headers(bob, "req_get")
    )
    assert got.status_code == 200
    assert got.json()["status"] == "approved"


def test_FR_RBAC_004_p1_3_approval_http_reject_withdraw_resubmit() -> None:
    dispatched: list = []
    client, pipeline, _, audits = _assembly(
        dispatched=lambda vid, rid, actor: dispatched.append(vid)
    )
    _seed_request(pipeline, "req_eng", "doc_eng", "ver_eng", "dept_eng", "usr_bob")
    alice = _login(client, "alice", "correct-password")
    bob = _login(client, "bob", "bob-password")

    # Reject with an optional reason; the document stays unassigned
    # and no ingest is dispatched.
    rejected = client.post(
        "/api/v1/approvals/req_eng/reject",
        json={"reason": "太敏感"},
        headers=_headers(alice, "req_rej"),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["reason"] == "太敏感"
    assert pipeline.doc_store.get("doc_eng").library_id == "unassigned"
    assert pipeline.versions.get("ver_eng").state == "rejected"
    assert dispatched == []

    # Resubmit reopens the same request; withdraw then returns the
    # version to uploaded and dispatches ingest (O3).
    resubmitted = client.post(
        "/api/v1/approvals/req_eng/resubmit",
        json={},
        headers=_headers(bob, "req_resub"),
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "pending"
    withdrawn = client.post(
        "/api/v1/approvals/req_eng/withdraw",
        headers=_headers(bob, "req_wd"),
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
    assert pipeline.versions.get("ver_eng").state == "uploaded"
    assert dispatched == ["ver_eng"]
    assert len(_audit_actions(audits, "doc.approval.withdrawn")) == 1

    # Only the proposer withdraws: the approver gets forbidden.
    _seed_request(pipeline, "req2", "doc2", "ver2", "dept_eng", "usr_bob")
    denied = client.post(
        "/api/v1/approvals/req2/withdraw",
        headers=_headers(alice, "req_wd2"),
    )
    assert denied.status_code == 403


def test_FR_RBAC_004_p1_3_approval_http_delegated_and_review() -> None:
    client, pipeline, _, audits = _assembly()
    _seed_request(pipeline, "req_eng", "doc_eng", "ver_eng", "dept_eng", "usr_bob")
    alice = _login(client, "alice", "correct-password")
    bob = _login(client, "bob", "bob-password")
    admin = _login(client, "admin", "admin-password")

    # Review read: proposer, approver, and super admin each read the
    # quarantined original, and each read is audited.
    for token in (bob, alice, admin):
        review = client.get(
            "/api/v1/approvals/req_eng/review",
            headers=_headers(token, "req_rev"),
        )
        assert review.status_code == 200
        assert review.content == b"original-doc_eng"
    assert len(_audit_actions(audits, "doc.approval.review")) == 3

    # A stranger sees nothing: add a ghost user who holds no role.
    pipeline.users.save(
        UserAccount(
            id="usr_ghost", username="ghost",
            password_hash=pipeline.hasher.hash("ghost-password"),
            role="user", status="active", token_version=1,
        )
    )
    ghost = _login(client, "ghost", "ghost-password")
    missing = client.get(
        "/api/v1/approvals/req_eng/review",
        headers=_headers(ghost, "req_rev_ghost"),
    )
    assert missing.status_code == 404

    # Super admin deciding a department queue is a delegation (O2).
    approved = client.post(
        "/api/v1/approvals/req_eng/approve", headers=_headers(admin, "req_appr")
    )
    assert approved.status_code == 200
    delegated = _audit_actions(audits, "authz.approval.delegated")
    assert len(delegated) == 1
    assert delegated[0]["actor"] == "usr_admin"


def test_FR_RBAC_004_p1_3_approval_http_pending_invisible_in_documents() -> None:
    client, pipeline, _, _ = _assembly()
    _seed_request(pipeline, "req_eng", "doc_eng", "ver_eng", "dept_eng", "usr_bob")
    bob = _login(client, "bob", "bob-password")
    admin = _login(client, "admin", "admin-password")

    # Fail-closed through the documents routes: the pending document
    # is absent from the member's list, detail, and preview, while
    # the super admin's list row carries no current version.
    listed = client.get("/api/v1/documents", headers=_headers(bob, "req_list"))
    assert listed.json()["items"] == []
    detail = client.get(
        "/api/v1/documents/doc_eng", headers=_headers(bob, "req_detail")
    )
    assert detail.status_code == 404
    preview = client.get(
        "/api/v1/documents/doc_eng/preview", headers=_headers(bob, "req_prev")
    )
    assert preview.status_code == 404
    listed = client.get("/api/v1/documents", headers=_headers(admin, "req_list2"))
    items = listed.json()["items"]
    assert [item["document_id"] for item in items] == ["doc_eng"]
    assert items[0]["current_version"] is None
