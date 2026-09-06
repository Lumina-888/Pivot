from __future__ import annotations

from dataclasses import dataclass

from pivot.audit.catalog import REQUIRED_ACTIONS
from pivot.observability.audit import AuditLogSink


def test_FR_AUDIT_001_covers_required_event_categories(audit_service, admin):
    assert len(REQUIRED_ACTIONS) >= 13
    for action in REQUIRED_ACTIONS:
        audit_service.record(
            actor="system",
            action=action,
            target="target",
            result="ok",
            request_id="req_seed",
        )
    listed = audit_service.list_events(admin, "req_list")
    actions = {item["action"] for item in listed["items"]}
    missing = set(REQUIRED_ACTIONS) - actions
    assert not missing
    assert "pagination" in listed
    assert listed["pagination"] is None


def test_FR_AUDIT_001_accepts_m01_audit_sink_drafts(audit_service):
    @dataclass(frozen=True)
    class Draft:
        actor: str
        action: str
        target: str
        result: str
        request_id: str
        metadata: dict

    sink = AuditLogSink(audit_service)
    sink.emit(
        Draft(
            actor="usr_alice",
            action="auth.login",
            target="usr_alice",
            result="ok",
            request_id="req_login",
            metadata={"password": "plain-password", "prompt": "SYSTEM_PROMPT"},
        )
    )
    event = audit_service.events()[0]
    assert event.action == "auth.login"
    assert event.metadata["password"] == "[REDACTED]"
    assert event.metadata["prompt"] == "[REDACTED]"


def test_FR_AUDIT_001_export_events_are_recorded(audit_service):
    for action in ("export.create", "export.download", "export.failed", "export.expired"):
        audit_service.record(
            actor="usr_alice",
            action=action,
            target="exp_1",
            result="ok",
            request_id="req_export",
        )
    actions = {event.action for event in audit_service.events()}
    assert {"export.create", "export.download", "export.failed", "export.expired"} <= actions
