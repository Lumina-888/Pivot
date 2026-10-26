"""S4: HTTP project-folder endpoints and audit views (ADR-018 D4, D6).

Project folder routes mirror the department folder router shape,
with the manager changed to the project lead (or the owning
department's admin, or a super admin). The lead grant cap surfaces
as 422 on the folder-member routes, exactly like the project-member
routes. The lead audit view lists only its own project's events,
the owning department's view picks up the project's folder events
through their dept_id metadata and excludes other departments'
projects, and the permanent exception list covers project documents.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from harness import Pipeline
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.ports import Library as _Library
from pivot.auth.ports import Membership, Principal, UserAccount
from pivot.documents.ports import DocumentRecord
from pivot.http import create_app
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)
ALICE = Principal(user_id="usr_alice", username="alice", role="user", token_version=1)
BOB = Principal(user_id="usr_bob", username="bob", role="user", token_version=1)
DAVE = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)


def _assembly():
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
    pipeline.users.save(
        UserAccount(
            id="usr_dave", username="dave",
            password_hash=pipeline.hasher.hash("dave-password"),
            role="user", status="active", token_version=1,
        )
    )
    pipeline.users.save(
        UserAccount(
            id="usr_erin", username="erin",
            password_hash=pipeline.hasher.hash("erin-password"),
            role="user", status="active", token_version=1,
        )
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
    service.create_project(ADMIN, "proj_x", "跨部门项目", "dept_eng", "req_seed_px")
    service.appoint_project_lead(ADMIN, "proj_x", "usr_bob", "req_seed_lead")
    service.add_project_member(
        BOB, "proj_x", "usr_dave", "editor", "req_seed_dave",
        expires_at=pipeline.clock.now() + timedelta(days=30),
    )
    service.add_project_member(
        BOB, "proj_x", "usr_erin", "reader", "req_seed_erin",
        expires_at=pipeline.clock.now() + timedelta(days=30),
    )
    pipeline.doc_store.save(
        DocumentRecord(
            id="doc_px", title="项目文档", space="shared",
            created_by="usr_admin", library_id="proj_x",
        )
    )
    client = TestClient(
        create_app(
            auth=pipeline.auth, audits=audits, departments=service,
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


def _tokens(client):
    return {
        "admin": _login(client, "admin", "admin-password"),
        "alice": _login(client, "alice", "correct-password"),
        "bob": _login(client, "bob", "bob-password"),
        "dave": _login(client, "dave", "dave-password"),
    }


def _create_folder(client, token, folder_id="fld_px"):
    response = client.post(
        "/api/v1/admin/projects/proj_x/folders",
        json={"folder_id": folder_id, "name": "项目文件夹"},
        headers=_headers(token, "req_folder"),
    )
    assert response.status_code in (200, 201)
    return response.json()


def test_FR_RBAC_004_p1_4_project_folder_http_crud_matrix() -> None:
    client, _, _ = _assembly()
    tokens = _tokens(client)
    created = _create_folder(client, tokens["bob"])
    assert created["folder_id"] == "fld_px"
    assert created["library_id"] == "proj_x"
    again = _create_folder(client, tokens["alice"], "fld_px")
    assert again["folder_id"] == "fld_px"
    # A plain project member cannot create folders: visible scope, so
    # the denial is forbidden (outsiders would get not_found instead).
    denied = client.post(
        "/api/v1/admin/projects/proj_x/folders",
        json={"folder_id": "fld_b", "name": "文件夹 B"},
        headers=_headers(tokens["dave"], "req_folder3"),
    )
    assert denied.status_code == 403
    # Rename by the lead; read by the owning admin and the lead.
    renamed = client.patch(
        "/api/v1/admin/projects/proj_x/folders/fld_px",
        json={"name": "新名"},
        headers=_headers(tokens["bob"], "req_rename"),
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "新名"
    got = client.get(
        "/api/v1/admin/projects/proj_x/folders/fld_px",
        headers=_headers(tokens["alice"], "req_get"),
    )
    assert got.status_code == 200
    listed = client.get(
        "/api/v1/admin/projects/proj_x/folders",
        headers=_headers(tokens["bob"], "req_list"),
    )
    assert listed.status_code == 200
    assert [item["folder_id"] for item in listed.json()["items"]] == ["fld_px"]
    # A plain member lists nothing: no folder row, no bypass.
    member_listed = client.get(
        "/api/v1/admin/projects/proj_x/folders",
        headers=_headers(tokens["dave"], "req_list_member"),
    )
    assert member_listed.status_code == 200
    assert member_listed.json()["items"] == []


def test_FR_RBAC_004_p1_4_project_folder_http_member_cap_422() -> None:
    client, pipeline, _ = _assembly()
    tokens = _tokens(client)
    _create_folder(client, tokens["bob"])
    now = pipeline.clock.now()
    # A 30-day grant from the lead is fine.
    added = client.post(
        "/api/v1/admin/projects/proj_x/folders/fld_px/members",
        json={
            "user_id": "usr_dave", "folder_role": "reader",
            "expires_at": (now + timedelta(days=30)).isoformat(),
        },
        headers=_headers(tokens["bob"], "req_add"),
    )
    assert added.status_code == 201
    assert added.json()["folder_role"] == "reader"
    # The same lead granting a fresh member permanent or 61 days
    # gets 422. (Re-adding an existing row is a no-op return, not a
    # new grant, so the cap cases must use a fresh folder member.)
    permanent = client.post(
        "/api/v1/admin/projects/proj_x/folders/fld_px/members",
        json={"user_id": "usr_erin", "folder_role": "editor"},
        headers=_headers(tokens["bob"], "req_perm"),
    )
    assert permanent.status_code == 422
    assert permanent.json()["code"] == "GRANT_EXPIRY_INVALID"
    over = client.post(
        "/api/v1/admin/projects/proj_x/folders/fld_px/members",
        json={
            "user_id": "usr_erin", "folder_role": "editor",
            "expires_at": (now + timedelta(days=61)).isoformat(),
        },
        headers=_headers(tokens["bob"], "req_over"),
    )
    assert over.status_code == 422
    # The owning department's admin is uncapped: permanent passes.
    admin_grant = client.post(
        "/api/v1/admin/projects/proj_x/folders/fld_px/members",
        json={"user_id": "usr_erin", "folder_role": "full"},
        headers=_headers(tokens["alice"], "req_admin_perm"),
    )
    assert admin_grant.status_code in (200, 201)
    assert admin_grant.json()["expires_at"] is None


def test_FR_RBAC_004_p1_4_project_folder_http_move_and_delete() -> None:
    client, _, _ = _assembly()
    tokens = _tokens(client)
    _create_folder(client, tokens["bob"])
    client.post(
        "/api/v1/admin/projects/proj_x/folders/fld_px/members",
        json={"user_id": "usr_dave", "folder_role": "reader"},
        headers=_headers(tokens["alice"], "req_add_reader"),
    )
    moved = client.post(
        "/api/v1/admin/projects/proj_x/documents/doc_px/folder",
        json={"folder_id": "fld_px"},
        headers=_headers(tokens["bob"], "req_move"),
    )
    assert moved.status_code == 200
    assert moved.json()["moved"] is True
    assert moved.json()["folder_id"] == "fld_px"
    # A no-op move reports moved False and changes nothing.
    noop = client.post(
        "/api/v1/admin/projects/proj_x/documents/doc_px/folder",
        json={"folder_id": "fld_px"},
        headers=_headers(tokens["bob"], "req_noop"),
    )
    assert noop.status_code == 200
    assert noop.json()["moved"] is False
    # A folder reader cannot move documents.
    denied = client.post(
        "/api/v1/admin/projects/proj_x/documents/doc_px/folder",
        json={"folder_id": None},
        headers=_headers(tokens["dave"], "req_move_no"),
    )
    assert denied.status_code == 403
    # Non-empty: delete is refused; empty it, then delete passes.
    refused = client.delete(
        "/api/v1/admin/projects/proj_x/folders/fld_px",
        headers=_headers(tokens["bob"], "req_del_no"),
    )
    assert refused.status_code == 403
    client.post(
        "/api/v1/admin/projects/proj_x/documents/doc_px/folder",
        json={"folder_id": None},
        headers=_headers(tokens["bob"], "req_back"),
    )
    client.delete(
        "/api/v1/admin/projects/proj_x/folders/fld_px/members/usr_dave",
        headers=_headers(tokens["bob"], "req_rm"),
    )
    deleted = client.delete(
        "/api/v1/admin/projects/proj_x/folders/fld_px",
        headers=_headers(tokens["bob"], "req_del"),
    )
    assert deleted.status_code == 204


def test_FR_RBAC_004_p1_4_project_audit_views_http() -> None:
    client, _, service = _assembly()
    tokens = _tokens(client)
    _create_folder(client, tokens["bob"])
    # A second project under another department, with its own folder
    # event, must never leak into the owning admin's department view.
    service.create_department(ADMIN, "dept_art", "美术部", "req_seed_art")
    service.create_project(ADMIN, "proj_y", "另一项目", "dept_art", "req_seed_py")
    service.create_project_folder(ADMIN, "proj_y", "fld_py", "另一文件夹", "req_py")
    lead_view = client.get(
        "/api/v1/admin/projects/proj_x/audit-events",
        headers=_headers(tokens["bob"], "req_lead_view"),
    )
    assert lead_view.status_code == 200
    lead_actions = [item["action"] for item in lead_view.json()["items"]]
    assert "authz.folder.created" in lead_actions
    assert all("proj_y" not in str(item) for item in lead_view.json()["items"])
    dept_view = client.get(
        "/api/v1/admin/audit-events",
        headers=_headers(tokens["alice"], "req_dept_view"),
    )
    assert dept_view.status_code == 200
    dept_actions = [item["action"] for item in dept_view.json()["items"]]
    assert "authz.folder.created" in dept_actions
    assert not any(
        item.get("metadata", {}).get("project_id") == "proj_y"
        for item in dept_view.json()["items"]
    )
    # A plain project member gets neither view.
    member_view = client.get(
        "/api/v1/admin/projects/proj_x/audit-events",
        headers=_headers(tokens["dave"], "req_member_view"),
    )
    assert member_view.status_code == 403
    admin_view = client.get(
        "/api/v1/admin/projects/proj_x/audit-events",
        headers=_headers(tokens["admin"], "req_admin_view"),
    )
    assert admin_view.status_code == 200


def test_FR_RBAC_004_p1_4_project_exception_permanent_list_http() -> None:
    client, _, service = _assembly()
    tokens = _tokens(client)
    service.grant_exception(
        ALICE, "doc_px", "req_grant", target_user_id="usr_dave"
    )
    listed = client.get(
        "/api/v1/admin/documents/doc_px/exceptions",
        params={"permanent_only": True},
        headers=_headers(tokens["alice"], "req_list"),
    )
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["target_user_id"] == "usr_dave"
    assert items[0]["expires_at"] is None
    # The lead administers no department, so the list is forbidden.
    denied = client.get(
        "/api/v1/admin/documents/doc_px/exceptions",
        params={"permanent_only": True},
        headers=_headers(tokens["bob"], "req_list_no"),
    )
    assert denied.status_code == 403
