"""S5: claim-sync submitter for FR-RBAC-004 (ADR-017 D3).

The submitter mirrors the ingest submitter: a celery task with bounded
retries, a final-failure audit event (authz.library.sync_failed, routed
to the claimed-to department's audit view by metadata dept_id), and a
dispatch that never fails the already-committed claim. Eager mode runs
the task inline, so these tests need no broker.
"""

from __future__ import annotations

from pivot_worker.celery_app import CeleryClaimSyncSubmitter


class _AuditCapture:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def __call__(self, **kwargs) -> None:
        self.events.append(kwargs)


def _submitter(sync, audit, *, max_retries: int = 2) -> CeleryClaimSyncSubmitter:
    return CeleryClaimSyncSubmitter(
        sync,
        audit=audit,
        parse_queue="parse",
        online_queue="online",
        concurrency=1,
        broker_url="memory://",
        always_eager=True,
        max_retries=max_retries,
    )


def test_FR_RBAC_004_claim_sync_success_writes_no_event() -> None:
    calls: list[str] = []
    audit = _AuditCapture()
    submitter = _submitter(calls.append, audit)
    submitter("doc_x", "dept_eng", "req_claim", "usr_admin")
    assert calls == ["doc_x"]
    assert audit.events == []


def test_FR_RBAC_004_claim_sync_failure_retries_then_audits() -> None:
    calls: list[str] = []
    audit = _AuditCapture()

    def _always_fail(document_id: str) -> None:
        calls.append(document_id)
        raise RuntimeError("qdrant down")

    submitter = _submitter(_always_fail, audit, max_retries=2)
    # Dispatch must not fail the claim: the task body already audited.
    submitter("doc_x", "dept_eng", "req_claim", "usr_admin")
    assert calls == ["doc_x", "doc_x", "doc_x"]
    assert len(audit.events) == 1
    event = audit.events[0]
    assert event["action"] == "authz.library.sync_failed"
    assert event["target"] == "doc_x"
    assert event["metadata"]["dept_id"] == "dept_eng"
    assert event["metadata"]["to_library"] == "dept_eng"
    assert event["metadata"]["attempts"] == 3


def test_FR_RBAC_004_claim_sync_dispatch_failure_audits() -> None:
    calls: list[str] = []
    audit = _AuditCapture()
    submitter = _submitter(calls.append, audit)

    def _broken_delay(*args, **kwargs):
        raise RuntimeError("broker down")

    submitter._task.delay = _broken_delay  # noqa: SLF001 - test seam
    assert submitter("doc_x", "dept_eng", "req_claim", "usr_admin") is None
    assert calls == []
    assert len(audit.events) == 1
    assert audit.events[0]["action"] == "authz.library.sync_failed"
    assert audit.events[0]["metadata"]["dept_id"] == "dept_eng"


def test_FR_RBAC_004_claim_sync_task_rides_parse_queue() -> None:
    submitter = _submitter(lambda document_id: None, _AuditCapture())
    assert submitter.task_queue == "parse"
