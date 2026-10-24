"""Library visibility matrix for FR-RBAC-004 (ADR-016 D1-D3).

Visible libraries are the public library plus the user's own department
libraries (union, never intersection). Super admins see every library.
An unauthorized document is handled as nonexistent: callers never learn
whether it exists, and the shared_visible flag alone authorizes nothing.
"""

from __future__ import annotations

import pytest
from pivot.auth.errors import AuthError
from pivot.auth.ports import (
    ChunkAuthz,
    CitationAuthz,
    DocumentAuthz,
    Library,
    Membership,
    Principal,
)
from pivot.http.memory import InMemoryResources
from pivot.security.rbac import AccessControl


def _catalog() -> InMemoryResources:
    catalog = InMemoryResources()
    catalog.libraries = {
        "pub": Library(id="pub", name="公共库", kind="public"),
        "dept_eng": Library(
            id="dept_eng", name="技术部", kind="department", dept_id="dept_eng"
        ),
        "dept_art": Library(
            id="dept_art", name="美术部", kind="department", dept_id="dept_art"
        ),
        "unassigned": Library(id="unassigned", name="未分配", kind="system"),
    }
    catalog.memberships = {
        "usr_alice": (
            Membership(user_id="usr_alice", dept_id="dept_eng", dept_role="reader"),
        ),
        "usr_multi": (
            Membership(user_id="usr_multi", dept_id="dept_eng", dept_role="reader"),
            Membership(user_id="usr_multi", dept_id="dept_art", dept_role="editor"),
        ),
        "usr_eng_admin": (
            Membership(
                user_id="usr_eng_admin", dept_id="dept_eng", dept_role="dept_admin"
            ),
        ),
    }
    catalog.documents = {
        "doc_pub": DocumentAuthz(
            id="doc_pub",
            deleted=False,
            shared_visible=True,
            export_allowed=True,
            library_id="pub",
        ),
        "doc_eng": DocumentAuthz(
            id="doc_eng",
            deleted=False,
            shared_visible=False,
            export_allowed=False,
            library_id="dept_eng",
        ),
        "doc_art": DocumentAuthz(
            id="doc_art",
            deleted=False,
            shared_visible=False,
            export_allowed=False,
            library_id="dept_art",
        ),
        # Shared-visible flag set, but the library is another department's:
        # the flag must not authorize anything on its own.
        "doc_bait": DocumentAuthz(
            id="doc_bait",
            deleted=False,
            shared_visible=True,
            export_allowed=True,
            library_id="dept_art",
        ),
        "doc_unassigned": DocumentAuthz(
            id="doc_unassigned",
            deleted=False,
            shared_visible=False,
            export_allowed=False,
            library_id="unassigned",
        ),
        "doc_deleted": DocumentAuthz(
            id="doc_deleted",
            deleted=True,
            shared_visible=True,
            export_allowed=True,
            library_id="pub",
        ),
    }
    catalog.chunks = {
        "chk_eng": ChunkAuthz(id="chk_eng", document_id="doc_eng", published=True),
        "chk_art": ChunkAuthz(id="chk_art", document_id="doc_art", published=True),
    }
    catalog.citations = {
        "cit_eng": CitationAuthz(
            id="cit_eng", document_id="doc_eng", chunk_id="chk_eng"
        ),
        "cit_art": CitationAuthz(
            id="cit_art", document_id="doc_art", chunk_id="chk_art"
        ),
    }
    return catalog


def _principal(user_id: str, role: str = "user") -> Principal:
    return Principal(
        user_id=user_id, username=user_id, role=role, token_version=1
    )


@pytest.fixture
def access() -> AccessControl:
    return AccessControl(_catalog())


def test_FR_RBAC_004_visible_libraries_single_department(access: AccessControl):
    assert access.visible_libraries(_principal("usr_alice")) == {"pub", "dept_eng"}


def test_FR_RBAC_004_visible_libraries_multi_department_union(access: AccessControl):
    assert access.visible_libraries(_principal("usr_multi")) == {
        "pub",
        "dept_eng",
        "dept_art",
    }


def test_FR_RBAC_004_visible_libraries_no_membership_is_public_only(
    access: AccessControl,
):
    assert access.visible_libraries(_principal("usr_nobody")) == {"pub"}


def test_FR_RBAC_004_visible_libraries_admin_sees_all_libraries(
    access: AccessControl,
):
    visible = access.visible_libraries(_principal("usr_admin", role="admin"))
    assert {"pub", "unassigned", "dept_eng", "dept_art"} <= visible


def test_FR_RBAC_004_visible_library_document_allows_read(access: AccessControl):
    access.authorize_document(_principal("usr_alice"), "doc_eng", "req_1")


def test_FR_RBAC_004_other_department_document_is_not_found(access: AccessControl):
    with pytest.raises(AuthError) as error:
        access.authorize_document(_principal("usr_alice"), "doc_art", "req_1")
    assert error.value.code == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_shared_visible_flag_alone_authorizes_nothing(
    access: AccessControl,
):
    with pytest.raises(AuthError) as error:
        access.authorize_document(_principal("usr_alice"), "doc_bait", "req_1")
    assert error.value.code == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_unassigned_document_is_admin_only(access: AccessControl):
    with pytest.raises(AuthError) as error:
        access.authorize_document(_principal("usr_alice"), "doc_unassigned", "req_1")
    assert error.value.code == "RESOURCE_NOT_FOUND"
    access.authorize_document(
        _principal("usr_admin", role="admin"), "doc_unassigned", "req_1"
    )


def test_FR_RBAC_004_deleted_document_is_not_found_even_for_admin(
    access: AccessControl,
):
    with pytest.raises(AuthError) as error:
        access.authorize_document(
            _principal("usr_admin", role="admin"), "doc_deleted", "req_1"
        )
    assert error.value.code == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_admin_may_read_and_manage_any_library(access: AccessControl):
    admin = _principal("usr_admin", role="admin")
    for document_id in ("doc_pub", "doc_eng", "doc_art", "doc_unassigned"):
        access.authorize_document(admin, document_id, "req_1", action="read")
        access.authorize_document(admin, document_id, "req_1", action="manage")


def test_FR_RBAC_004_department_admin_cross_department_manage_denied(
    access: AccessControl,
):
    with pytest.raises(AuthError) as error:
        access.authorize_document(
            _principal("usr_eng_admin"), "doc_art", "req_1", action="manage"
        )
    assert error.value.code == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_department_admin_own_department_manage_allowed(
    access: AccessControl,
):
    access.authorize_document(
        _principal("usr_eng_admin"), "doc_eng", "req_1", action="manage"
    )


def test_FR_RBAC_004_chunk_and_citation_follow_document_library(
    access: AccessControl,
):
    alice = _principal("usr_alice")
    access.authorize_chunk(alice, "chk_eng", "req_1")
    access.authorize_citation(alice, "cit_eng", "req_1")
    with pytest.raises(AuthError) as error:
        access.authorize_chunk(alice, "chk_art", "req_1")
    assert error.value.code == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as error:
        access.authorize_citation(alice, "cit_art", "req_1")
    assert error.value.code == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_unknown_document_is_not_found(access: AccessControl):
    with pytest.raises(AuthError) as error:
        access.authorize_document(_principal("usr_alice"), "doc_unknown", "req_1")
    assert error.value.code == "RESOURCE_NOT_FOUND"
