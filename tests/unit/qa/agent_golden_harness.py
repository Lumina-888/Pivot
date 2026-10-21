"""
Agent Golden Set 评测装配（ND-AGENT-05-C）

用途：以夹具场景驱动真实 Agent 图运行。Fake 只替换外部模型与检索服务：
- ScriptedGoldenModel 按场景脚本返回工具调用（占位符 $search_N.first 在
  运行时解析为第 N 次搜索返回的首个 evidence_id）；
- GoldenRetriever 对夹具语块做确定性关键词评分，并执行语块级权限过滤；
- 图、工具执行、证据注册表、预算与结构化收尾器均为生产实现。

本模块不是生产代码，不得被 api/worker 引用。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pivot.qa.agent_budget import BudgetPolicy
from pivot.qa.agent_finalizer import StructuredFinalizer
from pivot.qa.agent_graph import run_agent
from pivot.qa.ports import EvidenceHit, RetrievalResult

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "spec"
    / "fixtures"
    / "golden-set"
    / "agent"
    / "v0.1-public.json"
)

MIN_BIGRAM_OVERLAP = 3
MAX_HITS = 4


def load_fixture() -> dict[str, Any]:
    with open(FIXTURE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _bigrams(text: str) -> set[str]:
    cleaned = re.sub(r"[^\w]", "", text)
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


class GoldenRetriever:
    """确定性关键词检索 Fake：二元组重叠评分加权限与范围过滤。"""

    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self._chunks = chunks
        self.calls: list[dict[str, Any]] = []
        self.returned_chunk_ids: list[str] = []

    def retrieve(
        self,
        question: str,
        *,
        scope_type: str,
        scope_document_id: str | None,
        principal_id: str,
    ) -> RetrievalResult:
        self.calls.append(
            {
                "query": question,
                "scope_type": scope_type,
                "scope_document_id": scope_document_id,
                "principal_id": principal_id,
            }
        )
        query_grams = _bigrams(question)
        scored: list[tuple[int, str, dict[str, Any]]] = []
        for chunk in self._chunks:
            if chunk.get("access") == "restricted" and principal_id not in chunk.get(
                "allowed_principals", []
            ):
                continue
            if scope_type == "document" and chunk["document_id"] != scope_document_id:
                continue
            overlap = len(query_grams & _bigrams(chunk["text"]))
            if overlap >= MIN_BIGRAM_OVERLAP:
                scored.append((overlap, chunk["chunk_id"], chunk))
        scored.sort(key=lambda item: (-item[0], item[1]))
        hits = tuple(
            EvidenceHit(
                chunk_id=chunk["chunk_id"],
                document_id=chunk["document_id"],
                version_id=chunk["version_id"],
                text=chunk["text"],
                locator=chunk.get("locator", ""),
                external_llm_allowed=bool(chunk.get("external_llm_allowed", False)),
            )
            for _, _, chunk in scored[:MAX_HITS]
        )
        self.returned_chunk_ids.extend(hit.chunk_id for hit in hits)
        return RetrievalResult(
            status="found" if hits else "empty",
            evidence=hits,
        )


class ScriptedGoldenModel:
    """按场景脚本决策的 Fake 模型；脚本耗尽即报错（轨迹已偏离预期）。"""

    def __init__(self, script: list[dict[str, Any]]) -> None:
        self._script = script
        self._index = 0
        self.call_count = 0

    def decide(self, messages: list[Any], tools: list[Any]) -> Any:
        del tools
        self.call_count += 1
        if self._index >= len(self._script):
            raise AssertionError(
                f"脚本已耗尽但图仍在请求决策（第 {self.call_count} 次调用）"
            )
        step = self._script[self._index]
        self._index += 1
        if step.get("final"):
            return SimpleNamespace(
                content="（脚本结束）", tool_calls=[], usage_metadata=None
            )
        args = {
            key: self._resolve(value, messages) for key, value in step["args"].items()
        }
        return SimpleNamespace(
            content="",
            tool_calls=[
                {"id": f"call_{self.call_count}", "name": step["tool"], "args": args}
            ],
            usage_metadata=None,
        )

    @staticmethod
    def _resolve(value: Any, messages: list[Any]) -> Any:
        if not (isinstance(value, str) and value.startswith("$search_")):
            return value
        ordinal = int(value.split(".")[0].removeprefix("$search_"))
        search_results: list[list[str]] = []
        for message in messages:
            if not isinstance(message, dict) or message.get("role") != "tool":
                continue
            try:
                payload = json.loads(message.get("content") or "{}")
            except (TypeError, ValueError):
                continue
            if isinstance(payload, dict) and "evidence_ids" in payload:
                search_results.append(list(payload["evidence_ids"]))
        if ordinal > len(search_results) or not search_results[ordinal - 1]:
            raise AssertionError(f"占位符 {value} 无可用的搜索结果可解析")
        return search_results[ordinal - 1][0]


class GoldenDraftWriter:
    """确定性证据拼接写作者（StructuredFinalizer 的 claim/citation 方言）。"""

    def draft(
        self, question: str, hits: tuple[EvidenceHit, ...]
    ) -> tuple[str, list[dict], list[dict]]:
        del question
        claims = [{"index": i, "text": hit.text} for i, hit in enumerate(hits)]
        citations = [{"claim_index": i, "evidence_index": i} for i in range(len(hits))]
        return "\n".join(hit.text for hit in hits), claims, citations


def _normalize_messages(messages: list[Any]) -> tuple[list[str], list[str], list[str]]:
    """返回 (工具名序列, 工具消息内容, 全部文本) 供断言使用。"""
    tool_sequence: list[str] = []
    tool_contents: list[str] = []
    texts: list[str] = []
    for message in messages:
        content = getattr(message, "content", None)
        tool_calls = getattr(message, "tool_calls", None)
        if isinstance(message, dict):
            content = message.get("content", content)
            tool_calls = message.get("tool_calls", tool_calls)
        if tool_calls:
            for call in tool_calls:
                tool_sequence.append(
                    call["name"] if isinstance(call, dict) else call.get("name")
                )
        if content:
            texts.append(str(content))
        if message.__class__.__name__ == "ToolMessage" or (
            isinstance(message, dict) and message.get("type") == "tool"
        ):
            tool_contents.append(str(content or ""))
    return tool_sequence, tool_contents, texts


def run_scenario(fixture: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    """运行一个场景并返回可断言的运行记录。"""
    retriever = GoldenRetriever(fixture["chunks"])
    model = ScriptedGoldenModel(scenario["script"])
    overrides = scenario.get("budget_overrides", {})
    policy = BudgetPolicy(
        max_model_calls=int(overrides.get("max_model_calls", 10)),
        max_tool_calls=int(overrides.get("max_tool_calls", 20)),
        max_rewrite_count=int(overrides.get("max_rewrite_count", 3)),
        timeout_seconds=60.0,
    )
    finalizer = StructuredFinalizer(GoldenDraftWriter(), None)
    result = run_agent(
        scenario["question"],
        retriever,
        policy,
        run_id=f"run-{scenario['id']}",
        principal_id=scenario["principal_id"],
        conversation_id="conv-golden",
        scope_type=scenario.get("scope_type", "global"),
        scope_document_id=scenario.get("scope_document_id"),
        model=model,
        finalizer=finalizer,
        is_external_model=True,
    )
    tool_sequence, tool_contents, texts = _normalize_messages(result["messages"])
    final_answer = result.get("final_answer") or {}
    transcript = "\n".join(
        texts
        + [str(final_answer.get("answer", ""))]
        + [str(claim.get("text", "")) for claim in final_answer.get("claims", [])]
    )
    return {
        "result": result,
        "final_answer": final_answer,
        "tool_sequence": tool_sequence,
        "tool_contents": tool_contents,
        "transcript": transcript,
        "model_calls": model.call_count,
        "retriever": retriever,
    }


def assert_expectations(record: dict[str, Any], scenario: dict[str, Any]) -> None:
    """按场景 expect 块断言运行记录。"""
    expect = scenario["expect"]
    label = scenario["id"]
    final_answer = record["final_answer"]
    assert final_answer.get("status") == expect["final_status"], (
        f"{label}: 终态 {final_answer.get('status')} != 期望 {expect['final_status']}"
    )
    assert record["tool_sequence"] == expect["tool_sequence"], (
        f"{label}: 工具序列 {record['tool_sequence']} != 期望 {expect['tool_sequence']}"
    )
    answer = str(final_answer.get("answer", ""))
    for needle in expect.get("answer_contains", []):
        assert needle in answer, f"{label}: 答案缺少 {needle!r}"
    for needle in expect.get("transcript_not_contains", []):
        assert needle not in record["transcript"], (
            f"{label}: 记录中出现禁止内容 {needle!r}"
        )
    assert len(final_answer.get("claims", [])) >= int(expect.get("min_claims", 0)), (
        f"{label}: claims 数量不足"
    )
    if "model_calls" in expect:
        assert record["model_calls"] == expect["model_calls"], (
            f"{label}: 模型调用 {record['model_calls']} != 期望 {expect['model_calls']}"
        )
    for observation in expect.get("observations", []):
        _assert_observation(record, observation, label)


def _assert_observation(
    record: dict[str, Any], observation: dict[str, Any], label: str
) -> None:
    kind = observation["type"]
    if kind == "read_after_search":
        sequence = record["tool_sequence"]
        assert "search_knowledge" in sequence and "read_evidence" in sequence, (
            f"{label}: 轨迹缺少搜索或读取"
        )
        assert sequence.index("read_evidence") > sequence.index("search_knowledge"), (
            f"{label}: 读取必须发生在搜索之后"
        )
    elif kind == "search_queries_differ":
        queries = [call["query"] for call in record["retriever"].calls]
        assert len(set(queries)) >= 2, f"{label}: 多次搜索的查询词应当不同"
    elif kind == "tool_error_seen":
        assert any(
            observation["value"] in content for content in record["tool_contents"]
        ), f"{label}: 工具消息中未见错误 {observation['value']!r}"
    else:
        raise AssertionError(f"{label}: 未知观察类型 {kind}")
