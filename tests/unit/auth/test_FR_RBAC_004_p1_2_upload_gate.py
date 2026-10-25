"""S5: upload gate matrix for FR-RBAC-004 (ADR-017 D5).

Super admins, department editors and department admins may upload;
pure readers and users with no membership may not. Expired memberships
are excluded at read time, so an expired editor loses the gate on the
next request. Uploads still land in the unassigned library; the gate is
checked here and in AuthService, never in the visibility check.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeClock
from pivot.auth.errors import AuthError
from pivot.auth.ports import Membership, Principal
from pivot.security.rbac import AccessControl

ADMIN = Principal(user_id="usr_admin", username="admin", role="admin", token_version=1)
EDITOR = Principal(user_id="usr_bob", username="bob", role="user", token_version=1)
DEPT_ADMIN = Principal(user_id="usr_alice", username="alice", role="user", token_version=1)
READER = Principal(user_id="usr_carol", username="carol", role="user", token_version=1)
PLAIN = Principal(user_id="usr_dave", username="dave", role="user", token_version=1)

T0 = datetime(2026, 10, 25, 8, 0, tzinfo=UTC)


def _membership(user_id: str, dept_role: str, *, expires_at=None) -> Membership:
    return Membership(
        user_id=user_id,
        dept_id="dept_eng",
        dept_role=dept_role,
        granted_by="usr_admin",
        granted_at=T0,
        expires_at=expires_at,
    )


def _access(resources, clock: FakeClock) -> AccessControl:
    resources.memberships = {
        "usr_bob": (_membership("usr_bob", "editor"),),
        "usr_alice": (_membership("usr_alice", "dept_admin"),),
        "usr_carol": (_membership("usr_carol", "reader"),),
    }
    return AccessControl(resources, clock=clock)


def test_FR_RBAC_004_upload_gate_allows_admin_editor_dept_admin(
    resources, clock: FakeClock
) -> None:
    access = _access(resources, clock)
    assert access.can_upload(ADMIN) is True
    assert access.can_upload(EDITOR) is True
    assert access.can_upload(DEPT_ADMIN) is True


def test_FR_RBAC_004_upload_gate_denies_reader_and_plain_user(
    resources, clock: FakeClock
) -> None:
    access = _access(resources, clock)
    assert access.can_upload(READER) is False
    assert access.can_upload(PLAIN) is False


def test_FR_RBAC_004_upload_gate_excludes_expired_editor(
    resources
) -> None:
    # The fixture clock sits at 2026-09-06; pin this test's clock at
    # T0 so the expiry below is unambiguously in the past.
    resources.memberships = {
        "usr_bob": (
            _membership("usr_bob", "editor", expires_at=T0 - timedelta(seconds=1)),
        ),
    }
    access = AccessControl(resources, clock=FakeClock(now=T0))
    assert access.can_upload(EDITOR) is False


def test_FR_RBAC_004_require_upload_denies_plain_user_with_audit(
    auth_service, audits
) -> None:
    login = auth_service.login("alice", "correct-password", request_id="req_login")
    principal = auth_service.authenticate(login.access_token)
    # Alice has no membership in this fixture state: denied.
    with pytest.raises(AuthError) as error:
        auth_service.require_upload(principal, path="/api/v1/documents", request_id="req_up")
    assert error.value.code == "AUTH_FORBIDDEN"
    assert any(event.action == "auth.upload_forbidden" for event in audits.events)


def test_FR_RBAC_004_require_upload_allows_editor(
    auth_service, resources
) -> None:
    resources.memberships = {
        "usr_bob": (_membership("usr_bob", "editor"),),
    }
    login = auth_service.login("bob", "bob-password", request_id="req_login")
    principal = auth_service.authenticate(login.access_token)
    auth_service.require_upload(principal, path="/api/v1/documents", request_id="req_up")
