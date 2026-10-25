"""S3: project visibility in AccessControl for FR-RBAC-004 (ADR-018 D4, D2).

visible_libraries is pub plus own department libraries plus joined
projects, plus the owning-department branch: a department admin sees
their department's projects without joining them. is_project_lead
reads live lead rows only; super admins are never leads through this
helper (they use the global path). authorize_document needs no new
code for projects — default-folder documents pass on library
visibility — but the project facts are asserted here end to end.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeClock
from pivot.auth.errors import AuthError
from pivot.auth.ports import (
    DocumentAuthz,
    Library,
    Membership,
    Principal,
)
from pivot.http.memory import InMemoryResources
from pivot.security.rbac import AccessControl

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)
ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)
ENG_ADMIN = Principal(user_id="usr_alice", username="alice", role="user", token_version=1)
ART_ADMIN = Principal(user_id="usr_carol", username="carol", role="user", token_version=1)
LEAD = Principal(user_id="usr_erin", username="erin", role="user", token_version=1)
MEMBER = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
OUTSIDER = Principal(user_id="usr_ghost", username="ghost", role="user", token_version=1)


def _resources():
    resources = InMemoryResources()
    resources.libraries = {
        "pub": Library(id="pub", name="公共库", kind="public"),
        "dept_eng": Library(
            id="dept_eng", name="技术部", kind="department", dept_id="dept_eng"
        ),
        "dept_art": Library(
            id="dept_art", name="美术部", kind="department", dept_id="dept_art"
        ),
        "proj_x": Library(
            id="proj_x", name="跨部门项目", kind="project", dept_id="dept_eng"
        ),
        "proj_y": Library(
            id="proj_y", name="美术项目", kind="project", dept_id="dept_art"
        ),
        "unassigned": Library(id="unassigned", name="未分配", kind="system"),
    }
    resources.memberships = {
        "usr_alice": (
            Membership(
                user_id="usr_alice", dept_id="dept_eng",
                dept_role="dept_admin", granted_by="usr_admin",
            ),
        ),
        "usr_carol": (
            Membership(
                user_id="usr_carol", dept_id="dept_art",
                dept_role="dept_admin", granted_by="usr_admin",
            ),
        ),
        "usr_erin": (
            Membership(
                user_id="usr_erin", dept_id="proj_x",
                dept_role="project_lead", granted_by="usr_alice",
            ),
        ),
        "usr_dave": (
            Membership(
                user_id="usr_dave", dept_id="proj_x", dept_role="editor",
                granted_by="usr_erin",
            ),
        ),
    }
    resources.documents = {
        "doc_px": DocumentAuthz(
            id="doc_px", deleted=False, shared_visible=False,
            export_allowed=False, library_id="proj_x",
        ),
    }
    return resources


def test_FR_RBAC_004_p1_4_project_visible_union() -> None:
    access = AccessControl(_resources(), clock=FakeClock(T0))
    assert access.visible_libraries(LEAD) == frozenset({"pub", "proj_x"})
    assert access.visible_libraries(MEMBER) == frozenset({"pub", "proj_x"})
    assert access.visible_libraries(OUTSIDER) == frozenset({"pub"})
    assert access.visible_libraries(ADMIN) == frozenset(
        {"pub", "unassigned", "dept_eng", "dept_art", "proj_x", "proj_y"}
    )


def test_FR_RBAC_004_p1_4_project_owning_dept_admin_branch() -> None:
    access = AccessControl(_resources(), clock=FakeClock(T0))
    # Owning-department admins see their department's projects without
    # joining; other departments' projects stay invisible.
    visible = access.visible_libraries(ENG_ADMIN)
    assert "proj_x" in visible
    assert "proj_y" not in visible
    assert "dept_eng" in visible
    assert "dept_art" not in visible
    visible_art = access.visible_libraries(ART_ADMIN)
    assert "proj_y" in visible_art
    assert "proj_x" not in visible_art


def test_FR_RBAC_004_p1_4_project_is_project_lead() -> None:
    access = AccessControl(_resources(), clock=FakeClock(T0))
    assert access.is_project_lead(LEAD, "proj_x") is True
    assert access.is_project_lead(MEMBER, "proj_x") is False
    assert access.is_project_lead(LEAD, "proj_y") is False
    assert access.is_project_lead(ADMIN, "proj_x") is False
    assert access.is_project_lead(ENG_ADMIN, "proj_x") is False


def test_FR_RBAC_004_p1_4_project_is_project_lead_expired() -> None:
    resources = _resources()
    resources.memberships["usr_erin"] = (
        Membership(
            user_id="usr_erin", dept_id="proj_x",
            dept_role="project_lead", granted_by="usr_alice",
            expires_at=T0 - timedelta(seconds=1),
        ),
    )
    access = AccessControl(resources, clock=FakeClock(T0))
    assert access.is_project_lead(LEAD, "proj_x") is False
    assert "proj_x" not in access.visible_libraries(LEAD)


def test_FR_RBAC_004_p1_4_project_authorize_document() -> None:
    access = AccessControl(_resources(), clock=FakeClock(T0))
    access.authorize_document(LEAD, "doc_px", "req_auth")
    access.authorize_document(MEMBER, "doc_px", "req_auth")
    access.authorize_document(ENG_ADMIN, "doc_px", "req_auth")
    access.authorize_document(ADMIN, "doc_px", "req_auth")
    with pytest.raises(AuthError) as excinfo:
        access.authorize_document(OUTSIDER, "doc_px", "req_auth")
    assert excinfo.value.code == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        access.authorize_document(ART_ADMIN, "doc_px", "req_auth")
    assert excinfo.value.code == "RESOURCE_NOT_FOUND"
