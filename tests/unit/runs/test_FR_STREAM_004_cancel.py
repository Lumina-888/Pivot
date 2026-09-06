from __future__ import annotations

from fakes import ok_retriever
from pivot.qa.orchestrator import QaOrchestrator
from pivot.runs.machine import is_terminal
from pivot.runs.service import RunService


def test_FR_STREAM_004_cancel_is_idempotent_and_does_not_rewrite_terminal():
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到怎么处理",
        idempotency_key="idem_1",
        request_id="req_1",
    )
    first = runs.cancel(bundle.run.id, "req_c1")
    second = runs.cancel(bundle.run.id, "req_c2")
    assert first.run.state == "cancelled"
    assert second.run.state == "cancelled"
    events = [name for name, _ in runs.log(bundle.run.id).replay()]
    assert events.count("cancelled") == 1
    QaOrchestrator(ok_retriever()).execute(bundle, runs.log(bundle.run.id), "req_run")
    assert is_terminal(bundle.run.state)
    assert bundle.run.state == "cancelled"
