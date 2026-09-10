"""Consume the parse queue only. Online tasks stay on a separate queue."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class QueuePort(Protocol):
    def dequeue(self, queue: str) -> Mapping[str, Any] | None: ...


class IngestRunner(Protocol):
    def __call__(self, version_id: str, request_id: str, actor_id: str) -> Any: ...


class IngestQueueConsumer:
    def __init__(
        self,
        queue: QueuePort,
        runner: IngestRunner,
        *,
        parse_queue: str,
        online_queue: str,
        concurrency: int,
    ) -> None:
        if not parse_queue.strip() or not online_queue.strip():
            raise ValueError("parse and online queues are required")
        if parse_queue == online_queue:
            raise ValueError("parse and online queues must be isolated")
        if concurrency < 1:
            raise ValueError("worker concurrency must be a positive integer")
        self._queue = queue
        self._runner = runner
        self._parse_queue = parse_queue
        self._online_queue = online_queue
        self.concurrency = concurrency

    def consume_once(self) -> Any | None:
        payload = self._queue.dequeue(self._parse_queue)
        if payload is None:
            return None
        try:
            version_id = str(payload["version_id"])
            request_id = str(payload["request_id"])
            actor_id = str(payload["actor_id"])
        except KeyError as exc:
            raise ValueError("ingest queue payload is missing required fields") from exc
        return self._runner(version_id, request_id, actor_id)
