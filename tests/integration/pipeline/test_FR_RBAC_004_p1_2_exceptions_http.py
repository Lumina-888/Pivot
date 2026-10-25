"""HTTP exception endpoints for FR-RBAC-004 (ADR-017 D1, Q2, Q4).

End-to-end through create_app: grant/list/revoke over HTTP, the
power matrix (cross-department 404, dept-target 403, malformed
target 422), the permanent filter, and department-scoped audit
visibility for exception changes.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.ports import Principal, UserAccount
from pivot.documents.ports import DocumentRecord
from pivot.http import create_app
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)


def _assembly():
    pipeline = Pipeline()
    for user_id, username, password in (
        ("usr_carol", "carol", "carol-password"),
        ("usr_dave", "dave", "dave-password"),
    ):
        pipeline.users.save(
            UserAccount(
                id=user_id, username=username,
                password_hash=pipeline.hasher.hash(password),
                role="user", status="active", token_version=1,
            )
        )
    audits = AuditService(AppendOnlyAuditStore(), pipeline.clock)
    from pivot.auth.ports import Library as _Library

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
    service.create_department(ADMIN, "dept_art", "美术部", "req_seed_art")
    service.add_member(ADMIN, "dept_eng", "usr_alice", "dept_admin", "req_seed_a")
    service.add_member(ADMIN, "dept_eng", "usr_bob", "editor", "req_seed_b")
    service.add_member(ADMIN, "dept_art", "usr_carol", "dept_admin", "req_seed_c")
    pipeline.doc_store.save(
        DocumentRecord(
            id="doc_eng", title="技术文档", space="shared",
            created_by="usr_admin", library_id="dept_eng",
        )
    )
    pipeline.doc_store.save(
        DocumentRecord(
            id="doc_art", title="美术文档", space="shared",
            created_by="usr_admin", library_id="dept_art",
        )
    )
    app = create_app(auth=pipeline.auth, audits=audits, departments=service)
    client = TestClient(app, base_url="https://testserver")
    return pipeline, service, audits, client


def _login(client: TestClient, username: str, password: str, request_id: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"X-Request-ID": request_id},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _tokens(client: TestClient) -> dict[str, str]:
    return {
        "admin": _login(client, "admin", "admin-password", "req_login_admin"),
        "alice": _login(client, "alice", "correct-password", "req_login_alice"),
        "bob": _login(client, "bob", "bob-password", "req_login_bob"),
        "carol": _login(client, "carol", "carol-password", "req_login_carol"),
        "dave": _login(client, "dave", "dave-password", "req_login_dave"),
    }


def _auth(token: str, request_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Request-ID": request_id}


def test_FR_RBAC_004_http_grant_list_revoke_exception() -> None:
    _, _, _, client = _assembly()
    tokens = _tokens(client)
    granted = client.post(
        "/api/v1/admin/documents/doc_eng/exceptions",
        json={"target_user_id": "usr_dave", "reason": "跨组评审"},
        headers=_auth(tokens["alice"], "req_grant"),
    )
    assert granted.status_code == 201
    exception_id = granted.json()["id"]
    assert granted.json()["target_user_id"] == "usr_dave"
    again = client.post(
        "/api/v1/admin/documents/doc_eng/exceptions",
        json={"target_user_id": "usr_dave", "reason": "改期"},
        headers=_auth(tokens["alice"], "req_regrant"),
    )
    assert again.status_code == 200
    assert again.json()["id"] == exception_id
    listed = client.get(
        "/api/v1/admin/documents/doc_eng/exceptions",
        headers=_auth(tokens["alice"], "req_list"),
    )
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    revoked = client.delete(
        f"/api/v1/admin/documents/doc_eng/exceptions/{exception_id}",
        headers=_auth(tokens["alice"], "req_revoke"),
    )
    assert revoked.status_code == 204
    empty = client.get(
        "/api/v1/admin/documents/doc_eng/exceptions",
        headers=_auth(tokens["alice"], "req_list_after"),
    )
    assert empty.json()["items"] == []


def test_FR_RBAC_004_http_exception_permanent_filter() -> None:
    _, _, _, client = _assembly()
    tokens = _tokens(client)
    client.post(
        "/api/v1/admin/documents/doc_eng/exceptions",
        json={"target_user_id": "usr_dave"},
        headers=_auth(tokens["admin"], "req_perm"),
    )
    client.post(
        "/api/v1/admin/documents/doc_eng/exceptions",
        json={"target_user_id": "usr_carol", "expires_at": "2027-01-01T00:00:00Z"},
        headers=_auth(tokens["admin"], "req_temp"),
    )
    listed = client.get(
        "/api/v1/admin/documents/doc_eng/exceptions",
        params={"permanent_only": True},
        headers=_auth(tokens["admin"], "req_perm_list"),
    )
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["target_user_id"] == "usr_dave"
    assert items[0]["expires_at"] is None


def test_FR_RBAC_004_http_exception_power_matrix() -> None:
    _, _, _, client = _assembly()
    tokens = _tokens(client)
    cross = client.post(
        "/api/v1/admin/documents/doc_art/exceptions",
        json={"target_user_id": "usr_dave"},
        headers=_auth(tokens["alice"], "req_cross"),
    )
    assert cross.status_code == 404
    dept_target = client.post(
        "/api/v1/admin/documents/doc_eng/exceptions",
        json={"target_dept_id": "dept_art"},
        headers=_auth(tokens["alice"], "req_dept_target"),
    )
    assert dept_target.status_code == 403
    both = client.post(
        "/api/v1/admin/documents/doc_eng/exceptions",
        json={"target_user_id": "usr_dave", "target_dept_id": "dept_art"},
        headers=_auth(tokens["admin"], "req_both"),
    )
    assert both.status_code == 422
    neither = client.post(
        "/api/v1/admin/documents/doc_eng/exceptions",
        json={},
        headers=_auth(tokens["admin"], "req_neither"),
    )
    assert neither.status_code == 422
    plain_list = client.get(
        "/api/v1/admin/documents/doc_eng/exceptions",
        headers=_auth(tokens["dave"], "req_plain_list"),
    )
    assert plain_list.status_code == 403
    wrong_path = client.delete(
        "/api/v1/admin/documents/doc_art/exceptions/exc_ghost",
        headers=_auth(tokens["admin"], "req_wrong"),
    )
    assert wrong_path.status_code == 404


def test_FR_RBAC_004_http_exception_no_chain_through_grantee() -> None:
    _, _, _, client = _assembly()
    tokens = _tokens(client)
    client.post(
        "/api/v1/admin/documents/doc_art/exceptions",
        json={"target_user_id": "usr_alice"},
        headers=_auth(tokens["admin"], "req_seed"),
    )
    chained = client.post(
        "/api/v1/admin/documents/doc_art/exceptions",
        json={"target_user_id": "usr_dave"},
        headers=_auth(tokens["alice"], "req_chain"),
    )
    assert chained.status_code == 404


def test_FR_RBAC_004_http_exception_audit_in_own_dept_view() -> None:
    _, _, _, client = _assembly()
    tokens = _tokens(client)
    client.post(
        "/api/v1/admin/documents/doc_eng/exceptions",
        json={"target_user_id": "usr_dave"},
        headers=_auth(tokens["alice"], "req_grant"),
    )
    eng_view = client.get(
        "/api/v1/admin/audit-events", headers=_auth(tokens["alice"], "req_audit_eng")
    )
    assert eng_view.status_code == 200
    granted = [
        item for item in eng_view.json()["items"]
        if item["action"] == "authz.document_exception_granted"
    ]
    assert len(granted) == 1
    assert granted[0]["metadata"]["dept_id"] == "dept_eng"
    art_view = client.get(
        "/api/v1/admin/audit-events", headers=_auth(tokens["carol"], "req_audit_art")
    )
    assert art_view.status_code == 200
    assert all(
        item["action"] != "authz.document_exception_granted"
        for item in art_view.json()["items"]
    )
