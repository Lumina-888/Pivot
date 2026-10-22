"""ND-GAP-02: tiered audit write-failure policy (Owner decision 2026-10-22)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pivot.audit.policy import AuditWriteFailures, TieredAuditSink, is_critical_action
from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.documents.ports import AuditDraft


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 10, 22, 3, 0, tzinfo=UTC)


class _FailingStore(AppendOnlyAuditStore):
    def append(self, event) -> None:
        raise RuntimeError("audit store down")


class _FailingSink:
    def emit(self, event) -> None:
        raise RuntimeError("audit store down")


def test_FR_AUDIT_002_critical_action_classification():
    assert is_critical_action("auth.login")
    assert is_critical_action("login")  # alias canonicalizes to auth.login
    assert is_critical_action("auth.role_change")
    assert is_critical_action("authz.permission_change")
    assert is_critical_action("export.create")
    assert is_critical_action("export.download")
    assert is_critical_action("document.delete")
    assert not is_critical_action("qa.run")
    assert not is_critical_action("document.upload")
    assert not is_critical_action("document.retry")


def test_FR_AUDIT_002_critical_audit_failure_fails_closed():
    failures = AuditWriteFailures()
    service = AuditService(_FailingStore(), _Clock(), failures=failures)
    with pytest.raises(RuntimeError):
        service.record(
            actor="usr_admin",
            action="export.create",
            target="exp_1",
            result="ok",
            request_id="req_1",
        )
    assert failures.count == 0


def test_FR_AUDIT_002_general_audit_failure_is_counted_not_silent():
    failures = AuditWriteFailures()
    service = AuditService(_FailingStore(), _Clock(), failures=failures)
    event = service.record(
        actor="usr_alice",
        action="qa.run",
        target="run_1",
        result="ok",
        request_id="req_2",
        run_id="run_1",
    )
    assert event.action == "qa.run"
    assert failures.count == 1


def test_FR_AUDIT_002_tiered_sink_propagates_critical_and_counts_general():
    failures = AuditWriteFailures()
    sink = TieredAuditSink(_FailingSink(), failures)
    with pytest.raises(RuntimeError):
        sink.emit(
            AuditDraft(
                actor="usr_alice",
                action="document.delete",
                target="doc_1",
                result="ok",
                request_id="req_1",
            )
        )
    sink.emit(
        AuditDraft(
            actor="usr_alice",
            action="document.upload",
            target="doc_1",
            result="ok",
            request_id="req_2",
        )
    )
    assert failures.count == 1
