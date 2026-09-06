"""Duck-typed AuditSink compatible with M01 AuditEventDraft (FR-AUDIT-001)."""

from __future__ import annotations

from typing import Any

from pivot.audit.service import AuditService


class AuditLogSink:
    def __init__(self, service: AuditService) -> None:
        self._service = service

    def emit(self, event: Any) -> None:
        metadata = dict(getattr(event, "metadata", None) or {})
        self._service.record(
            actor=event.actor,
            action=event.action,
            target=event.target,
            result=event.result,
            request_id=event.request_id,
            metadata=metadata,
            run_id=getattr(event, "run_id", None),
        )
