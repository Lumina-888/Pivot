"""Agent 端到端闭环（Fake 模型，不调用付费 API）。"""

from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from pivot.qa.agent_budget import BudgetPolicy
from pivot.qa.agent_graph import run_agent
from pivot.qa.ports import EvidenceHit, RetrievalResult


class ScriptedModel:
    """按调用次序返回预设 AIMessage。"""

    def __init__(self, responses: list[AIMessage]) -> None:
        self.responses = responses
        self.calls: list[list[dict[str, Any]]] = []

    def decide(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AIMessage:
        self.calls.append(messages)
        if len(self.calls) > len(self.responses):
            raise AssertionError("scripted model ran out of responses")
        return self.responses[len(self.calls) - 1]


class CorpusRetriever:
    def __init__(self, hits: tuple[EvidenceHit, ...]) -> None:
        self.hits = hits
        self.queries: list[str] = []

    def retrieve(self, question, *, scope_type, scope_document_id, principal_id):
        self.queries.append(question)
        matched = tuple(
            hit for hit in self.hits if question in hit.text or "迟到" in question
        )
        if not matched:
            return RetrievalResult(status="empty", evidence=())
        return RetrievalResult(status="found", evidence=matched)

    def resolve_evidence(
        self, chunk_id, *, scope_type, scope_document_id, principal_id
    ):
        return next((hit for hit in self.hits if hit.chunk_id == chunk_id), None)


class EchoWriter:
    def draft(self, question, hits):
        answer = hits[0].text
        claims = [{"index": 0, "text": answer}]
        citations = [{"claim_index": 0, "evidence_index": 0}]
        return answer, claims, citations


ATTENDANCE = EvidenceHit(
    chunk_id="chk-attendance",
    document_id="doc-attendance",
    version_id="v1",
    text="一个月内累计迟到三次，视为旷工一天。",
    locator="第一条",
    external_llm_allowed=True,
)


def _policy(
    *,
    max_model_calls: int = 4,
    max_tool_calls: int = 4,
    max_rewrite_count: int = 1,
    timeout_seconds: float = 30,
) -> BudgetPolicy:
    return BudgetPolicy(
        max_model_calls=max_model_calls,
        max_tool_calls=max_tool_calls,
        max_rewrite_count=max_rewrite_count,
        timeout_seconds=timeout_seconds,
    )


def test_complete_question_answering_flow():
    """搜索后读取证据，最终答案必须引用已授权原文。"""
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-search",
                        "name": "search_knowledge",
                        "args": {"query": "迟到三次"},
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-read",
                        "name": "read_evidence",
                        "args": {"evidence_id": "ev_1"},
                    }
                ],
            ),
            AIMessage(content="证据已足够，可以回答。"),
        ]
    )
    result = run_agent(
        "迟到三次怎么处理？",
        CorpusRetriever((ATTENDANCE,)),
        _policy(),
        run_id="run-e2e",
        principal_id="user-1",
        conversation_id="conv-1",
        model=model,
        draft_writer=EchoWriter(),
    )

    assert result["final_answer"]["status"] == "completed"
    assert "视为旷工一天" in result["final_answer"]["answer"]
    assert result["final_answer"]["claims"][0]["evidence_ids"] == ["ev_1"]
    assert result["budget_state"]["model_calls"] == 3
    assert result["budget_state"]["tool_calls"] == 2
    assert len(model.calls) == 3
    assert json.loads(model.calls[2][-1]["content"])["text"].startswith(
        "一个月内累计迟到三次"
    )


def test_multi_turn_tool_sequence_keeps_question_context():
    """第二轮决策仍能看到原始问题和上一轮工具结果。"""
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-search",
                        "name": "search_knowledge",
                        "args": {"query": "火星"},
                    }
                ],
            ),
            AIMessage(content="没有足够证据。"),
        ]
    )
    result = run_agent(
        "火星移民政策是什么？",
        CorpusRetriever((ATTENDANCE,)),
        _policy(),
        run_id="run-empty",
        principal_id="user-1",
        conversation_id="conv-1",
        model=model,
        draft_writer=EchoWriter(),
    )

    assert result["final_answer"]["status"] == "insufficient_evidence"
    second_turn = model.calls[1]
    assert second_turn[0]["content"] == "火星移民政策是什么？"
    tool_message = next(message for message in second_turn if message["role"] == "tool")
    assert json.loads(tool_message["content"])["status"] == "empty"


def test_budget_exhaustion_stops_before_another_model_call():
    """模型次数用尽后停止，不再请求下一次决策。"""
    model = ScriptedModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-search",
                        "name": "search_knowledge",
                        "args": {"query": "迟到三次"},
                    }
                ],
            )
        ]
    )

    result = run_agent(
        "迟到三次怎么处理？",
        CorpusRetriever((ATTENDANCE,)),
        _policy(max_model_calls=1, max_tool_calls=1),
        run_id="run-budget",
        principal_id="user-1",
        conversation_id="conv-1",
        model=model,
        draft_writer=EchoWriter(),
    )

    assert result["final_answer"]["status"] == "budget_exhausted"
    assert result["budget_state"]["model_calls"] == 1
    assert len(model.calls) == 1


def test_run_agent_rejects_non_positive_budget():
    with pytest.raises(ValueError):
        BudgetPolicy(
            max_model_calls=0,
            max_tool_calls=1,
            max_rewrite_count=0,
            timeout_seconds=1,
        )
