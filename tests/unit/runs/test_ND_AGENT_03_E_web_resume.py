"""ND-AGENT-03-E: Web resume endpoint tests."""

from __future__ import annotations

from pivot.runs.service import RunService


def test_FR_AGENT_007_web_resume_same_run():
    """Resume accepts clarification and returns same run."""
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="请解释考勤制度",
        idempotency_key="idem_1",
        request_id="req_1",
    )
    
    # Simulate waiting state
    bundle.run.state = "waiting_for_user"
    runs.commit(bundle)
    
    # Resume with clarification
    resumed = runs.resume(
        run_id=bundle.run.id,
        clarification_id="clarif_1",
        answer="我想了解迟到扣分规则",
        idempotency_key="idem_resume_1",
        request_id="req_resume_1",
    )
    
    assert resumed.run.id == bundle.run.id
    assert resumed.run.message_id == bundle.run.message_id


def test_FR_AGENT_007_resume_idempotency_same_params():
    """Resume with same idempotency key and params returns same result."""
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="考勤政策",
        idempotency_key="idem_1",
        request_id="req_1",
    )
    
    bundle.run.state = "waiting_for_user"
    runs.commit(bundle)
    
    first = runs.resume(
        run_id=bundle.run.id,
        clarification_id="clarif_1",
        answer="详细说明",
        idempotency_key="idem_resume_1",
        request_id="req_first",
    )
    
    second = runs.resume(
        run_id=bundle.run.id,
        clarification_id="clarif_1",
        answer="详细说明",
        idempotency_key="idem_resume_1",
        request_id="req_second",
    )
    
    assert first.run.id == second.run.id


def test_FR_AGENT_007_resume_idempotency_conflict():
    """Resume with same key but different params raises conflict."""
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="考勤政策",
        idempotency_key="idem_1",
        request_id="req_1",
    )
    
    bundle.run.state = "waiting_for_user"
    runs.commit(bundle)
    
    runs.resume(
        run_id=bundle.run.id,
        clarification_id="clarif_1",
        answer="第一次回答",
        idempotency_key="idem_resume_1",
        request_id="req_first",
    )
    
    try:
        runs.resume(
            run_id=bundle.run.id,
            clarification_id="clarif_1",
            answer="不同的回答",
            idempotency_key="idem_resume_1",
            request_id="req_second",
        )
        assert False, "Expected conflict error"
    except Exception as e:
        from pivot.runs.errors import RunError
        if isinstance(e, RunError):
            assert e.code == "IDEMPOTENCY_CONFLICT"
        else:
            raise
