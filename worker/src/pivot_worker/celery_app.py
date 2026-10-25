"""Celery ingest adapter. Broker URL and concurrency are injected, not frozen."""

from __future__ import annotations

import logging
from typing import Any, Callable

from celery import Celery

from pivot_worker.queue import IngestRunner
from pivot_worker.settings import WorkerSettings

logger = logging.getLogger(__name__)


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
    def app(self) -> Celery:
        return self._app

    @property
    def task_queue(self) -> str:
        queue = getattr(self._task, "queue", None)
        return str(queue or self.parse_queue)

    def __call__(self, version_id: str, request_id: str, actor_id: str) -> Any:
        result = self._task.delay(version_id, request_id, actor_id)
        if self._app.conf.task_always_eager:
            return result.get()
        return result


class CeleryClaimSyncSubmitter:
    """Dispatch a post-claim vector reconcile as a worker task (ADR-017 D3).

    Mirrors CeleryIngestSubmitter: the API side only delays the task by
    name; the worker process registers the same task name with its own
    sync callable, so the API-side closure never executes in broker
    mode. Workers listen on the parse queue only, so the reconcile task
    rides that queue too.

    ``sync`` must raise on failure: the task retries a bounded number
    of times, and on exhaustion writes ``authz.library.sync_failed``
    (metadata ``dept_id`` is the claimed-to library, so the target
    department's admins see it in their audit view) and, in broker
    mode, re-raises so celery also marks the task failed. In eager
    mode the task returns after auditing instead: the failure is
    already on record, and the dispatch must not fail the claim.
    ``audit`` is a record callable with AuditService.record's keyword
    shape.

    Dispatch never fails the claim: the claim is already committed
    when this runs. In eager mode the task body still retries and
    audits, but ``__call__`` swallows the final raise; in broker mode
    a dispatch failure (broker down, task never ran) audits directly
    for the same reason — a lost sync must stay visible to admins.
    """

    def __init__(
        self,
        sync: Callable[[str], None],
        *,
        audit: Callable[..., Any],
        parse_queue: str,
        online_queue: str,
        concurrency: int,
        broker_url: str | None,
        always_eager: bool = False,
        app: Celery | None = None,
        max_retries: int = 3,
        retry_backoff_seconds: int = 60,
    ) -> None:
        self._sync = sync
        self._audit = audit
        self._max_retries = max_retries
        self._backoff = retry_backoff_seconds
        self.parse_queue = parse_queue
        self.online_queue = online_queue
        self._app = app or build_ingest_celery(
            parse_queue=parse_queue,
            online_queue=online_queue,
            concurrency=concurrency,
            broker_url=broker_url,
            always_eager=always_eager,
        )

        @self._app.task(
            name="pivot.reconcile_claimed_document",
            queue=parse_queue,
            bind=True,
            max_retries=max_retries,
        )
        def reconcile_claimed_document(
            task_self, document_id: str, library_id: str,
            request_id: str, actor_id: str,
        ) -> None:
            if task_self.app.conf.task_always_eager:
                # Eager mode runs inline and does not re-execute
                # self.retry(): the Retry exception would just
                # propagate out of .delay(). Loop here for the same
                # bounded attempt count, audit the exhaustion, and
                # return: the failure is already on record in the
                # audit event, and the dispatch must not fail the
                # already-committed claim. (Broker mode below still
                # re-raises so celery marks the task failed.)
                for _attempt in range(max_retries + 1):
                    try:
                        sync(document_id)
                        return
                    except Exception:
                        pass
                try:
                    audit(
                        actor=actor_id,
                        action="authz.library.sync_failed",
                        target=document_id,
                        result="failed",
                        request_id=request_id,
                        metadata={
                            "dept_id": library_id,
                            "from_library": "unassigned",
                            "to_library": library_id,
                            "attempts": max_retries + 1,
                        },
                    )
                except Exception:
                    logger.exception(
                        "claim sync audit failed for document %s",
                        document_id,
                    )
                logger.exception(
                    "claim sync failed after retries for document %s",
                    document_id,
                )
                return
            try:
                sync(document_id)
            except Exception as exc:
                if task_self.request.retries >= max_retries:
                    try:
                        audit(
                            actor=actor_id,
                            action="authz.library.sync_failed",
                            target=document_id,
                            result="failed",
                            request_id=request_id,
                            metadata={
                                "dept_id": library_id,
                                "from_library": "unassigned",
                                "to_library": library_id,
                                "attempts": task_self.request.retries + 1,
                            },
                        )
                    except Exception:
                        logger.exception(
                            "claim sync audit failed for document %s",
                            document_id,
                        )
                    raise
                logger.warning(
                    "claim sync failed for document %s, retry %d/%d",
                    document_id, task_self.request.retries + 1, max_retries,
                )
                raise task_self.retry(exc=exc, countdown=retry_backoff_seconds)

        self._task = reconcile_claimed_document

    @property
    def app(self) -> Celery:
        return self._app

    @property
    def task_queue(self) -> str:
        queue = getattr(self._task, "queue", None)
        return str(queue or self.parse_queue)

    def __call__(
        self, document_id: str, library_id: str, request_id: str, actor_id: str
    ) -> Any:
        try:
            result = self._task.delay(document_id, library_id, request_id, actor_id)
        except Exception:
            # Dispatch itself failed: the task never ran, so audit here
            # — otherwise the lost sync would be invisible to admins.
            try:
                self._audit(
                    actor=actor_id,
                    action="authz.library.sync_failed",
                    target=document_id,
                    result="failed",
                    request_id=request_id,
                    metadata={
                        "dept_id": library_id,
                        "from_library": "unassigned",
                        "to_library": library_id,
                    },
                )
            except Exception:
                logger.exception(
                    "claim sync dispatch audit failed for document %s", document_id
                )
            logger.exception(
                "claim sync dispatch failed for document %s", document_id
            )
            return None
        if self._app.conf.task_always_eager:
            try:
                return result.get()
            except Exception:
                # Eager mode runs the task inline; its final failure is
                # already audited by the task body. The claim itself
                # succeeded, so the dispatch must not fail the request.
                logger.exception(
                    "claim sync failed after retries for document %s", document_id
                )
                return None
        return result


def worker_listen_queues(parse_queue: str, online_queue: str) -> tuple[str, ...]:
    if not parse_queue.strip() or not online_queue.strip():
        raise RuntimeError("parse and online queues are required")
    if parse_queue == online_queue:
        raise RuntimeError("parse and online queues must be isolated")
    return (parse_queue,)


def _unassembled_runner(version_id: str, request_id: str, actor_id: str) -> None:
    raise RuntimeError(
        "ingest runner is not assembled; object bytes still require a shared ObjectStore"
    )


def start_celery_worker(
    settings: WorkerSettings,
    runner: IngestRunner | None = None,
    *,
    claim_sync: Callable[[str], None] | None = None,
    claim_sync_audit: Callable[..., Any] | None = None,
    block: bool = True,
) -> CeleryIngestSubmitter:
    submitter = CeleryIngestSubmitter(
        runner or _unassembled_runner,
        parse_queue=settings.parse_queue,
        online_queue=settings.online_queue,
        concurrency=settings.concurrency,
        broker_url=settings.celery_broker,
        always_eager=False,
    )
    if claim_sync is not None and claim_sync_audit is not None:
        # Same app, so the worker that consumes ingest also consumes
        # claim reconciles; a separate app would register a task no
        # worker ever picks up.
        CeleryClaimSyncSubmitter(
            claim_sync,
            audit=claim_sync_audit,
            parse_queue=settings.parse_queue,
            online_queue=settings.online_queue,
            concurrency=settings.concurrency,
            broker_url=settings.celery_broker,
            always_eager=False,
            app=submitter.app,
        )
    if not block:
        return submitter
    queues = worker_listen_queues(settings.parse_queue, settings.online_queue)
    submitter.app.worker_main(
        [
            "worker",
            f"--queues={queues[0]}",
            f"--concurrency={settings.concurrency}",
        ]
    )
    return submitter
