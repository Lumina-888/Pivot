"""In-memory repository for deterministic tests only.

This implementation is deliberately not a business fact store. Production
callers must use the SQLAlchemy session backed by PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Generic, TypeVar

T = TypeVar("T")


class MemoryRepository(Generic[T]):
    """Small repository fake with the same read/write shape as Repository."""

    def __init__(self) -> None:
        self._items: dict[str, T] = {}

    def add(self, entity: T) -> None:
        entity_id = getattr(entity, "id", None)
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError("repository entities require a non-empty string id")
        if entity_id in self._items:
            raise ValueError(f"duplicate entity id: {entity_id}")
        self._items[entity_id] = entity

    def get(self, entity_id: str) -> T | None:
        return self._items.get(entity_id)

    def list(self) -> Iterable[T]:
        return tuple(self._items.values())


class MemoryAuditEventRepository(MemoryRepository[T]):
    """Append-only test repository; it intentionally has no update/delete API."""

    def append(self, event: T) -> None:
        self.add(event)
