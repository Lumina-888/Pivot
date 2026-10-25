"""S5: HTTP upload gate for FR-RBAC-004 (ADR-017 D5).

End-to-end through create_app: super admin, department admin and
editor uploads succeed and still land in the unassigned library;
reader and no-membership uploads are refused. The pre-existing
no-membership refusal keeps passing under the new gate.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline, policy_pdf
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.ports import Library as _Library
from pivot.auth.ports import Principal, UserAccount
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
    service.add_member(ADMIN, "dept_eng", "usr_alice", "dept_admin", "req_seed_a")
    service.add_member(ADMIN, "dept_eng", "usr_bob", "editor", "req_seed_b")
    service.add_member(ADMIN, "dept_eng", "usr_carol", "reader", "req_seed_c")
    client = TestClient(
        create_app(auth=pipeline.auth, documents=pipeline.documents),
        base_url="https://testserver",
    )
    return pipeline, client


def _login(client: TestClient, username: str, password: str, request_id: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"X-Request-ID": request_id},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _upload(client: TestClient, token: str, request_id: str):
    data = {"title": "Attendance Policy"}
    files = {"file": ("handbook.pdf", policy_pdf(), "application/pdf")}
    return client.post(
        "/api/v1/documents",
        data=data,
        files=files,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": request_id,
            "Idempotency-Key": f"idem-{request_id}",
        },
    )


def test_FR_RBAC_004_http_upload_gate_matrix() -> None:
    pipeline, client = _assembly()
    tokens = {
        "admin": _login(client, "admin", "admin-password", "req_login_admin"),
        "alice": _login(client, "alice", "correct-password", "req_login_alice"),
        "bob": _login(client, "bob", "bob-password", "req_login_bob"),
        "carol": _login(client, "carol", "carol-password", "req_login_carol"),
        "dave": _login(client, "dave", "dave-password", "req_login_dave"),
    }
    for user in ("admin", "alice", "bob"):
        response = _upload(client, tokens[user], f"req_up_{user}")
        assert response.status_code == 201, user
        record = pipeline.doc_store.get(response.json()["document_id"])
        assert record is not None
        # Uploads still default to the unassigned library (P1-3 owns
        # library selection); the gate only decides who may upload.
        assert record.library_id == "unassigned"
    for user in ("carol", "dave"):
        response = _upload(client, tokens[user], f"req_up_{user}")
        assert response.status_code == 403, user
        assert response.json()["code"] == "AUTH_FORBIDDEN"
