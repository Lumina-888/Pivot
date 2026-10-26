"""S4: project-folder authorization closeout for FR-RBAC-004
(ADR-018 D4, D2, D3).

The S3 residual is closed here: the department-admin branch of
visible_folder_ids and the folder_visible bypass now cover project
libraries owned by the caller's department, and a project lead sees
every folder of the projects they lead regardless of folder role.
Project members see the default folder plus their own project
folders; outsiders see neither. Exceptions still coexist: an
exception-granted document inside an invisible project folder stays
visible.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeClock
from pivot.auth.errors import AuthError
from pivot.auth.ports import (
    DocumentAuthz,
    DocumentException,
    Folder,
    FolderMembership,
    Library,
    Membership,
    Principal,
)
from pivot.http.memory import InMemoryResources
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)
ENG_ADMIN = Principal(user_id="usr_alice", username="alice", role="user", token_version=1)
ART_ADMIN = Principal(user_id="usr_carol", username="carol", role="user", token_version=1)
LEAD = Principal(user_id="usr_bob", username="bob", role="user", token_version=1)
PX_EDITOR = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
PX_READER = Principal(user_id="usr_erin", username="erin", role="user", token_version=1)
DEPT_EDITOR = Principal(user_id="usr_frank", username="frank", role="user", token_version=1)
OUTSIDER = Principal(user_id="usr_ghost", username="ghost", role="user", token_version=1)

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)


def _seed():
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
            id="proj_y", name="另一项目", kind="project", dept_id="dept_art"
        ),
        "unassigned": Library(id="unassigned", name="未分配", kind="system"),
    }
    resources.memberships = {
        "usr_alice": (
            Membership(
                user_id="usr_alice", dept_id="dept_eng", dept_role="dept_admin",
                granted_by="usr_admin",
            ),
        ),
        "usr_carol": (
            Membership(
                user_id="usr_carol", dept_id="dept_art", dept_role="dept_admin",
                granted_by="usr_admin",
            ),
        ),
        "usr_bob": (
            Membership(
                user_id="usr_bob", dept_id="proj_x", dept_role="project_lead",
                granted_by="usr_alice",
            ),
        ),
        "usr_dave": (
            Membership(
                user_id="usr_dave", dept_id="proj_x", dept_role="editor",
                granted_by="usr_bob",
            ),
        ),
        "usr_erin": (
            Membership(
                user_id="usr_erin", dept_id="proj_x", dept_role="reader",
                granted_by="usr_bob",
            ),
        ),
        "usr_frank": (
            Membership(
                user_id="usr_frank", dept_id="dept_eng", dept_role="editor",
                granted_by="usr_admin",
            ),
        ),
    }
    resources.folders = {
        "fld_px": Folder(id="fld_px", library_id="proj_x", name="项目文件夹"),
        "fld_py": Folder(id="fld_py", library_id="proj_y", name="另一文件夹"),
    }
    resources.folder_memberships = {
        "usr_dave": (
            FolderMembership(
                folder_id="fld_px", user_id="usr_dave", folder_role="reader",
                granted_by="usr_admin",
            ),
        ),
    }
    resources.documents = {
        "doc_px_default": DocumentAuthz(
            id="doc_px_default", deleted=False, shared_visible=False,
            export_allowed=False, library_id="proj_x", folder_id=None,
        ),
        "doc_px_folder": DocumentAuthz(
            id="doc_px_folder", deleted=False, shared_visible=False,
            export_allowed=False, library_id="proj_x", folder_id="fld_px",
        ),
        "doc_py_folder": DocumentAuthz(
            id="doc_py_folder", deleted=False, shared_visible=False,
            export_allowed=False, library_id="proj_y", folder_id="fld_py",
        ),
    }
    return resources


def _authorize(resources, clock, principal, document_id) -> None:
    AccessControl(resources, clock=clock).authorize_document(
        principal, document_id, "req_authz"
    )


def _code(excinfo) -> str:
    return excinfo.value.code


def test_FR_RBAC_004_project_folder_visible_to_lead_and_owning_admin() -> None:
    clock = FakeClock(T0)
    resources = _seed()
    # The lead passes with no folder row: folder roles never restrict
    # the lead inside their own project (D2 bypass, S4).
    _authorize(resources, clock, LEAD, "doc_px_folder")
    # The owning department's admin passes the same way (S3 residual).
    _authorize(resources, clock, ENG_ADMIN, "doc_px_folder")
    _authorize(resources, clock, ADMIN, "doc_px_folder")
    # A live folder member passes in any role, even reader.
    _authorize(resources, clock, PX_EDITOR, "doc_px_folder")


def test_FR_RBAC_004_project_folder_hidden_from_member_and_outsider() -> None:
    clock = FakeClock(T0)
    resources = _seed()
    # A project member without a folder row sees nothing of the folder.
    with pytest.raises(AuthError) as excinfo:
        _authorize(resources, clock, PX_READER, "doc_px_folder")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # Another department's admin sees nothing of this project either.
    with pytest.raises(AuthError) as excinfo:
        _authorize(resources, clock, ART_ADMIN, "doc_px_folder")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        _authorize(resources, clock, OUTSIDER, "doc_px_folder")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    # The default folder is the library itself: any project member
    # passes on library visibility alone.
    _authorize(resources, clock, PX_READER, "doc_px_default")


def test_FR_RBAC_004_project_folder_exception_survives_invisible_folder() -> None:
    clock = FakeClock(T0)
    resources = _seed()
    # A department editor outside the project, granted an exception on
    # the folder document, still sees it through the exception channel.
    resources.exceptions["exc_1"] = DocumentException(
        id="exc_1", document_id="doc_px_folder",
        target_user_id="usr_frank", granted_by="usr_admin",
    )
    _authorize(resources, clock, DEPT_EDITOR, "doc_px_folder")
    resources.exceptions["exc_1"] = DocumentException(
        id="exc_1", document_id="doc_px_folder",
        target_user_id="usr_frank", granted_by="usr_admin",
        expires_at=T0 - timedelta(seconds=1),
    )
    with pytest.raises(AuthError) as excinfo:
        _authorize(resources, clock, DEPT_EDITOR, "doc_px_folder")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_project_folder_visible_sets() -> None:
    clock = FakeClock(T0)
    resources = _seed()
    access = AccessControl(resources, clock=clock)
    assert access.visible_folder_ids(ADMIN) == frozenset({"fld_px", "fld_py"})
    # Owning-department admin: all folders of owned projects.
    assert access.visible_folder_ids(ENG_ADMIN) == frozenset({"fld_px"})
    assert access.visible_folder_ids(ART_ADMIN) == frozenset({"fld_py"})
    # Lead: all folders of led projects, with no folder row needed.
    assert access.visible_folder_ids(LEAD) == frozenset({"fld_px"})
    # Member: only their own folders.
    assert access.visible_folder_ids(PX_EDITOR) == frozenset({"fld_px"})
    assert access.visible_folder_ids(PX_READER) == frozenset()
    assert access.visible_folder_ids(OUTSIDER) == frozenset()
    # folder_visible mirrors the same rule for one folder.
    assert access.folder_visible(LEAD, "fld_px", "proj_x") is True
    assert access.folder_visible(ENG_ADMIN, "fld_px", "proj_x") is True
    assert access.folder_visible(PX_EDITOR, "fld_px", "proj_x") is True
    assert access.folder_visible(PX_READER, "fld_px", "proj_x") is False
    assert access.folder_visible(ART_ADMIN, "fld_px", "proj_x") is False
    # An expired lead membership loses the bypass with it.
    resources.memberships["usr_bob"] = (
        Membership(
            user_id="usr_bob", dept_id="proj_x", dept_role="project_lead",
            granted_by="usr_alice",
            expires_at=T0 - timedelta(seconds=1),
        ),
    )
    assert access.visible_folder_ids(LEAD) == frozenset()
    assert access.folder_visible(LEAD, "fld_px", "proj_x") is False
