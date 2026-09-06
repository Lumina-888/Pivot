"""Persistence ports; business state transitions belong to accountable modules."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypeVar

from pivot.db.models import AuditEvent

T = TypeVar("T")


class Repository(Protocol[T]):
    """Minimal aggregate persistence port backed by the PostgreSQL fact source."""

    def add(self, entity: T) -> None: ...

    def get(self, entity_id: str) -> T | None: ...

    def list(self) -> Iterable[T]: ...


class AuditEventRepository(Protocol):
    """Append-only audit port; update/delete are intentionally absent."""

    def append(self, event: AuditEvent) -> None: ...

    def get(self, event_id: str) -> AuditEvent | None: ...

    def list(self) -> Iterable[AuditEvent]: ...
