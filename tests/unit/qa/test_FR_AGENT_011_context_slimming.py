"""
FR-AGENT-011 Agent 上下文瘦身（M 线，端到端方案第八节）

- M-1 观测掩盖：decide 外发副本中，较早轮次的 read_evidence 全文换成存根，
  最近一次读取保留全文；落库状态与检查点保持原文。
- M-2 重复读短路：重复读取的目标证据全文仍在外发历史中（它是最近一次
  全文读取）时返回短提示（带摘要）；全文已被掩盖的证据再读直接给全文，
  短提示的「全文见前次结果」永远为真。每次读取仍走完整授权复核。
- M-3 预算触发：BudgetPolicy.history_token_soft_budget 默认关（None）；
  累计已报告 token 达到软预算后加重掩盖（旧读取连片段也不留，
  最近一次读取仍保留全文）。软预算数值不冻结，属 DR-010 输入。
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from pivot.qa.agent_budget import BudgetPolicy
from pivot.qa.agent_finalizer import StructuredFinalizer
from pivot.qa.agent_graph import run_agent
from pivot.qa.ports import EvidenceHit, RetrievalResult
from tests.unit.qa.agent_golden_harness import GoldenDraftWriter

TEXT_A = "年休假天数表：" + "甲" * 200
TEXT_B = "婚假规定说明：" + "乙" * 200
MASK_MARKER = "已掩盖"


class _StubRetriever:
    """固定返回两条证据的检索存根。"""

    def retrieve(
        self,
        question: str,
        *,
        scope_type: str,
        scope_document_id: str | None,
        principal_id: str,
    ) -> RetrievalResult:
        del question, scope_type, scope_document_id, principal_id
        hits = (
            EvidenceHit(
                chunk_id="chk-a",
                document_id="doc-a",
                version_id="ver-a",
                text=TEXT_A,
                locator="第1条",
                external_llm_allowed=True,
            ),
            EvidenceHit(
                chunk_id="chk-b",
                document_id="doc-b",
                version_id="ver-b",
                text=TEXT_B,
                locator="第2条",
                external_llm_allowed=True,
            ),
        )
        return RetrievalResult(status="found", evidence=hits)


class _RecordingModel:
    """按脚本决策并记录每次 decide 收到的外发消息副本。"""

    def __init__(
        self,
        script: list[dict[str, Any]],
        *,
        usage: dict[str, int] | None = None,
    ) -> None:
        self._script = script
        self._index = 0
        self._usage = usage
        self.seen_messages: list[list[dict[str, Any]]] = []

    def decide(self, messages: list[Any], tools: list[Any]) -> Any:
        del tools
        self.seen_messages.append(
            [dict(message) for message in messages if isinstance(message, dict)]
        )
        step = self._script[self._index]
        self._index += 1
        if step.get("final"):
            return SimpleNamespace(
                content="（脚本结束）", tool_calls=[], usage_metadata=self._usage
            )
        return SimpleNamespace(
            content="",
            tool_calls=[
                {
                    "id": f"call_{self._index}",
                    "name": step["tool"],
                    "args": step["args"],
                }
            ],
            usage_metadata=self._usage,
        )


def _policy(**overrides: Any) -> BudgetPolicy:
    values: dict[str, Any] = {
        "max_model_calls": 10,
        "max_tool_calls": 20,
        "max_rewrite_count": 3,
        "timeout_seconds": 60.0,
    }
    values.update(overrides)
    return BudgetPolicy(**values)


def _run(script: list[dict[str, Any]], model: _RecordingModel, policy: BudgetPolicy):
    return run_agent(
        "年休假有几天？",
        _StubRetriever(),
        policy,
        run_id="run-fr-agent-011",
        principal_id="employee_wang",
        conversation_id="conv-fr-agent-011",
        model=model,
        finalizer=StructuredFinalizer(GoldenDraftWriter(), None),
        is_external_model=True,
    )


def _tool_payloads(messages: list[Any]) -> list[dict[str, Any]]:
    payloads = []
    for message in messages:
        content = getattr(message, "content", None)
        if isinstance(message, dict):
            content = message.get("content", content)
        if not isinstance(content, str):
            continue
        try:
            payload = json.loads(content)
        except ValueError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _read_payloads(messages: list[Any]) -> list[dict[str, Any]]:
    return [
        payload
        for payload in _tool_payloads(messages)
        if "evidence_id" in payload and ("text" in payload or "already_read" in payload)
    ]


_SEARCH = {"tool": "search_knowledge", "args": {"query": "年休假"}}
_READ_1 = {"tool": "read_evidence", "args": {"evidence_id": "ev_1"}}
_READ_2 = {"tool": "read_evidence", "args": {"evidence_id": "ev_2"}}
_FINAL = {"final": True}


def test_FR_AGENT_011_older_reads_are_masked_only_in_outbound_copy() -> None:
    """M-1：外发副本掩盖较早读取、保留最近读取；落库状态保持原文。"""
    model = _RecordingModel([_SEARCH, _READ_1, _READ_2, _FINAL])
    result = _run([_SEARCH, _READ_1, _READ_2, _FINAL], model, _policy())

    last_seen = model.seen_messages[-1]
    outbound_reads = _read_payloads(last_seen)
    assert len(outbound_reads) == 2
    older, latest = outbound_reads
    assert MASK_MARKER in older["text"], "较早读取的全文应在外发副本中被掩盖"
    assert TEXT_A not in older["text"]
    assert older["evidence_id"] == "ev_1"
    assert latest["text"] == TEXT_B, "最近一次读取必须保留全文"

    # 搜索结果不属于读取全文，不得被掩盖改动
    search_payloads = [
        payload for payload in _tool_payloads(last_seen) if "evidence_ids" in payload
    ]
    assert search_payloads and search_payloads[0]["evidence_ids"] == ["ev_1", "ev_2"]

    # 落库状态保持原文：两条读取的全文都在
    persisted_reads = _read_payloads(result["messages"])
    assert [payload["text"] for payload in persisted_reads] == [TEXT_A, TEXT_B]


def test_FR_AGENT_011_repeat_read_of_visible_evidence_returns_stub() -> None:
    """M-2：目标证据全文仍在外发历史中时，重复读取一律短路为短提示。"""
    model = _RecordingModel([_SEARCH, _READ_1, _READ_1, _READ_1, _FINAL])
    result = _run([_SEARCH, _READ_1, _READ_1, _READ_1, _FINAL], model, _policy())

    reads = _read_payloads(result["messages"])
    assert len(reads) == 3
    assert reads[0]["text"] == TEXT_A
    for stub in reads[1:]:
        assert stub.get("already_read") is True, "全文可见时的重复读应短路"
        assert "text" not in stub, "短提示不得携带全文"
        assert TEXT_A[:30] in stub["excerpt"], "短提示应带摘要便于模型定位"


def test_FR_AGENT_011_reread_of_masked_evidence_returns_full_text() -> None:
    """M-1/M-2 自洽：读 B 后 A 的全文已被掩盖，再读 A 必须直接给全文。"""
    script = [_SEARCH, _READ_1, _READ_2, _READ_1, _FINAL]
    model = _RecordingModel(script)
    result = _run(script, model, _policy())

    reads = _read_payloads(result["messages"])
    assert len(reads) == 3
    assert reads[0]["text"] == TEXT_A
    assert reads[1]["text"] == TEXT_B
    assert reads[2]["text"] == TEXT_A, "被掩盖证据的再读不得被短提示挡住"


def test_FR_AGENT_011_soft_budget_heavy_masking_strips_excerpts() -> None:
    """M-3：软预算触发后旧读取连片段也不留；最近一次仍保留全文。"""
    usage = {"input_tokens": 600, "output_tokens": 0}
    model = _RecordingModel([_SEARCH, _READ_1, _READ_2, _FINAL], usage=usage)
    result = _run(
        [_SEARCH, _READ_1, _READ_2, _FINAL],
        model,
        _policy(history_token_soft_budget=500),
    )

    outbound_reads = _read_payloads(model.seen_messages[-1])
    assert len(outbound_reads) == 2
    older, latest = outbound_reads
    assert MASK_MARKER in older["text"]
    assert TEXT_A[:30] not in older["text"], "加重掩盖不得保留开头片段"
    assert latest["text"] == TEXT_B, "最近一次读取在加重模式下仍保留全文"
    # 加重掩盖仍只作用于外发副本
    persisted_reads = _read_payloads(result["messages"])
    assert [payload["text"] for payload in persisted_reads] == [TEXT_A, TEXT_B]


def test_FR_AGENT_011_soft_budget_defaults_off() -> None:
    """M-3 默认关：用量再大也只做常规掩盖，最近一次读取保留全文。"""
    usage = {"input_tokens": 100_000, "output_tokens": 0}
    model = _RecordingModel([_SEARCH, _READ_1, _READ_2, _FINAL], usage=usage)
    _run([_SEARCH, _READ_1, _READ_2, _FINAL], model, _policy())

    outbound_reads = _read_payloads(model.seen_messages[-1])
    assert len(outbound_reads) == 2
    assert MASK_MARKER in outbound_reads[0]["text"]
    assert outbound_reads[1]["text"] == TEXT_B


def test_FR_AGENT_011_soft_budget_must_be_non_negative() -> None:
    """M-3 开关校验：负数软预算拒绝构造，零与正数合法。"""
    with pytest.raises(ValueError):
        _policy(history_token_soft_budget=-1)
    _policy(history_token_soft_budget=0)
    _policy(history_token_soft_budget=8_000)
