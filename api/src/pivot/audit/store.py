"""Append-only audit collection (FR-AUDIT-002). Production persists via M03."""

from __future__ import annotations

from collections.abc import Iterable

from pivot.audit.errors import append_only
from pivot.audit.models import AuditEventRecord


class AppendOnlyAuditStore:
    """In-memory append-only log. update/delete APIs are intentionally absent."""

    def __init__(self) -> None:
        self._items: dict[str, AuditEventRecord] = {}
        self._order: list[str] = []

    def append(self, event: AuditEventRecord) -> None:
        if event.id in self._items:
            raise append_only(event.request_id or "req_audit")
        self._items[event.id] = event
        self._order.append(event.id)

    def get(self, event_id: str) -> AuditEventRecord | None:
        return self._items.get(event_id)

    def list(self) -> tuple[AuditEventRecord, ...]:
        return tuple(self._items[event_id] for event_id in self._order)

    def query(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        request_id: str | None = None,
        run_id: str | None = None,
    ) -> tuple[AuditEventRecord, ...]:
        events: Iterable[AuditEventRecord] = self.list()
        if actor is not None:
            events = [item for item in events if item.actor == actor]
        if action is not None:
            events = [item for item in events if item.action == action]
        if request_id is not None:
            events = [item for item in events if item.request_id == request_id]
        if run_id is not None:
            events = [item for item in events if item.run_id == run_id]
        return tuple(events)
