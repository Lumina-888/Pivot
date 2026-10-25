"""S2: temporary grants for FR-RBAC-004 (ADR-017 D2, Q1, Q3).

Read-time expiry: visible_libraries and admin_departments exclude
expired memberships, effective on the next request with no sweeper.
Renewal goes through the role-change path and writes a renewal audit
event; after expiry a row is purged on department-member reads, so
renewal is refused and only a fresh grant works. The 60-day cap binds
only the project-lead level (Q1): it does not exist until P1-4, so
department admins granting long-term memberships must stay unlimited.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeClock, InMemoryResources as FakeResources
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.departments import (
    DepartmentAdminService,
    _check_grant_expiry,
)
from pivot.auth.errors import AuthError
from pivot.auth.ports import Library, Membership, Principal, UserAccount
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
PLAIN = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)

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
    }
    users = InMemoryUserDirectory(
        [
            UserAccount(
                id="usr_admin", username="admin", password_hash="x",
                role="admin", status="active", token_version=1,
            ),
            UserAccount(
                id="usr_alice", username="alice", password_hash="x",
                role="user", status="active", token_version=1,
            ),
            UserAccount(
                id="usr_bob", username="bob", password_hash="x",
                role="user", status="active", token_version=1,
            ),
            UserAccount(
                id="usr_dave", username="dave", password_hash="x",
                role="user", status="active", token_version=1,
            ),
        ]
    )
    documents = MemoryDocuments()
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


def test_FR_RBAC_004_expiry_visible_before_deadline_invisible_at_it() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    access = AccessControl(resources, clock=clock)
    deadline = T0 + timedelta(seconds=10)
    service.add_member(
        ADMIN, "dept_eng", "usr_dave", "reader", "req_tmp",
        expires_at=deadline,
    )
    dave = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
    assert "dept_eng" in access.visible_libraries(dave)
    clock.advance(9)
    assert "dept_eng" in access.visible_libraries(dave)
    clock.advance(1)
    assert "dept_eng" not in access.visible_libraries(dave)
    clock.advance(1)
    assert "dept_eng" not in access.visible_libraries(dave)


def test_FR_RBAC_004_expiry_department_admin_loses_scope_next_request() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    access = AccessControl(resources, clock=clock)
    service.add_member(
        ADMIN, "dept_eng", "usr_dave", "dept_admin", "req_tmp_admin",
        expires_at=T0 + timedelta(seconds=10),
    )
    dave = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)
    assert access.is_department_admin(dave, "dept_eng")
    clock.advance(11)
    assert not access.is_department_admin(dave, "dept_eng")
    assert access.admin_departments(dave) == frozenset()
    with pytest.raises(AuthError):
        service.add_member(
            dave, "dept_eng", "usr_bob", "reader", "req_denied"
        )


def test_FR_RBAC_004_expiry_add_member_stores_expiry_or_long_term() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    deadline = T0 + timedelta(days=30)
    member, created = service.add_member(
        ADMIN, "dept_eng", "usr_dave", "reader", "req_tmp",
        expires_at=deadline,
    )
    assert created
    assert member.expires_at == deadline
    stored = resources.get_department_members("dept_eng")
    assert next(m for m in stored if m.user_id == "usr_dave").expires_at == deadline
    plain, _ = service.add_member(
        ADMIN, "dept_eng", "usr_dave", "reader", "req_dup"
    )
    assert plain.expires_at == deadline


def test_FR_RBAC_004_expiry_role_change_keeps_expiry_when_omitted() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    deadline = T0 + timedelta(days=30)
    service.add_member(
        ADMIN, "dept_eng", "usr_dave", "reader", "req_tmp",
        expires_at=deadline,
    )
    updated = service.set_member_role(
        ADMIN, "dept_eng", "usr_dave", "editor", "req_role"
    )
    assert updated.expires_at == deadline


def test_FR_RBAC_004_expiry_role_change_clears_expiry_when_none() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    service.add_member(
        ADMIN, "dept_eng", "usr_dave", "reader", "req_tmp",
        expires_at=T0 + timedelta(days=30),
    )
    updated = service.set_member_role(
        ADMIN, "dept_eng", "usr_dave", "editor", "req_clear",
        expires_at=None,
    )
    assert updated.expires_at is None


def test_FR_RBAC_004_expiry_renewal_writes_renewal_event() -> None:
    clock = FakeClock(T0)
    service, _, _, _, audits = _seed(clock)
    old = T0 + timedelta(days=30)
    new = T0 + timedelta(days=60)
    service.add_member(
        ADMIN, "dept_eng", "usr_dave", "reader", "req_tmp", expires_at=old
    )
    service.set_member_role(
        ADMIN, "dept_eng", "usr_dave", "reader", "req_renew",
        expires_at=new,
    )
    actions = _actions(audits)
    renewals = [e for e in actions if e["action"] == "authz.permission_renewed"]
    assert len(renewals) == 1
    assert renewals[0]["metadata"]["old_expires_at"] == "2026-11-24T08:00:00Z"
    assert renewals[0]["metadata"]["new_expires_at"] == "2026-12-24T08:00:00Z"
    assert renewals[0]["metadata"]["dept_id"] == "dept_eng"


def test_FR_RBAC_004_expiry_shortening_and_restriction_are_not_renewal() -> None:
    clock = FakeClock(T0)
    service, _, _, _, audits = _seed(clock)
    service.add_member(
        ADMIN, "dept_eng", "usr_dave", "reader", "req_tmp",
        expires_at=T0 + timedelta(days=30),
    )
    service.set_member_role(
        ADMIN, "dept_eng", "usr_dave", "reader", "req_shorten",
        expires_at=T0 + timedelta(days=10),
    )
    assert not [e for e in _actions(audits) if e["action"] == "authz.permission_renewed"]
    service.set_member_role(
        ADMIN, "dept_eng", "usr_dave", "reader", "req_to_permanent",
        expires_at=None,
    )
    renewals = [e for e in _actions(audits) if e["action"] == "authz.permission_renewed"]
    assert len(renewals) == 1
    assert renewals[0]["metadata"]["new_expires_at"] is None
    service.set_member_role(
        ADMIN, "dept_eng", "usr_bob", "editor", "req_restrict",
        expires_at=T0 + timedelta(days=30),
    )
    assert len([e for e in _actions(audits) if e["action"] == "authz.permission_renewed"]) == 1


def test_FR_RBAC_004_expiry_renewal_after_expiry_refused_regrant_works() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    service.add_member(
        ADMIN, "dept_eng", "usr_dave", "reader", "req_tmp",
        expires_at=T0 + timedelta(seconds=10),
    )
    clock.advance(11)
    with pytest.raises(AuthError):
        service.set_member_role(
            ADMIN, "dept_eng", "usr_dave", "editor", "req_late_renew",
            expires_at=T0 + timedelta(days=30),
        )
    member, created = service.add_member(
        ADMIN, "dept_eng", "usr_dave", "editor", "req_regrant",
        expires_at=T0 + timedelta(days=30),
    )
    assert created
    assert member.expires_at == T0 + timedelta(days=30)


def test_FR_RBAC_004_expiry_department_admin_long_term_unlimited() -> None:
    clock = FakeClock(T0)
    service, _, _, _, _ = _seed(clock)
    member, created = service.add_member(
        ENG_ADMIN, "dept_eng", "usr_dave", "reader", "req_long",
        expires_at=T0 + timedelta(days=3650),
    )
    assert created
    assert member.expires_at == T0 + timedelta(days=3650)
    renewed = service.set_member_role(
        ENG_ADMIN, "dept_eng", "usr_dave", "reader", "req_long_renew",
        expires_at=T0 + timedelta(days=3650),
    )
    assert renewed.expires_at == T0 + timedelta(days=3650)


def test_FR_RBAC_004_expiry_project_lead_cap_sixty_days() -> None:
    now = T0
    _check_grant_expiry("project_lead", now + timedelta(days=60), now)
    _check_grant_expiry("admin", now + timedelta(days=3650), now)
    _check_grant_expiry("dept_admin", now + timedelta(days=3650), now)
    with pytest.raises(ValueError):
        _check_grant_expiry("project_lead", None, now)
    with pytest.raises(ValueError):
        _check_grant_expiry("project_lead", now + timedelta(days=61), now)


def test_FR_RBAC_004_expiry_purge_on_department_members_not_on_memberships() -> None:
    clock = FakeClock(T0)
    service, resources, _, _, _ = _seed(clock)
    service.add_member(
        ADMIN, "dept_eng", "usr_dave", "reader", "req_tmp",
        expires_at=T0 + timedelta(seconds=10),
    )
    clock.advance(11)
    raw_before = resources.get_memberships("usr_dave")
    assert [m for m in raw_before if m.user_id == "usr_dave"]
    members = resources.get_department_members("dept_eng")
    assert not [m for m in members if m.user_id == "usr_dave"]
    assert [m for m in members if m.user_id == "usr_alice"]
    assert resources.get_memberships("usr_dave") == ()


def test_FR_RBAC_004_expiry_fake_catalog_purges_on_department_members() -> None:
    catalog = FakeResources()
    catalog.memberships = {
        "usr_dave": (
            Membership(
                user_id="usr_dave", dept_id="dept_eng", dept_role="reader",
                granted_by="usr_admin",
                expires_at=datetime(2020, 1, 1, tzinfo=UTC),
            ),
        ),
    }
    assert catalog.get_department_members("dept_eng") == ()
    assert catalog.get_memberships("usr_dave") == ()
