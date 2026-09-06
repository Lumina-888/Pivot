from __future__ import annotations

from fakes import ok_retriever
from pivot.qa.orchestrator import QaOrchestrator
from pivot.qa.verifier import FailingVerifier
from pivot.runs.service import RunService


def test_FR_QA_004_verifier_failure_does_not_default_to_answered():
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到怎么处理",
        idempotency_key="idem_1",
        request_id="req_1",
    )
    QaOrchestrator(ok_retriever(), verifier=FailingVerifier()).execute(
        bundle, runs.log(bundle.run.id), "req_1"
    )
    assert bundle.run.state == "uncertain"
    assert bundle.run.error_code == "VERIFICATION_UNAVAILABLE"
    assert bundle.run.state != "answered"
    assert runs.log(bundle.run.id).terminal == "uncertain"
