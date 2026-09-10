"""Celery ingest adapter. Broker URL and concurrency are injected, not frozen."""

from __future__ import annotations

from typing import Any

from celery import Celery

from pivot_worker.queue import IngestRunner


def build_ingest_celery(
    *,
    parse_queue: str,
    online_queue: str,
    concurrency: int,
    broker_url: str | None,
    always_eager: bool = False,
) -> Celery:
    if not parse_queue.strip() or not online_queue.strip():
        raise RuntimeError("parse and online queues are required")
    if parse_queue == online_queue:
        raise RuntimeError("parse and online queues must be isolated")
    if concurrency < 1:
        raise RuntimeError("worker concurrency must be a positive integer")
    broker = (broker_url or "").strip()
    if not broker:
        raise RuntimeError("PIVOT_CELERY_BROKER is required when PIVOT_INGEST=celery")
    app = Celery("pivot.ingest")
    app.conf.update(
        broker_url=broker,
        task_always_eager=always_eager,
        task_eager_propagates=True,
        task_ignore_result=False,
        task_default_queue=parse_queue,
        worker_concurrency=concurrency,
        task_create_missing_queues=True,
    )
    return app


class CeleryIngestSubmitter:
    def __init__(
        self,
        runner: IngestRunner,
        *,
        parse_queue: str,
        online_queue: str,
        concurrency: int,
        broker_url: str | None,
        always_eager: bool = False,
        app: Celery | None = None,
    ) -> None:
        self._runner = runner
        self.parse_queue = parse_queue
        self.online_queue = online_queue
        self._app = app or build_ingest_celery(
            parse_queue=parse_queue,
            online_queue=online_queue,
            concurrency=concurrency,
            broker_url=broker_url,
            always_eager=always_eager,
        )

        @self._app.task(name="pivot.ingest_document", queue=parse_queue)
        def ingest_document(version_id: str, request_id: str, actor_id: str) -> Any:
            return runner(version_id, request_id, actor_id)

        self._task = ingest_document

    @property
    def task_queue(self) -> str:
        queue = getattr(self._task, "queue", None)
        return str(queue or self.parse_queue)

    def __call__(self, version_id: str, request_id: str, actor_id: str) -> Any:
        result = self._task.delay(version_id, request_id, actor_id)
        if self._app.conf.task_always_eager:
            return result.get()
        return result
