"""ND-AGENT-03-C: 调用返回后重检取消，晚到结果不得覆盖 cancelled。"""

from __future__ import annotations

import threading

import pytest
from langchain_core.messages import AIMessage
from pivot.qa.agent_budget import BudgetPolicy
from pivot.qa.agent_context import RunContext
from pivot.qa.agent_graph import AgentNodes, AgentState
from pivot.qa.ports import RetrievalResult
from pivot.runs.errors import RunError
from pivot.runs.service import RunService


class BlockingModel:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def decide(self, messages, tools):
        self.entered.set()
        assert self.release.wait(timeout=5)
        return AIMessage(content="晚到答案")


class EmptyRetriever:
    def retrieve(self, question, *, scope_type, scope_document_id, principal_id):
        return RetrievalResult(status="empty", evidence=())


def _state() -> AgentState:
    return {
        "messages": [{"type": "human", "content": "迟到怎么处理"}],
        "run_id": "run-1",
        "principal_id": "user-1",
        "conversation_id": "conv-1",
        "scope_type": "global",
        "scope_document_id": None,
        "budget_state": {
            "model_calls": 0,
            "tool_calls": 0,
            "rewrite_count": 0,
            "elapsed_seconds": 0.0,
        },
        "evidence_registry_data": {},
        "final_answer": None,
    }


def test_FR_AGENT_008_cancel_blocks_late_model_answer():
    model = BlockingModel()
    nodes = AgentNodes(
        EmptyRetriever(),
        BudgetPolicy(max_model_calls=3, max_tool_calls=3, max_rewrite_count=2, timeout_seconds=60),
        RunContext("run-1", "conv-1", "user-1", "global", None),
        model,
    )
    worker = threading.Thread(target=lambda: nodes.decide(_state()))
    worker.start()
    assert model.entered.wait(timeout=5)
    nodes.cancel()
    model.release.set()
    worker.join(timeout=5)
    result = nodes.decide(_state())
    final_answer = result["final_answer"]
    assert final_answer is not None
    assert final_answer["status"] == "cancelled"
    assert result["messages"] == []


def test_FR_STREAM_004_cancel_terminal_is_idempotent():
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv-1",
        owner_id="user-1",
        question="迟到怎么处理",
        idempotency_key="idem-1",
        request_id="req-1",
    )
    first = runs.cancel(bundle.run.id, "req-c1")
    second = runs.cancel(bundle.run.id, "req-c2")
    assert first.run.state == second.run.state == "cancelled"
    with pytest.raises(RunError):
        from pivot.runs.machine import apply

        apply("answered", "cancel", "req-c3")
    events = [name for name, _data in runs.log(bundle.run.id).replay()]
    assert events.count("cancelled") == 1
