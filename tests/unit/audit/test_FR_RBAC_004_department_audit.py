"""Department-scoped audit listing for FR-RBAC-004 (ADR-016 D10).

Department admins see only their own department's audit events;
global admins keep the unfiltered view; everyone else is refused.
Events without a department scope never appear in a department view.
"""

from __future__ import annotations

import pytest
from pivot.audit.errors import AuditError
from pivot.audit.ports import Actor
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.http.memory import UtcClock

DEPT_ADMIN = Actor(user_id="usr_alice", username="alice", role="user", status="active")
INACTIVE = Actor(user_id="usr_ghost", username="ghost", role="user", status="disabled")


def _service_with_events() -> AuditService:
    service = AuditService(AppendOnlyAuditStore(), UtcClock())
    service.record(
        actor="usr_admin", action="authz.permission_change", target="usr_bob",
        result="ok", request_id="req_1",
        metadata={"dept_id": "dept_eng", "dept_role": "editor"},
    )
    service.record(
        actor="usr_alice", action="authz.permission_change", target="usr_dave",
        result="ok", request_id="req_2",
        metadata={"dept_id": "dept_eng", "dept_role": "reader"},
    )
    service.record(
        actor="usr_admin", action="authz.permission_change", target="usr_erin",
        result="ok", request_id="req_3",
        metadata={"dept_id": "dept_art", "dept_role": "editor"},
    )
    service.record(
        actor="usr_alice", action="qa.run", target="run_1",
        result="ok", request_id="req_4", metadata={},
    )
    return service


def test_FR_RBAC_004_department_admin_lists_only_own_department_events():
    service = _service_with_events()
    listed = service.list_department_events(
        DEPT_ADMIN, frozenset({"dept_eng"}), "req_list"
    )
    items = listed["items"]
    assert len(items) == 2
    assert all(item["metadata"]["dept_id"] == "dept_eng" for item in items)
    assert listed["pagination"] is None


def test_FR_RBAC_004_department_audit_listing_respects_actor_and_action_filters():
    service = _service_with_events()
    by_actor = service.list_department_events(
        DEPT_ADMIN, frozenset({"dept_eng"}), "req_list",
        filter_actor="usr_alice",
    )
    assert len(by_actor["items"]) == 1
    assert by_actor["items"][0]["actor"] == "usr_alice"
    by_action = service.list_department_events(
        DEPT_ADMIN, frozenset({"dept_eng"}), "req_list",
        filter_action="qa.run",
    )
    assert by_action["items"] == []


def test_FR_RBAC_004_department_audit_listing_refuses_empty_scope_or_inactive():
    service = _service_with_events()
    with pytest.raises(AuditError) as empty:
        service.list_department_events(DEPT_ADMIN, frozenset(), "req_list")
    assert empty.value.code == "AUTH_FORBIDDEN"
    with pytest.raises(AuditError) as inactive:
        service.list_department_events(INACTIVE, frozenset({"dept_eng"}), "req_list")
    assert inactive.value.code == "AUTH_FORBIDDEN"


def test_FR_RBAC_004_department_audit_listing_records_its_own_access():
    service = _service_with_events()
    service.list_department_events(DEPT_ADMIN, frozenset({"dept_eng"}), "req_list")
    events = service.events()
    access = [event for event in events if event.action == "admin.debug_access"]
    assert len(access) == 1
    assert access[0].metadata["department_ids"] == ["dept_eng"]
