from __future__ import annotations

from fakes import ok_retriever
from pivot.qa.graph import STAGES
from pivot.qa.orchestrator import QaOrchestrator
from pivot.runs.service import RunService


def test_FR_QA_001_runs_controlled_graph_and_answers():
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到怎么处理",
        idempotency_key="idem_1",
        request_id="req_1",
    )
    QaOrchestrator(ok_retriever()).execute(bundle, runs.log(bundle.run.id), "req_1")
    stages = [
        data["payload"].get("stage")
        for name, data in runs.log(bundle.run.id).replay()
        if name == "stage"
    ]
    for required in STAGES:
        assert required in stages
    assert bundle.run.state == "answered"
    assert bundle.run.answer_markdown
    events = [name for name, _ in runs.log(bundle.run.id).replay()]
    assert events[0] == "run_started"
    assert events[-1] == "completed"
