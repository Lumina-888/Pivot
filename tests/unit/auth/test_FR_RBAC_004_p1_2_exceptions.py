"""S3: document-level exceptions for FR-RBAC-004 (ADR-017 D1, Q2, Q4).

Grant-only whole-document visibility: a personal grant or a
department-target grant (super admin only) lets the grantee see one
document outside its library. Department targets expand dynamically
over live memberships: joining a department gains the document,
leaving (or expiring) loses it. Exceptions never widen a library,
never chain (a grantor who sees a document only through an exception
cannot pass it on), and never outlive their expiry (exclusive
boundary, same as membership expiry in S2).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeClock
from pivot.audit.ports import Actor
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.departments import DepartmentAdminService
from pivot.auth.errors import AuthError
from pivot.auth.ports import (
    DocumentAuthz,
    Library,
    Membership,
    Principal,
    UserAccount,
)
from pivot.documents.ports import DocumentRecord
from pivot.http.memory import (
    InMemoryResources,
    InMemoryUserDirectory,
    MemoryDocuments,
)
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)
ENG_ADMIN = Principal(user_id="usr_alice", username="alice", role="user", token_version=1)
ENG_EDITOR = Principal(user_id="usr_bob", username="bob", role="user", token_version=1)
ART_ADMIN = Principal(user_id="usr_carol", username="carol", role="user", token_version=1)
PLAIN = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
ERIN = Principal(user_id="usr_erin", username="erin", role="user", token_version=1)
FRANK = Principal(user_id="usr_frank", username="frank", role="user", token_version=1)

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)


def _seed(clock: FakeClock):
    resources = InMemoryResources()
    resources.libraries = {
        "pub": Library(id="pub", name="公共库", kind="public"),
        "dept_eng": Library(
            id="dept_eng", name="技术部", kind="department", dept_id="dept_eng"
        ),
        "dept_art": Library(
            id="dept_art", name="美术部", kind="department", dept_id="dept_art"
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
        "usr_carol": (
            Membership(
                user_id="usr_carol", dept_id="dept_art", dept_role="dept_admin",
                granted_by="usr_admin",
            ),
        ),
    }
    # The authorization catalog reads documents from here; the service's
    # document store below is a separate object with the same rows.
    resources.documents = {
        doc_id: DocumentAuthz(
            id=doc_id, deleted=False, shared_visible=False,
            export_allowed=False, library_id=library_id,
        )
        for doc_id, library_id in (
            ("doc_eng", "dept_eng"),
            ("doc_art", "dept_art"),
            ("doc_pub", "pub"),
        )
    }
    users = InMemoryUserDirectory(
        [
            UserAccount(
                id=user_id, username=username, password_hash="x",
                role=role, status="active", token_version=1,
            )
            for user_id, username, role in (
                ("usr_admin", "admin", "admin"),
                ("usr_alice", "alice", "user"),
                ("usr_bob", "bob", "user"),
                ("usr_carol", "carol", "user"),
                ("usr_dave", "dave", "user"),
                ("usr_erin", "erin", "user"),
                ("usr_frank", "frank", "user"),
            )
        ]
    )
    documents = MemoryDocuments()
    for doc_id, library_id in (
        ("doc_eng", "dept_eng"),
        ("doc_art", "dept_art"),
        ("doc_pub", "pub"),
    ):
        documents.save(
            DocumentRecord(
                id=doc_id, title=doc_id, space="shared",
                created_by="usr_admin", library_id=library_id,
            )
        )
    audits = AuditService(AppendOnlyAuditStore(), clock)
    service = DepartmentAdminService(
        store=resources,
        documents=documents,
        users=users,
        access=AccessControl(resources, clock=clock),
        audits=audits,
        clock=clock,
    )
    return service, resources, documents, users, audits


def _actions(audits) -> list[dict]:
    return [event.to_info() for event in audits.events()]


def _authorize(resources, clock, principal, document_id) -> None:
    AccessControl(resources, clock=clock).authorize_document(
        principal, document_id, "req_authz"
    )


def _code(excinfo) -> str:
    return excinfo.value.code


def test_FR_RBAC_004_exception_dept_admin_grants_personal_on_own_doc() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, audits = _seed(clock)
    exception, created = service.grant_exception(
        ENG_ADMIN, "doc_eng", "req_grant",
        target_user_id="usr_dave", reason="跨组评审",
    )
    assert created is True
    assert exception.target_user_id == "usr_dave"
    assert exception.target_dept_id is None
    assert exception.expires_at is None
    _authorize(resources, clock, PLAIN, "doc_eng")
    granted = [
        event for event in _actions(audits)
        if event["action"] == "authz.document_exception_granted"
    ]
    assert len(granted) == 1
    assert granted[0]["metadata"]["dept_id"] == "dept_eng"
    assert granted[0]["metadata"]["target_user_id"] == "usr_dave"


def test_FR_RBAC_004_exception_cross_department_grant_is_not_found() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    with pytest.raises(AuthError) as excinfo:
        service.grant_exception(
            ENG_ADMIN, "doc_art", "req_cross",
            target_user_id="usr_dave",
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_exception_plain_user_grant_is_forbidden() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    with pytest.raises(AuthError) as excinfo:
        service.grant_exception(
            PLAIN, "doc_eng", "req_plain",
            target_user_id="usr_erin",
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"


def test_FR_RBAC_004_exception_dept_target_is_super_admin_only() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    with pytest.raises(AuthError) as excinfo:
        service.grant_exception(
            ENG_ADMIN, "doc_eng", "req_dept_target",
            target_dept_id="dept_art",
        )
    assert _code(excinfo) == "AUTH_FORBIDDEN"


def test_FR_RBAC_004_exception_grant_requires_exactly_one_target() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    with pytest.raises(ValueError):
        service.grant_exception(ADMIN, "doc_eng", "req_both",
                                target_user_id="usr_dave",
                                target_dept_id="dept_art")
    with pytest.raises(ValueError):
        service.grant_exception(ADMIN, "doc_eng", "req_neither")


def test_FR_RBAC_004_exception_grant_to_unknown_target_is_not_found() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    with pytest.raises(AuthError) as excinfo:
        service.grant_exception(
            ADMIN, "doc_eng", "req_no_user", target_user_id="usr_ghost",
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        service.grant_exception(
            ADMIN, "doc_eng", "req_no_dept", target_dept_id="dept_ghost",
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        service.grant_exception(
            ADMIN, "doc_eng", "req_pub_target", target_dept_id="pub",
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_exception_grant_on_deleted_doc_is_not_found() -> None:
    clock = FakeClock(T0)
    service, _, documents, _, _ = _seed(clock)
    documents.save(
        DocumentRecord(
            id="doc_gone", title="gone", space="shared",
            created_by="usr_admin", library_id="dept_eng",
            deleted_at=T0,
        )
    )
    with pytest.raises(AuthError) as excinfo:
        service.grant_exception(
            ADMIN, "doc_gone", "req_gone", target_user_id="usr_dave",
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_exception_does_not_chain_through_grantee() -> None:
    # Carol administers art and sees doc_eng only through a super-admin
    # exception; she still cannot grant doc_eng onward: grantor
    # visibility is judged by library scope alone, never by exceptions.
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    service.grant_exception(
        ADMIN, "doc_eng", "req_seed", target_user_id="usr_carol",
    )
    with pytest.raises(AuthError) as excinfo:
        service.grant_exception(
            ART_ADMIN, "doc_eng", "req_chain",
            target_user_id="usr_frank",
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_exception_dept_target_expands_and_shrinks() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    service.grant_exception(
        ADMIN, "doc_eng", "req_dept", target_dept_id="dept_art",
    )
    # Art members see the eng document through the department grant.
    _authorize(resources, clock, ART_ADMIN, "doc_eng")
    with pytest.raises(AuthError):
        _authorize(resources, clock, ERIN, "doc_eng")
    # Joining the department gains the document automatically.
    service.add_member(ADMIN, "dept_art", "usr_erin", "reader", "req_join")
    _authorize(resources, clock, ERIN, "doc_eng")
    # Leaving loses it automatically.
    service.remove_member(ADMIN, "dept_art", "usr_erin", "req_leave")
    with pytest.raises(AuthError):
        _authorize(resources, clock, ERIN, "doc_eng")


def test_FR_RBAC_004_exception_dept_target_expired_member_not_expanded() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    service.grant_exception(
        ADMIN, "doc_eng", "req_dept", target_dept_id="dept_art",
    )
    service.add_member(
        ADMIN, "dept_art", "usr_erin", "reader", "req_join",
        expires_at=T0 + timedelta(days=365),
    )
    _authorize(resources, clock, ERIN, "doc_eng")
    clock.advance(366 * 24 * 3600)
    with pytest.raises(AuthError):
        _authorize(resources, clock, ERIN, "doc_eng")


def test_FR_RBAC_004_exception_regrant_updates_row_not_duplicate() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    first, created = service.grant_exception(
        ENG_ADMIN, "doc_eng", "req_first",
        target_user_id="usr_dave", reason="v1",
        expires_at=T0 + timedelta(days=30),
    )
    assert created is True
    second, created = service.grant_exception(
        ENG_ADMIN, "doc_eng", "req_second",
        target_user_id="usr_dave", reason="v2",
        expires_at=T0 + timedelta(days=90),
    )
    assert created is False
    assert second.id == first.id
    assert second.reason == "v2"
    assert second.expires_at == T0 + timedelta(days=90)
    rows = service.list_exceptions(ADMIN, "doc_eng", "req_list")
    assert len(rows) == 1


def test_FR_RBAC_004_exception_expired_row_regrant_is_renewal() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    first, _ = service.grant_exception(
        ENG_ADMIN, "doc_eng", "req_first",
        target_user_id="usr_dave",
        expires_at=T0 + timedelta(seconds=3600),
    )
    clock.advance(3601)
    with pytest.raises(AuthError):
        _authorize(resources, clock, PLAIN, "doc_eng")
    second, created = service.grant_exception(
        ENG_ADMIN, "doc_eng", "req_again",
        target_user_id="usr_dave",
        expires_at=T0 + timedelta(days=365),
    )
    assert created is False
    assert second.id == first.id
    _authorize(resources, clock, PLAIN, "doc_eng")
    rows = service.list_exceptions(ADMIN, "doc_eng", "req_list")
    assert len(rows) == 1


def test_FR_RBAC_004_exception_expiry_boundary_is_exclusive() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    service.grant_exception(
        ENG_ADMIN, "doc_eng", "req_grant",
        target_user_id="usr_dave",
        expires_at=T0 + timedelta(seconds=3600),
    )
    clock.advance(3599)
    _authorize(resources, clock, PLAIN, "doc_eng")
    clock.advance(1)
    with pytest.raises(AuthError):
        _authorize(resources, clock, PLAIN, "doc_eng")


def test_FR_RBAC_004_exception_revoke_by_own_dept_admin() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, audits = _seed(clock)
    exception, _ = service.grant_exception(
        ADMIN, "doc_eng", "req_grant", target_user_id="usr_dave",
    )
    _authorize(resources, clock, PLAIN, "doc_eng")
    # A dept admin may revoke even a super-admin grant on their own
    # department's document: revocation only shrinks visibility.
    service.revoke_exception(
        ENG_ADMIN, exception.id, "req_revoke", document_id="doc_eng",
    )
    with pytest.raises(AuthError):
        _authorize(resources, clock, PLAIN, "doc_eng")
    revoked = [
        event for event in _actions(audits)
        if event["action"] == "authz.document_exception_revoked"
    ]
    assert len(revoked) == 1
    assert revoked[0]["metadata"]["dept_id"] == "dept_eng"


def test_FR_RBAC_004_exception_revoke_scope_and_mismatch() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    exception, _ = service.grant_exception(
        ADMIN, "doc_eng", "req_grant", target_user_id="usr_dave",
    )
    with pytest.raises(AuthError) as excinfo:
        service.revoke_exception(
            ART_ADMIN, exception.id, "req_cross",
            document_id="doc_eng",
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        service.revoke_exception(
            ENG_ADMIN, exception.id, "req_mismatch",
            document_id="doc_art",
        )
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        service.revoke_exception(ADMIN, "exc_ghost", "req_ghost")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"


def test_FR_RBAC_004_exception_list_scope_and_permanent_filter() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    service.grant_exception(
        ENG_ADMIN, "doc_eng", "req_perm",
        target_user_id="usr_dave",
    )
    service.grant_exception(
        ENG_ADMIN, "doc_eng", "req_temp",
        target_user_id="usr_erin",
        expires_at=T0 + timedelta(days=30),
    )
    rows = service.list_exceptions(ENG_ADMIN, "doc_eng", "req_list")
    assert len(rows) == 2
    permanent = service.list_exceptions(
        ENG_ADMIN, "doc_eng", "req_perm_list", permanent_only=True,
    )
    assert len(permanent) == 1
    assert permanent[0].target_user_id == "usr_dave"
    assert permanent[0].expires_at is None
    with pytest.raises(AuthError) as excinfo:
        service.list_exceptions(ART_ADMIN, "doc_eng", "req_cross")
    assert _code(excinfo) == "RESOURCE_NOT_FOUND"
    with pytest.raises(AuthError) as excinfo:
        service.list_exceptions(PLAIN, "doc_eng", "req_plain")
    assert _code(excinfo) == "AUTH_FORBIDDEN"


def test_FR_RBAC_004_exception_audit_visible_in_own_dept_view_only() -> None:
    clock = FakeClock(T0)
    service, _, _, _, audits = _seed(clock)
    service.grant_exception(
        ENG_ADMIN, "doc_eng", "req_grant", target_user_id="usr_dave",
    )
    eng_view = audits.list_department_events(
        Actor(user_id="usr_alice", username="alice", role="user"),
        frozenset({"dept_eng"}), "req_view_eng",
    )
    granted = [
        item for item in eng_view["items"]
        if item["action"] == "authz.document_exception_granted"
    ]
    assert len(granted) == 1
    art_view = audits.list_department_events(
        Actor(user_id="usr_carol", username="carol", role="user"),
        frozenset({"dept_art"}), "req_view_art",
    )
    assert all(
        item["action"] != "authz.document_exception_granted"
        for item in art_view["items"]
    )


def test_FR_RBAC_004_exception_grant_then_member_removed_still_visible() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    service.grant_exception(
        ADMIN, "doc_eng", "req_grant", target_user_id="usr_erin",
    )
    service.add_member(ADMIN, "dept_eng", "usr_erin", "reader", "req_join")
    service.remove_member(ADMIN, "dept_eng", "usr_erin", "req_leave")
    _authorize(resources, clock, ERIN, "doc_eng")


def test_FR_RBAC_004_exception_visible_then_revoked_invisible() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    exception, _ = service.grant_exception(
        ADMIN, "doc_art", "req_grant", target_user_id="usr_dave",
    )
    _authorize(resources, clock, PLAIN, "doc_art")
    service.revoke_exception(ADMIN, exception.id, "req_revoke")
    with pytest.raises(AuthError):
        _authorize(resources, clock, PLAIN, "doc_art")


def test_FR_RBAC_004_exception_expired_but_member_still_visible() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    service.grant_exception(
        ADMIN, "doc_eng", "req_grant",
        target_user_id="usr_bob",
        expires_at=T0 + timedelta(seconds=3600),
    )
    clock.advance(3601)
    # Bob is an eng editor: the membership channel survives the
    # exception's expiry.
    _authorize(resources, clock, ENG_EDITOR, "doc_eng")


def test_FR_RBAC_004_exception_expired_and_nonmember_invisible() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    service.grant_exception(
        ADMIN, "doc_eng", "req_grant",
        target_user_id="usr_dave",
        expires_at=T0 + timedelta(seconds=3600),
    )
    clock.advance(3601)
    with pytest.raises(AuthError):
        _authorize(resources, clock, PLAIN, "doc_eng")
