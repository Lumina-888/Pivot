"""HTTP department admin endpoints for FR-RBAC-004 (ADR-016 D3, D10).

End-to-end through create_app: bearer auth, power matrix over HTTP,
department-scoped audit listing, and no audit mutation routes.
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
    # Mirror the S1 migration seeds: the public and system libraries
    # always exist in a real deployment; the in-memory store starts empty.
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
            id="doc_free", title="未分配文档", space="shared",
            created_by="usr_admin", library_id="unassigned",
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


def test_FR_RBAC_004_http_super_admin_creates_and_recreates_department():
    _, _, _, client = _assembly()
    tokens = _tokens(client)
    created = client.post(
        "/api/v1/admin/departments",
        json={"dept_id": "dept_ops", "name": "运维部"},
        headers=_auth(tokens["admin"], "req_create"),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["library_id"] == "dept_ops"
    assert body["kind"] == "department"
    assert body["dept_id"] == "dept_ops"
    again = client.post(
        "/api/v1/admin/departments",
        json={"dept_id": "dept_ops", "name": "运维部"},
        headers=_auth(tokens["admin"], "req_create_again"),
    )
    assert again.status_code == 200
    assert again.json()["library_id"] == "dept_ops"


def test_FR_RBAC_004_http_department_create_forbidden_and_unauthenticated():
    _, _, _, client = _assembly()
    tokens = _tokens(client)
    denied = client.post(
        "/api/v1/admin/departments",
        json={"dept_id": "dept_ops", "name": "运维部"},
        headers=_auth(tokens["alice"], "req_alice_create"),
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "AUTH_FORBIDDEN"
    anon = client.post(
        "/api/v1/admin/departments",
        json={"dept_id": "dept_ops", "name": "运维部"},
        headers={"X-Request-ID": "req_anon_create"},
    )
    assert anon.status_code == 401


def test_FR_RBAC_004_http_department_listing_is_scoped():
    _, _, _, client = _assembly()
    tokens = _tokens(client)
    listed = client.get(
        "/api/v1/admin/departments", headers=_auth(tokens["alice"], "req_list")
    )
    assert listed.status_code == 200
    ids = {item["library_id"] for item in listed.json()["items"]}
    assert ids == {"pub", "dept_eng"}
    other = client.get(
        "/api/v1/admin/departments/dept_art",
        headers=_auth(tokens["alice"], "req_get_other"),
    )
    assert other.status_code == 404
    assert other.json()["code"] == "RESOURCE_NOT_FOUND"
    pub = client.get(
        "/api/v1/admin/departments/pub",
        headers=_auth(tokens["alice"], "req_get_pub"),
    )
    assert pub.status_code == 200
    denied = client.get(
        "/api/v1/admin/departments", headers=_auth(tokens["dave"], "req_list_plain")
    )
    assert denied.status_code == 403


def test_FR_RBAC_004_http_member_power_matrix():
    _, _, _, client = _assembly()
    tokens = _tokens(client)
    added = client.post(
        "/api/v1/admin/departments/dept_eng/members",
        json={"user_id": "usr_dave", "dept_role": "reader"},
        headers=_auth(tokens["alice"], "req_add"),
    )
    assert added.status_code == 201
    assert added.json()["dept_role"] == "reader"
    escalation = client.post(
        "/api/v1/admin/departments/dept_eng/members",
        json={"user_id": "usr_dave", "dept_role": "dept_admin"},
        headers=_auth(tokens["alice"], "req_escalate"),
    )
    assert escalation.status_code == 403
    cross = client.post(
        "/api/v1/admin/departments/dept_art/members",
        json={"user_id": "usr_dave", "dept_role": "reader"},
        headers=_auth(tokens["alice"], "req_cross"),
    )
    assert cross.status_code == 404
    bad_role = client.post(
        "/api/v1/admin/departments/dept_eng/members",
        json={"user_id": "usr_dave", "dept_role": "superuser"},
        headers=_auth(tokens["admin"], "req_bad_role"),
    )
    assert bad_role.status_code == 422
    patched = client.patch(
        "/api/v1/admin/departments/dept_eng/members/usr_dave",
        json={"dept_role": "editor"},
        headers=_auth(tokens["alice"], "req_patch"),
    )
    assert patched.status_code == 200
    assert patched.json()["dept_role"] == "editor"
    removed = client.delete(
        "/api/v1/admin/departments/dept_eng/members/usr_dave",
        headers=_auth(tokens["alice"], "req_remove"),
    )
    assert removed.status_code == 204
    gone = client.delete(
        "/api/v1/admin/departments/dept_eng/members/usr_dave",
        headers=_auth(tokens["alice"], "req_remove_again"),
    )
    assert gone.status_code == 404


def test_FR_RBAC_004_http_claim_document_matrix():
    pipeline, _, _, client = _assembly()
    tokens = _tokens(client)
    claimed = client.post(
        "/api/v1/admin/documents/doc_free/claim",
        json={"library_id": "dept_eng"},
        headers=_auth(tokens["alice"], "req_claim"),
    )
    assert claimed.status_code == 200
    assert claimed.json()["library_id"] == "dept_eng"
    assert pipeline.doc_store.get("doc_free").library_id == "dept_eng"
    pipeline.doc_store.save(
        DocumentRecord(
            id="doc_free2", title="未分配文档二", space="shared",
            created_by="usr_admin", library_id="unassigned",
        )
    )
    cross = client.post(
        "/api/v1/admin/documents/doc_free2/claim",
        json={"library_id": "dept_eng"},
        headers=_auth(tokens["carol"], "req_claim_cross"),
    )
    assert cross.status_code == 404
    assert pipeline.doc_store.get("doc_free2").library_id == "unassigned"


def test_FR_RBAC_004_http_remove_department_rules():
    _, _, _, client = _assembly()
    tokens = _tokens(client)
    created = client.post(
        "/api/v1/admin/departments",
        json={"dept_id": "dept_ops", "name": "运维部"},
        headers=_auth(tokens["admin"], "req_create_ops"),
    )
    assert created.status_code == 201
    removed = client.delete(
        "/api/v1/admin/departments/dept_ops",
        headers=_auth(tokens["admin"], "req_remove_ops"),
    )
    assert removed.status_code == 204
    blocked = client.delete(
        "/api/v1/admin/departments/dept_eng",
        headers=_auth(tokens["admin"], "req_remove_eng"),
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "RESOURCE_FORBIDDEN"


def test_FR_RBAC_004_http_audit_listing_is_department_scoped():
    _, service, _, client = _assembly()
    tokens = _tokens(client)
    service.add_member(ADMIN, "dept_eng", "usr_dave", "reader", "req_audit_eng")
    service.add_member(ADMIN, "dept_art", "usr_dave", "reader", "req_audit_art")
    eng_view = client.get(
        "/api/v1/admin/audit-events", headers=_auth(tokens["alice"], "req_audit_list")
    )
    assert eng_view.status_code == 200
    items = eng_view.json()["items"]
    assert items
    assert all(item["metadata"].get("dept_id") == "dept_eng" for item in items)
    admin_view = client.get(
        "/api/v1/admin/audit-events", headers=_auth(tokens["admin"], "req_audit_admin")
    )
    assert admin_view.status_code == 200
    admin_depts = {
        item["metadata"].get("dept_id") for item in admin_view.json()["items"]
    }
    assert {"dept_eng", "dept_art"} <= admin_depts
    denied = client.get(
        "/api/v1/admin/audit-events", headers=_auth(tokens["dave"], "req_audit_plain")
    )
    assert denied.status_code == 403


def test_FR_RBAC_004_http_audit_events_have_no_mutation_route():
    _, _, _, client = _assembly()
    tokens = _tokens(client)
    put = client.put(
        "/api/v1/admin/audit-events",
        json={},
        headers=_auth(tokens["admin"], "req_audit_put"),
    )
    assert put.status_code in {404, 405}
    delete = client.delete(
        "/api/v1/admin/audit-events",
        headers=_auth(tokens["admin"], "req_audit_delete"),
    )
    assert delete.status_code in {404, 405}


def test_FR_RBAC_004_http_member_expiry_round_trip_and_purge():
    _, _, _, client = _assembly()
    tokens = _tokens(client)
    added = client.post(
        "/api/v1/admin/departments/dept_eng/members",
        json={
            "user_id": "usr_dave",
            "dept_role": "reader",
            "expires_at": "2030-01-01T00:00:00Z",
        },
        headers=_auth(tokens["admin"], "req_exp_add"),
    )
    assert added.status_code == 201
    assert added.json()["expires_at"] == "2030-01-01T00:00:00Z"
    kept = client.patch(
        "/api/v1/admin/departments/dept_eng/members/usr_dave",
        json={"dept_role": "editor"},
        headers=_auth(tokens["admin"], "req_exp_keep"),
    )
    assert kept.status_code == 200
    assert kept.json()["expires_at"] == "2030-01-01T00:00:00Z"
    assert kept.json()["dept_role"] == "editor"
    cleared = client.patch(
        "/api/v1/admin/departments/dept_eng/members/usr_dave",
        json={"dept_role": "editor", "expires_at": None},
        headers=_auth(tokens["admin"], "req_exp_clear"),
    )
    assert cleared.status_code == 200
    assert cleared.json()["expires_at"] is None
    past = client.post(
        "/api/v1/admin/departments/dept_eng/members",
        json={
            "user_id": "usr_carol",
            "dept_role": "reader",
            "expires_at": "2020-01-01T00:00:00Z",
        },
        headers=_auth(tokens["admin"], "req_exp_past"),
    )
    assert past.status_code == 201
    listed = client.get(
        "/api/v1/admin/departments/dept_eng/members",
        headers=_auth(tokens["admin"], "req_exp_list"),
    )
    assert listed.status_code == 200
    user_ids = [item["user_id"] for item in listed.json()["items"]]
    assert "usr_carol" not in user_ids
    assert "usr_dave" in user_ids
