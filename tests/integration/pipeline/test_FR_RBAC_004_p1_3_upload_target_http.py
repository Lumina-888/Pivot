"""S3: HTTP upload-with-target for FR-RBAC-004 (ADR-019 D1/D2).

End-to-end through POST /documents: target validation fail-closed
before anything is created, targeted uploads born pending_approval
with ingest skipped (the second layer), the self-approval fast path
reusing S2's approve() (one ingest dispatch, library already rewritten
when it fires), and the quarantine write/read contract (pending review
reads the uploaded bytes; decided requests close the review path).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline, policy_pdf
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.approvals import ApprovalService
from pivot.auth.ports import Library as _Library
from pivot.auth.ports import Membership, Principal, UserAccount
from pivot.documents.errors import DocumentError
from pivot.http import create_app
from pivot.security.rbac import AccessControl

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
    pipeline.resources.libraries["proj_x"] = _Library(
        id="proj_x", name="跨部门项目", kind="project", dept_id="dept_eng"
    )
    pipeline.resources.memberships["usr_alice"] = (
        Membership(
            user_id="usr_alice", dept_id="dept_eng", dept_role="dept_admin",
            granted_by="usr_admin",
        ),
    )
    pipeline.resources.memberships["usr_bob"] = (
        Membership(
            user_id="usr_bob", dept_id="proj_x", dept_role="project_lead",
            granted_by="usr_alice",
        ),
    )
    pipeline.resources.memberships["usr_frank"] = (
        Membership(
            user_id="usr_frank", dept_id="dept_eng", dept_role="editor",
            granted_by="usr_admin",
        ),
    )
    pipeline.resources.memberships["usr_dave"] = (
        Membership(
            user_id="usr_dave", dept_id="proj_x", dept_role="editor",
            granted_by="usr_bob",
        ),
    )
    for user_id, username, password in (
        ("usr_frank", "frank", "frank-password"),
        ("usr_dave", "dave", "dave-password"),
    ):
        pipeline.users.save(
            UserAccount(
                id=user_id,
                username=username,
                password_hash=pipeline.hasher.hash(password),
                role="user",
                status="active",
                token_version=1,
            )
        )
    dispatched: list = []

    def _ingest(version_id, request_id, actor_id):
        # Snapshot the library at dispatch time: approve() must have
        # already rewritten it to the target, never the old library.
        version = pipeline.versions.get(version_id)
        doc = pipeline.doc_store.get(version.document_id)
        dispatched.append((version_id, doc.library_id, actor_id))

    approvals = ApprovalService(
        store=pipeline.resources,
        documents=pipeline.doc_store,
        versions=pipeline.versions,
        objects=pipeline.doc_objects,
        access=AccessControl(pipeline.resources),
        audits=audits,
        clock=pipeline.clock,
        ingest=_ingest,
    )
    client = TestClient(
        create_app(
            auth=pipeline.auth,
            audits=audits,
            approvals=approvals,
            documents=pipeline.documents,
            ingest=_ingest,
        ),
        base_url="https://testserver",
    )
    return client, pipeline, approvals, audits, dispatched


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"X-Request-ID": "req_login"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _upload(client, token, *, target=None, request_id, filename="handbook.pdf"):
    data = {"title": "handbook"}
    if target is not None:
        data["target_library_id"] = target
    return client.post(
        "/api/v1/documents",
        data=data,
        files={"file": (filename, policy_pdf(), "application/pdf")},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": request_id,
        },
    )


def _audit_actions(audits, action: str) -> list[dict]:
    return [
        event.to_info() for event in audits.events() if event.action == action
    ]


def test_FR_RBAC_004_p1_3_upload_no_target_unchanged() -> None:
    client, pipeline, _, _, dispatched = _assembly()
    token = _login(client, "admin", "admin-password")
    response = _upload(client, token, request_id="req_plain")
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "uploaded"
    assert body["target_library_id"] is None
    assert body["approval_request_id"] is None
    assert len(dispatched) == 1


def test_FR_RBAC_004_p1_3_upload_target_pending_skips_ingest() -> None:
    client, pipeline, _, audits, dispatched = _assembly()
    token = _login(client, "frank", "frank-password")
    response = _upload(client, token, target="dept_eng", request_id="req_tgt")
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "pending_approval"
    assert body["target_library_id"] == "dept_eng"
    assert body["approval_request_id"]
    assert len(dispatched) == 0
    doc = pipeline.doc_store.get(body["document_id"])
    assert doc.library_id == "unassigned"
    version = pipeline.versions.get(body["version_id"])
    assert version.state == "pending_approval"
    assert len(_audit_actions(audits, "doc.approval.requested")) == 1


def test_FR_RBAC_004_p1_3_upload_target_invisible_and_unassigned_refused() -> None:
    client, pipeline, _, _, dispatched = _assembly()
    token = _login(client, "frank", "frank-password")
    for target in ("dept_art", "unassigned", "missing"):
        response = _upload(client, token, target=target, request_id="req_bad")
        assert response.status_code == 404
        assert response.json()["code"] == "RESOURCE_NOT_FOUND"
    assert pipeline.doc_store.list_active() == ()
    assert len(dispatched) == 0


def test_FR_RBAC_004_p1_3_upload_self_approve_department_admin() -> None:
    client, pipeline, _, audits, dispatched = _assembly()
    token = _login(client, "alice", "correct-password")
    response = _upload(client, token, target="dept_eng", request_id="req_self")
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "uploaded"
    assert body["approval_request_id"]
    assert len(_audit_actions(audits, "authz.approval.approved")) == 1
    assert _audit_actions(audits, "authz.approval.delegated") == []
    # Exactly one dispatch, fired by approve() after the rewrite.
    assert len(dispatched) == 1
    assert dispatched[0][1] == "dept_eng"
    doc = pipeline.doc_store.get(body["document_id"])
    assert doc.library_id == "dept_eng"
    request = pipeline.resources.approval_requests[body["approval_request_id"]]
    assert request.status == "approved"


def test_FR_RBAC_004_p1_3_upload_self_approve_public_is_ordinary() -> None:
    client, pipeline, _, audits, dispatched = _assembly()
    token = _login(client, "admin", "admin-password")
    response = _upload(client, token, target="pub", request_id="req_self_pub")
    assert response.status_code == 201
    assert response.json()["state"] == "uploaded"
    assert len(_audit_actions(audits, "authz.approval.approved")) == 1
    # O2: a super admin on the public queue acts ordinarily, not by
    # delegation.
    assert _audit_actions(audits, "authz.approval.delegated") == []
    assert len(dispatched) == 1


def test_FR_RBAC_004_p1_3_upload_self_approve_admin_on_department_is_delegated() -> None:
    client, pipeline, _, audits, dispatched = _assembly()
    token = _login(client, "admin", "admin-password")
    response = _upload(client, token, target="dept_eng", request_id="req_self_del")
    assert response.status_code == 201
    assert response.json()["state"] == "uploaded"
    assert len(_audit_actions(audits, "authz.approval.approved")) == 1
    # O2: the same super admin on a department queue acts by
    # delegation, recorded alongside the ordinary approval.
    delegated = _audit_actions(audits, "authz.approval.delegated")
    assert len(delegated) == 1
    assert delegated[0]["actor"] == "usr_admin"
    assert len(dispatched) == 1


def test_FR_RBAC_004_p1_3_upload_self_approve_project_lead() -> None:
    client, pipeline, _, audits, dispatched = _assembly()
    token = _login(client, "bob", "bob-password")
    response = _upload(client, token, target="proj_x", request_id="req_self_px")
    assert response.status_code == 201
    assert response.json()["state"] == "uploaded"
    assert len(_audit_actions(audits, "authz.approval.approved")) == 1
    assert _audit_actions(audits, "authz.approval.delegated") == []
    assert len(dispatched) == 1
    assert dispatched[0][1] == "proj_x"


def test_FR_RBAC_004_p1_3_upload_repeat_creates_no_second_request() -> None:
    client, pipeline, _, audits, dispatched = _assembly()
    token = _login(client, "frank", "frank-password")
    first = _upload(client, token, target="dept_eng", request_id="req_r1")
    assert first.status_code == 201
    second = _upload(client, token, target="dept_eng", request_id="req_r2")
    assert second.status_code == 201
    assert second.json()["version_id"] == first.json()["version_id"]
    assert second.json()["approval_request_id"] == first.json()["approval_request_id"]
    assert len(pipeline.resources.approval_requests) == 1
    assert len(_audit_actions(audits, "doc.approval.requested")) == 1
    assert len(dispatched) == 0


def test_FR_RBAC_004_p1_3_upload_quarantine_contract() -> None:
    client, pipeline, approvals, audits, _ = _assembly()
    token = _login(client, "frank", "frank-password")
    response = _upload(client, token, target="dept_eng", request_id="req_q")
    body = response.json()
    key = f"quarantine/{body['document_id']}/{body['version_id']}"
    assert pipeline.doc_objects.get(key) == policy_pdf()
    # Pending review reads the uploaded bytes from the same key.
    content = approvals.review_read(FRANK, body["approval_request_id"], "req_review")
    assert content.body == policy_pdf()
    assert len(_audit_actions(audits, "doc.approval.review")) == 1
    # Once decided, the dedicated review path closes (S2 rule). The
    # reader here is the proposer herself, so the refusal is the
    # decided-state refusal, not a scope refusal.
    ALICE = Principal(user_id="usr_alice", username="alice", role="user", token_version=1)
    client2, pipeline2, approvals2, _, _ = _assembly()
    token2 = _login(client2, "alice", "correct-password")
    decided = _upload(client2, token2, target="dept_eng", request_id="req_q2")
    request_id = decided.json()["approval_request_id"]
    try:
        approvals2.review_read(ALICE, request_id, "req_review2")
    except DocumentError as exc:
        assert exc.code == "RESOURCE_FORBIDDEN"
    else:
        raise AssertionError("review of a decided request must fail")


def test_FR_RBAC_004_p1_3_upload_retarget_http() -> None:
    client, pipeline, _, audits, dispatched = _assembly()
    token = _login(client, "frank", "frank-password")
    response = _upload(client, token, target="dept_eng", request_id="req_rt0")
    assert response.status_code == 201
    body = response.json()
    request_id = body["approval_request_id"]
    # The proposer retargets to the public library over HTTP.
    retargeted = client.post(
        f"/api/v1/approvals/{request_id}/retarget",
        json={"target_library_id": "pub"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_rt1",
        },
    )
    assert retargeted.status_code == 200
    retargeted_body = retargeted.json()
    assert retargeted_body["request_id"] == request_id
    assert retargeted_body["target_library_id"] == "pub"
    assert retargeted_body["status"] == "pending"
    # No new request, no ingest, version still pending_approval.
    assert len(pipeline.resources.approval_requests) == 1
    assert len(dispatched) == 0
    version = pipeline.versions.get(body["version_id"])
    assert version.state == "pending_approval"
    events = _audit_actions(audits, "doc.approval.retargeted")
    assert len(events) == 1
    assert events[0]["metadata"]["old_target_library_id"] == "dept_eng"
    assert events[0]["metadata"]["new_target_library_id"] == "pub"
    # Retargeting into an invisible department reads as not_found.
    refused = client.post(
        f"/api/v1/approvals/{request_id}/retarget",
        json={"target_library_id": "dept_art"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_rt2",
        },
    )
    assert refused.status_code == 404
