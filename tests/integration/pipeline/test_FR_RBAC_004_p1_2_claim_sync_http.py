"""S5: HTTP claim dispatch for FR-RBAC-004 (ADR-017 D3).

A successful claim dispatches the reconcile task with (document_id,
library_id, request_id, actor_id) through the injected submitter; with
no submitter wired, the claim still succeeds and nothing dispatches.
The task body itself (retries, final-failure audit) is covered in the
worker submitter tests; this file pins the router seam.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.ports import Library as _Library
from pivot.auth.ports import Principal
from pivot.documents.ports import DocumentRecord
from pivot.http import create_app
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)


def _assembly(claim_sync=None):
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
    pipeline.doc_store.save(
        DocumentRecord(
            id="doc_new", title="新文档", space="shared",
            created_by="usr_admin", library_id="unassigned",
        )
    )
    client = TestClient(
        create_app(
            auth=pipeline.auth, audits=audits, departments=service,
            claim_sync=claim_sync,
        ),
        base_url="https://testserver",
    )
    return client


def _admin_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin-password"},
        headers={"X-Request-ID": "req_login_admin"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _claim(client: TestClient, token: str, request_id: str):
    return client.post(
        "/api/v1/admin/documents/doc_new/claim",
        json={"library_id": "dept_eng"},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": request_id},
    )


def test_FR_RBAC_004_http_claim_dispatches_reconcile() -> None:
    dispatched: list[tuple] = []
    client = _assembly(claim_sync=lambda *args: dispatched.append(args))
    response = _claim(client, _admin_token(client), "req_claim")
    assert response.status_code == 200
    assert response.json()["library_id"] == "dept_eng"
    assert dispatched == [("doc_new", "dept_eng", "req_claim", "usr_admin")]


def test_FR_RBAC_004_http_claim_without_submitter_still_succeeds() -> None:
    client = _assembly()
    response = _claim(client, _admin_token(client), "req_claim")
    assert response.status_code == 200
    assert response.json()["library_id"] == "dept_eng"
