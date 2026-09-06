"""Vendor-neutral storage ports.

PostgreSQL remains the business fact source. These queue/cache ports represent
rebuildable or short-lived state only; Redis must never be the sole fact store.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class ObjectStore(Protocol):
    """Object storage for originals, intermediates and exports."""

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def presign(self, key: str, *, expires_seconds: int) -> str: ...


@runtime_checkable
class VectorStore(Protocol):
    """Rebuildable vector index; payload must trace to PG facts."""

    def upsert(self, points: Iterable[Mapping]) -> None: ...
    def search(
        self, vector: Iterable[float], *, limit: int, filters: Mapping | None = None
    ) -> list[Mapping]: ...
    def delete(self, *, version_id: str | None = None, chunk_id: str | None = None) -> None: ...


@runtime_checkable
class QueueStore(Protocol):
    """Short-lived task queue; queue loss must not lose business facts."""

    def enqueue(self, queue: str, payload: Mapping) -> str: ...
    def dequeue(self, queue: str) -> Mapping | None: ...


@runtime_checkable
class CacheStore(Protocol):
    """Short-term cache/rate-limit state; not a business fact store."""

    def get(self, key: str) -> bytes | None: ...
    def set(self, key: str, value: bytes, *, ttl_seconds: int) -> None: ...
    def delete(self, key: str) -> None: ...
