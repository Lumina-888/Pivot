"""
FR-AGENT-012 答案层问题-证据相关性判定（ADR-015）

- 收尾前判定问题与注册证据的语义相关性；不相关则复用
  insufficient_evidence 结局拒答，且不再调用草稿生成器。
- 判定异常、输出不可解析、预算耗尽一律 fail-open（照常成答）：
  相关性是质量门，不是授权门。
- 判定调用计入单 Run 模型调用计数与 token 结算。
- relevance_judge 默认 None（关），关时行为与变更前一致。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pivot.qa.agent_budget import BudgetPolicy
from pivot.qa.agent_finalizer import StructuredFinalizer
from pivot.qa.agent_graph import run_agent
from pivot.qa.agent_relevance import ModelRelevanceJudge, RelevanceVerdict
from pivot.qa.ports import EvidenceHit, RetrievalResult

from tests.unit.qa.agent_golden_harness import GoldenDraftWriter

TEXT = "年休假天数表：累计工作满 1 年不满 10 年的职工，年休假 5 天。"
QUESTION = "婚假有几天？"  # 与证据话题相邻但答非所问（ag-005 形状）


class _StubRetriever:
    def retrieve(
        self,
        question: str,
        *,
        scope_type: str,
        scope_document_id: str | None,
        principal_id: str,
    ) -> RetrievalResult:
        del question, scope_type, scope_document_id, principal_id
        hit = EvidenceHit(
            chunk_id="chk-a",
            document_id="doc-a",
            version_id="ver-a",
            text=TEXT,
            locator="第1条",
            external_llm_allowed=True,
        )
        return RetrievalResult(status="found", evidence=(hit,))


class _ScriptModel:
    """search -> read -> final 的脚本模型，可报告固定用量。"""

    def __init__(self, *, usage: dict[str, int] | None = None) -> None:
        self._usage = usage
        self._step = 0

    def decide(self, messages: list[Any], tools: list[Any]) -> Any:
        del messages, tools
        self._step += 1
        if self._step == 1:
            return SimpleNamespace(
                content="",
                tool_calls=[
                    {"id": "c1", "name": "search_knowledge", "args": {"query": "假期"}}
                ],
                usage_metadata=self._usage,
            )
        if self._step == 2:
            return SimpleNamespace(
                content="",
                tool_calls=[
                    {"id": "c2", "name": "read_evidence", "args": {"evidence_id": "ev_1"}}
                ],
                usage_metadata=self._usage,
            )
        return SimpleNamespace(content="（结束）", tool_calls=[], usage_metadata=self._usage)


class _CountingWriter(GoldenDraftWriter):
    def __init__(self) -> None:
        self.calls = 0

    def draft(self, question: str, hits: tuple) -> Any:
        self.calls += 1
        return super().draft(question, hits)


class _StubJudge:
    def __init__(self, verdict: RelevanceVerdict | Exception) -> None:
        self._verdict = verdict
        self.calls = 0

    def judge(self, question: str, evidences: list[dict[str, Any]]) -> RelevanceVerdict:
        del question, evidences
        self.calls += 1
        if isinstance(self._verdict, Exception):
            raise self._verdict
        return self._verdict


def _policy(**overrides: Any) -> BudgetPolicy:
    values: dict[str, Any] = {
        "max_model_calls": 10,
        "max_tool_calls": 20,
        "max_rewrite_count": 3,
        "timeout_seconds": 60.0,
    }
    values.update(overrides)
    return BudgetPolicy(**values)


def _run(*, judge: Any = None, writer: _CountingWriter | None = None, **policy_kw: Any):
    writer = writer or _CountingWriter()
    result = run_agent(
        QUESTION,
        _StubRetriever(),
        _policy(**policy_kw),
        run_id="run-fr-agent-012",
        principal_id="employee_wang",
        conversation_id="conv-fr-agent-012",
        model=_ScriptModel(),
        finalizer=StructuredFinalizer(writer, None),
        is_external_model=True,
        relevance_judge=judge,
    )
    return result, writer


def test_FR_AGENT_012_irrelevant_verdict_refuses_without_drafting() -> None:
    """判定不相关：复用 insufficient_evidence 拒答，且不调用草稿生成器。"""
    judge = _StubJudge(RelevanceVerdict(relevant=False))
    result, writer = _run(judge=judge)
    assert judge.calls == 1
    assert writer.calls == 0, "判定不相关后不得再成答"
    assert result["final_answer"]["status"] == "insufficient_evidence"
    assert result["final_answer"]["claims"] == []


def test_FR_AGENT_012_relevant_verdict_completes() -> None:
    """判定相关：照常成答。"""
    judge = _StubJudge(RelevanceVerdict(relevant=True))
    result, writer = _run(judge=judge)
    assert result["final_answer"]["status"] == "completed"
    assert writer.calls == 1


def test_FR_AGENT_012_judge_failure_fails_open() -> None:
    """判定抛错：fail-open，照常成答（质量门故障不误拒）。"""
    judge = _StubJudge(RuntimeError("provider down"))
    result, writer = _run(judge=judge)
    assert result["final_answer"]["status"] == "completed"
    assert writer.calls == 1


def test_FR_AGENT_012_no_judge_keeps_current_behavior() -> None:
    """默认关：无判定器时答非所问的证据也照常成答（变更前行为）。"""
    result, writer = _run(judge=None)
    assert result["final_answer"]["status"] == "completed"
    assert writer.calls == 1


def test_FR_AGENT_012_judge_call_counts_against_budget() -> None:
    """判定调用计入模型调用计数与 token 结算（与 decide 同口径）。"""
    usage = {"input_tokens": 100, "output_tokens": 10}
    judge = _StubJudge(RelevanceVerdict(relevant=True, usage=usage))
    result, _ = _run(judge=judge)
    budget = result["budget_state"]
    # 脚本模型 3 次 decide（无用量报告，走次计数）+ 判定 1 次
    assert budget["model_calls"] == 4
    assert budget["total_tokens"] == 110


def test_FR_AGENT_012_budget_exhausted_skips_judge() -> None:
    """预算已耗尽：跳过判定（不调判定器），fail-open 照常成答。"""
    judge = _StubJudge(RelevanceVerdict(relevant=False))
    # 脚本恰好用满 3 次 decide，finalize 时预算已到上限
    result, writer = _run(judge=judge, max_model_calls=3)
    assert judge.calls == 0
    assert result["final_answer"]["status"] == "completed"
    assert writer.calls == 1


class _FakeJudgeModel:
    def __init__(self, content: str) -> None:
        self._content = content

    def decide(self, messages: list[Any], tools: list[Any]) -> Any:
        del messages, tools
        return SimpleNamespace(
            content=self._content,
            tool_calls=[],
            usage_metadata={"input_tokens": 5, "output_tokens": 1},
        )


def test_FR_AGENT_012_model_judge_parses_verdicts() -> None:
    """ModelRelevanceJudge：严格解析首行裁决，不可解析按相关处理。"""
    evidences = [{"text": TEXT, "locator": "第1条", "chunk_id": "chk-a"}]
    irrelevant = ModelRelevanceJudge(_FakeJudgeModel("IRRELEVANT\n证据讲的是年休假"))
    assert irrelevant.judge(QUESTION, evidences).relevant is False
    relevant = ModelRelevanceJudge(_FakeJudgeModel("RELEVANT"))
    assert relevant.judge(QUESTION, evidences).relevant is True
    garbage = ModelRelevanceJudge(_FakeJudgeModel("我觉得差不多吧"))
    verdict = garbage.judge(QUESTION, evidences)
    assert verdict.relevant is True, "不可解析输出必须 fail-open"
    assert verdict.usage == {"input_tokens": 5, "output_tokens": 1}
