"""ND-AGENT-03-D: 一轮澄清与 owner 恢复，不重置预算。"""

from __future__ import annotations

from pivot.qa.agent_graph import AgentState, accept_clarification, resume_clarification


def _state(**budget: int) -> AgentState:
    return {
        "messages": [{"type": "human", "content": "哪个制度"}],
        "run_id": "run-1",
        "principal_id": "owner-1",
        "conversation_id": "conv-1",
        "scope_type": "global",
        "scope_document_id": None,
        "budget_state": {
            "model_calls": budget.get("model_calls", 1),
            "tool_calls": 0,
            "rewrite_count": 0,
            "clarification_count": budget.get("clarification_count", 0),
            "elapsed_seconds": 0.0,
        },
        "evidence_registry_data": {},
        "final_answer": None,
        "clarification": None,
    }  # type: ignore[return-value]


def test_FR_AGENT_007_first_clarification_waits_for_owner():
    waiting = accept_clarification(_state())
    pending = waiting.get("clarification")
    assert pending is not None
    assert pending["status"] == "waiting_for_user"
    assert waiting["budget_state"]["clarification_count"] == 1
    assert waiting["budget_state"]["model_calls"] == 1


def test_FR_AGENT_007_second_clarification_rejected():
    waiting = accept_clarification(_state())
    second = accept_clarification(waiting)
    answer = second["final_answer"]
    assert answer is not None
    assert answer["status"] == "second_clarification_rejected"


def test_FR_AGENT_007_resume_is_owner_isolated():
    waiting = accept_clarification(_state())
    foreign = resume_clarification(waiting, "考勤制度", actor_id="other-user")
    denied = foreign["final_answer"]
    assert denied is not None
    assert denied["status"] == "resume_forbidden"
    resumed = resume_clarification(waiting, "考勤制度", actor_id="owner-1")
    resumed_clarification = resumed.get("clarification")
    assert resumed["final_answer"] is None
    assert resumed_clarification is not None
    assert resumed_clarification["status"] == "resuming"
    assert resumed["budget_state"]["model_calls"] == 1
    assert resumed["messages"][-1]["content"] == "考勤制度"


def test_FR_AGENT_004_budget_survives_resume():
    waiting = accept_clarification(_state(model_calls=2, clarification_count=0))
    resumed = resume_clarification(waiting, "继续", actor_id="owner-1")
    assert resumed["budget_state"]["model_calls"] == 2
    assert resumed["budget_state"]["clarification_count"] == 1
