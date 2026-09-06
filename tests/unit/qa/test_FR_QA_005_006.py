from __future__ import annotations

from fakes import ok_retriever
from pivot.qa.graph import MAX_CLARIFICATIONS
from pivot.qa.orchestrator import ClarifyOnceClassifier, QaOrchestrator
from pivot.runs.service import RunService
from pivot.stream.events import FORBIDDEN_PAYLOAD_KEYS


def test_FR_QA_005_events_do_not_expose_thinking_or_prompts():
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到怎么处理",
        idempotency_key="idem_1",
        request_id="req_1",
    )
    QaOrchestrator(ok_retriever()).execute(bundle, runs.log(bundle.run.id), "req_1")
    for _name, data in runs.log(bundle.run.id).replay():
        assert FORBIDDEN_PAYLOAD_KEYS.isdisjoint(data["payload"])
        assert "system" not in data["payload"]
        assert "thinking" not in str(data["payload"]).lower()


def test_FR_QA_006_only_one_clarification_round():
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到？",
        idempotency_key="idem_1",
        request_id="req_1",
    )
    orch = QaOrchestrator(ok_retriever(), classifier=ClarifyOnceClassifier())
    orch.execute(bundle, runs.log(bundle.run.id), "req_1")
    assert bundle.run.state == "waiting_for_user"
    assert bundle.run.clarification_count == MAX_CLARIFICATIONS
    orch.resume(bundle, runs.log(bundle.run.id), "考勤制度", "req_2")
    assert bundle.run.state == "answered"
    assert bundle.run.clarification_count == 1
