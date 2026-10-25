"""S3: HTTP project endpoints for FR-RBAC-004 (ADR-018 D4).

Project routes mirror the department router shape: create/list/get/
remove, member add/set/remove/list, lead appointment, and the shared
claim route (which dispatches the claim-sync reconciler for project
targets exactly like department targets). Lead cap violations are
service-level ValueErrors proven in the unit suite, not HTTP shapes:
no ValueError handler exists, so this file asserts only the mapped
AuthError shapes (404/403) plus the happy paths.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from harness import Pipeline
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.ports import Library as _Library
from pivot.auth.ports import Membership, Principal
from pivot.documents.ports import DocumentRecord
from pivot.http import create_app
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)


def _assembly(claim_sync=None):
    pipeline = Pipeline()
    # The Pipeline clock is fixed at 2026-09-06 while the fake store
    # purges by real now: advance the clock to real now so a temp
    # grant inside the 60-day lead cap is also future for the purge.
    pipeline.clock.advance(
        int((datetime.now(UTC) - pipeline.clock.now()).total_seconds())
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
            id="doc_un", title="未分配文档", space="shared",
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


def _create_project(client, token, project_id="proj_x"):
    response = client.post(
        "/api/v1/admin/projects",
        json={
            "project_id": project_id, "name": "跨部门项目",
            "owning_dept_id": "dept_eng",
        },
        headers=_headers(token, "req_project"),
    )
    assert response.status_code in (200, 201)
    return response.json()


def test_FR_RBAC_004_p1_4_project_http_crud() -> None:
    client, _, _ = _assembly()
    alice = _login(client, "alice", "correct-password")
    bob = _login(client, "bob", "bob-password")
    created = _create_project(client, alice)
    assert created["kind"] == "project"
    assert created["dept_id"] == "dept_eng"
    again = _create_project(client, alice)
    assert again["library_id"] == "proj_x"
    listed = client.get(
        "/api/v1/admin/projects", headers=_headers(alice, "req_list")
    )
    assert listed.status_code == 200
    assert [item["library_id"] for item in listed.json()["items"]] == [
        "proj_x"
    ]
    got = client.get(
        "/api/v1/admin/projects/proj_x", headers=_headers(alice, "req_get")
    )
    assert got.status_code == 200
    assert got.json()["name"] == "跨部门项目"
    # Bob is a department editor, not a project member: the project
    # is invisible to him.
    missing = client.get(
        "/api/v1/admin/projects/proj_x", headers=_headers(bob, "req_get")
    )
    assert missing.status_code == 404
    removed = client.delete(
        "/api/v1/admin/projects/proj_x", headers=_headers(alice, "req_rm")
    )
    assert removed.status_code == 204


def test_FR_RBAC_004_p1_4_project_http_members_and_lead() -> None:
    client, _, _ = _assembly()
    alice = _login(client, "alice", "correct-password")
    bob = _login(client, "bob", "bob-password")
    _create_project(client, alice)
    lead = client.post(
        "/api/v1/admin/projects/proj_x/lead",
        json={"user_id": "usr_bob"},
        headers=_headers(alice, "req_lead"),
    )
    assert lead.status_code in (200, 201)
    assert lead.json()["dept_role"] == "project_lead"
    # Bob the lead adds Alice as a temp editor; the role patch
    # tri-state keeps the stored expiry when omitted. The expiry sits
    # 30 days out: inside the lead cap and future for the store purge.
    expires = (datetime.now(UTC) + timedelta(days=30)).isoformat().replace(
        "+00:00", "Z"
    )
    added = client.post(
        "/api/v1/admin/projects/proj_x/members",
        json={
            "user_id": "usr_alice", "project_role": "editor",
            "expires_at": expires,
        },
        headers=_headers(bob, "req_add"),
    )
    assert added.status_code in (200, 201)
    assert added.json()["dept_role"] == "editor"
    patched = client.patch(
        "/api/v1/admin/projects/proj_x/members/usr_alice",
        json={"project_role": "reader"},
        headers=_headers(bob, "req_patch"),
    )
    assert patched.status_code == 200
    assert patched.json()["dept_role"] == "reader"
    assert patched.json()["expires_at"] == expires
    # A lead cannot appoint another lead through the member route.
    denied = client.post(
        "/api/v1/admin/projects/proj_x/members",
        json={
            "user_id": "usr_alice", "project_role": "project_lead",
            "expires_at": expires,
        },
        headers=_headers(bob, "req_add2"),
    )
    assert denied.status_code == 403
    removed = client.delete(
        "/api/v1/admin/projects/proj_x/members/usr_alice",
        headers=_headers(bob, "req_rm"),
    )
    assert removed.status_code == 204
    members = client.get(
        "/api/v1/admin/projects/proj_x/members",
        headers=_headers(bob, "req_members"),
    )
    assert members.status_code == 200
    assert [m["user_id"] for m in members.json()["items"]] == ["usr_bob"]


def test_FR_RBAC_004_p1_4_project_http_lead_cap_maps_to_422() -> None:
    client, _, _ = _assembly()
    alice = _login(client, "alice", "correct-password")
    bob = _login(client, "bob", "bob-password")
    _create_project(client, alice)
    client.post(
        "/api/v1/admin/projects/proj_x/lead",
        json={"user_id": "usr_bob"},
        headers=_headers(alice, "req_lead"),
    )
    over_cap = (datetime.now(UTC) + timedelta(days=61)).isoformat().replace(
        "+00:00", "Z"
    )
    denied = client.post(
        "/api/v1/admin/projects/proj_x/members",
        json={
            "user_id": "usr_alice", "project_role": "editor",
            "expires_at": over_cap,
        },
        headers=_headers(bob, "req_over"),
    )
    assert denied.status_code == 422
    assert denied.json()["code"] == "GRANT_EXPIRY_INVALID"
    permanent = client.post(
        "/api/v1/admin/projects/proj_x/members",
        json={"user_id": "usr_alice", "project_role": "editor"},
        headers=_headers(bob, "req_perm"),
    )
    assert permanent.status_code == 422
    # The owning department admin is uncapped: the same permanent
    # grant through her token succeeds.
    granted = client.post(
        "/api/v1/admin/projects/proj_x/members",
        json={"user_id": "usr_alice", "project_role": "editor"},
        headers=_headers(alice, "req_admin_perm"),
    )
    assert granted.status_code in (200, 201)
    # A lead patching that member to permanent is capped the same way.
    unpermed = client.patch(
        "/api/v1/admin/projects/proj_x/members/usr_alice",
        json={"project_role": "editor", "expires_at": None},
        headers=_headers(bob, "req_unperm"),
    )
    assert unpermed.status_code == 422


def test_FR_RBAC_004_p1_4_project_http_claim_dispatches_sync() -> None:
    dispatched: list[tuple] = []

    def claim_sync(document_id, library_id, request_id, actor_id):
        dispatched.append((document_id, library_id, actor_id))

    client, _, _ = _assembly(claim_sync=claim_sync)
    alice = _login(client, "alice", "correct-password")
    bob = _login(client, "bob", "bob-password")
    _create_project(client, alice)
    client.post(
        "/api/v1/admin/projects/proj_x/lead",
        json={"user_id": "usr_bob"},
        headers=_headers(alice, "req_lead"),
    )
    claimed = client.post(
        "/api/v1/admin/documents/doc_un/claim",
        json={"library_id": "proj_x"},
        headers=_headers(bob, "req_claim"),
    )
    assert claimed.status_code == 200
    assert claimed.json()["library_id"] == "proj_x"
    assert dispatched == [("doc_un", "proj_x", "usr_bob")]


def test_FR_RBAC_004_p1_4_project_http_remove_nonempty_forbidden() -> None:
    client, _, _ = _assembly()
    alice = _login(client, "alice", "correct-password")
    _create_project(client, alice)
    client.post(
        "/api/v1/admin/projects/proj_x/lead",
        json={"user_id": "usr_bob"},
        headers=_headers(alice, "req_lead"),
    )
    removed = client.delete(
        "/api/v1/admin/projects/proj_x", headers=_headers(alice, "req_rm")
    )
    assert removed.status_code == 403
