"""S2: folder-aware authorization for FR-RBAC-004 (ADR-018 D3, D2).

authorize_document now checks library visibility AND folder
visibility: a document in a restricted folder passes only for its
department's admins (who bypass folder roles), for live folder
members in any role, or through a live exception grant. Expired folder
members hold nothing. visible_folder_ids is the set the retriever
selection and the search scope derive from: super admins see every
folder, department admins see every folder in their departments,
members see their own folders inside libraries they can still see.
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
ENG_EDITOR = Principal(user_id="usr_bob", username="bob", role="user", token_version=1)
ENG_READER = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
ENG_READER2 = Principal(user_id="usr_erin", username="erin", role="user", token_version=1)
OUTSIDER = Principal(user_id="usr_ghost", username="ghost", role="user", token_version=1)

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)


def _seed(clock: FakeClock):
    resources = InMemoryResources()
    resources.libraries = {
        "pub": Library(id="pub", name="公共库", kind="public"),
        "dept_eng": Library(
            id="dept_eng", name="技术部", kind="department", dept_id="dept_eng"
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
        "usr_bob": (
            Membership(
                user_id="usr_bob", dept_id="dept_eng", dept_role="editor",
                granted_by="usr_admin",
            ),
        ),
        "usr_dave": (
            Membership(
                user_id="usr_dave", dept_id="dept_eng", dept_role="reader",
                granted_by="usr_admin",
            ),
        ),
        "usr_erin": (
            Membership(
                user_id="usr_erin", dept_id="dept_eng", dept_role="reader",
                granted_by="usr_admin",
            ),
        ),
    }
    resources.folders = {
        "fld_a": Folder(id="fld_a", library_id="dept_eng", name="文件夹 A"),
    }
    resources.folder_memberships = {
        "usr_dave": (
            FolderMembership(
                folder_id="fld_a", user_id="usr_dave", folder_role="reader",
                granted_by="usr_admin",
            ),
        ),
    }
    resources.documents = {
        "doc_default": DocumentAuthz(
            id="doc_default", deleted=False, shared_visible=False,
            export_allowed=False, library_id="dept_eng", folder_id=None,
        ),
        "doc_folder": DocumentAuthz(
            id="doc_folder", deleted=False, shared_visible=False,
            export_allowed=False, library_id="dept_eng", folder_id="fld_a",
        ),
    }
    return resources


def _authorize(resources, clock, principal, document_id) -> None:
    AccessControl(resources, clock=clock).authorize_document(
        principal, document_id, "req_authz"
    )


def _code(excinfo) -> str:
    return excinfo.value.code


def test_FR_RBAC_004_folder_default_document_visible_to_department() -> None:
    clock = FakeClock(T0)
    resources = _seed(clock)
    # The default folder is the library itself: library visibility
    # alone decides, with or without a folder membership.
    _authorize(resources, clock, ENG_EDITOR, "doc_default")
    _authorize(resources, clock, ENG_READER2, "doc_default")
    with pytest.raises(AuthError) as excinfo:
        _authorize(resources, clock, OUTSIDER, "doc_default")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_folder_document_visible_to_member_admin_and_super_admin() -> None:
    clock = FakeClock(T0)
    resources = _seed(clock)
    # A live folder member passes in any role, even reader.
    _authorize(resources, clock, ENG_READER, "doc_folder")
    # A department admin passes even though they hold no folder row:
    # folder roles never restrict a department admin (ADR-018 D2).
    _authorize(resources, clock, ENG_ADMIN, "doc_folder")
    _authorize(resources, clock, ADMIN, "doc_folder")


def test_FR_RBAC_004_folder_document_hidden_from_department_nonmember() -> None:
    clock = FakeClock(T0)
    resources = _seed(clock)
    # Same department, no folder membership: the document is answered
    # as not found, not forbidden, so folder contents never leak.
    with pytest.raises(AuthError) as excinfo:
        _authorize(resources, clock, ENG_EDITOR, "doc_folder")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        _authorize(resources, clock, ENG_READER2, "doc_folder")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_folder_expired_member_loses_folder() -> None:
    clock = FakeClock(T0)
    resources = _seed(clock)
    resources.folder_memberships["usr_dave"] = (
        FolderMembership(
            folder_id="fld_a", user_id="usr_dave", folder_role="reader",
            granted_by="usr_admin",
            expires_at=T0 - timedelta(seconds=1),
        ),
    )
    with pytest.raises(AuthError) as excinfo:
        _authorize(resources, clock, ENG_READER, "doc_folder")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_folder_exception_survives_invisible_folder() -> None:
    clock = FakeClock(T0)
    resources = _seed(clock)
    # Folders never replace exceptions: an exception-granted document
    # inside a folder the caller cannot see stays visible.
    resources.exceptions["exc_1"] = DocumentException(
        id="exc_1", document_id="doc_folder",
        target_user_id="usr_erin", granted_by="usr_admin",
    )
    _authorize(resources, clock, ENG_READER2, "doc_folder")
    # And an expired exception does not rescue it.
    resources.exceptions["exc_1"] = DocumentException(
        id="exc_1", document_id="doc_folder",
        target_user_id="usr_erin", granted_by="usr_admin",
        expires_at=T0 - timedelta(seconds=1),
    )
    with pytest.raises(AuthError) as excinfo:
        _authorize(resources, clock, ENG_READER2, "doc_folder")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_folder_visible_sets() -> None:
    clock = FakeClock(T0)
    resources = _seed(clock)
    access = AccessControl(resources, clock=clock)
    assert access.visible_folder_ids(ADMIN) == frozenset({"fld_a"})
    assert access.visible_folder_ids(ENG_ADMIN) == frozenset({"fld_a"})
    assert access.visible_folder_ids(ENG_READER) == frozenset({"fld_a"})
    assert access.visible_folder_ids(ENG_READER2) == frozenset()
    assert access.visible_folder_ids(OUTSIDER) == frozenset()
    # A folder membership in a department the caller left grants
    # nothing: visible folders intersect visible libraries.
    resources.memberships["usr_dave"] = ()
    assert access.visible_folder_ids(ENG_READER) == frozenset()
    # folder_visible mirrors the same rule for one folder.
    assert access.folder_visible(ENG_ADMIN, "fld_a", "dept_eng") is True
    assert access.folder_visible(ENG_READER, "fld_a", "dept_eng") is True
    assert access.folder_visible(ENG_READER2, "fld_a", "dept_eng") is False
