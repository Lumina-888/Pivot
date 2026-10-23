"""Agent 结局对接（W2）：LangGraph 运行结果映射到 Run 状态机与 SSE。

执行入口与 QaOrchestrator.execute 同形，HTTP 层按引擎开关二选一。
图的四种结局映射为既有 Run 终态：completed 对 answered、
insufficient_evidence 对 refused、verification_failed 对 uncertain、
其余（预算耗尽、取消、供应商失败）对 failed。阶段事件只发公开阶段名
（agent_projection 口径），不透传内部节点名。发布语义与编排器一致：
先经 persist_result 提交，再发 token、citation 与终态事件。

澄清恢复的公开契约尚未冻结（SPEC），本模块只把图内澄清结局映射为
waiting_for_user，不实现恢复执行；恢复调用的行为与现行流水线一致，
留待契约冻结后另行接线。尝试记录的 provider_attempts 落账需要 04
持久化会话，同样不在本片范围。
"""

from __future__ import annotations

from collections.abc import Callable

from pivot.qa.orchestrator import TERMINAL_EVENT
from pivot.runs.machine import apply, is_terminal
from pivot.runs.models import RunBundle
from pivot.stream.buffer import EventLog

_PUBLIC_STAGES = frozenset(
    {"planning", "retrieving", "drafting", "verifying", "waiting_for_user"}
)


class AgentQaExecutor:
    """Execute runs through the assembled LangGraph agent runner."""

    def __init__(self, runner) -> None:
        self._runner = runner

    def execute(
        self,
        bundle: RunBundle,
        log: EventLog,
        request_id: str,
        *,
        persist_result: Callable[[RunBundle], None] | None = None,
    ) -> RunBundle:
        run = bundle.run
        if is_terminal(run.state):
            return bundle
        log.emit("run_started", "received", {})
        # A waiting_for_user run re-entering execute (the HTTP resume path)
        # raises here exactly as the orchestrator does; the public resume
        # contract is not frozen yet.
        run.state = apply(run.state, "plan", request_id)
        self._stage(log, "planning")
        try:
            result = self._runner.run(
                run.question,
                run_id=run.id,
                principal_id=run.owner_id,
                conversation_id=run.conversation_id,
                scope_type=run.scope_type,
                scope_document_id=run.scope_document_id,
            )
        except Exception:
            run.error_code = "PROVIDER_TEMPORARY_ERROR"
            self._advance(bundle, log, request_id, "retrieve", "retrieving")
            run.state = apply(run.state, "fail", request_id)
            return self._publish(bundle, log, persist_result)
        clarification = result.get("clarification") or {}
        if clarification.get("status") == "waiting_for_user":
            run.clarification_count += 1
            run.state = apply(run.state, "clarify", request_id)
            log.emit("stage", "waiting_for_user", {"awaiting": "clarification"})
            return self._publish(bundle, log, persist_result)
        final = result.get("final_answer") or {}
        status = final.get("status")
        self._advance(bundle, log, request_id, "retrieve", "retrieving")
        if status == "completed":
            self._advance(bundle, log, request_id, "draft", "drafting")
            self._advance(bundle, log, request_id, "verify", "verifying")
            bundle.claims = [
                {
                    "text": claim.get("text", ""),
                    "evidence_ids": list(claim.get("evidence_ids") or []),
                }
                for claim in final.get("claims") or []
            ]
            registry = result.get("evidence_registry_data") or {}
            seen: set[str] = set()
            bundle.citations = []
            for claim in bundle.claims:
                for evidence_id in claim["evidence_ids"]:
                    if evidence_id in seen:
                        continue
                    seen.add(evidence_id)
                    entry = registry.get(evidence_id) or {}
                    citation = {"id": evidence_id}
                    for field in ("chunk_id", "document_id", "version_id", "locator"):
                        if entry.get(field) is not None:
                            citation[field] = entry[field]
                    bundle.citations.append(citation)
            run.answer_markdown = final.get("answer") or ""
            run.state = apply(run.state, "answer", request_id)
        elif status == "insufficient_evidence":
            run.state = apply(run.state, "refuse", request_id)
        elif status == "verification_failed":
            self._advance(bundle, log, request_id, "draft", "drafting")
            self._advance(bundle, log, request_id, "verify", "verifying")
            run.error_code = "VERIFICATION_UNAVAILABLE"
            run.state = apply(run.state, "uncertain", request_id)
        else:
            run.error_code = "PROVIDER_TEMPORARY_ERROR"
            run.state = apply(run.state, "fail", request_id)
        return self._publish(bundle, log, persist_result)

    def _advance(
        self,
        bundle: RunBundle,
        log: EventLog,
        request_id: str,
        event: str,
        stage: str,
    ) -> None:
        bundle.run.state = apply(bundle.run.state, event, request_id)
        self._stage(log, stage)

    def _stage(self, log: EventLog, name: str) -> None:
        if name in _PUBLIC_STAGES:
            log.emit("stage", name, {"stage": name})

    def _publish(
        self,
        bundle: RunBundle,
        log: EventLog,
        persist_result: Callable[[RunBundle], None] | None,
    ) -> RunBundle:
        run = bundle.run
        if persist_result is not None:
            try:
                persist_result(bundle)
            except Exception:
                run.answer_markdown = None
                bundle.claims, bundle.citations = [], []
                run.state, run.error_code = "failed", "PROVIDER_TEMPORARY_ERROR"
                raise
        if not is_terminal(run.state):
            return bundle
        if run.state == "answered":
            log.emit("token", "answered", {"text": run.answer_markdown})
            for citation in bundle.citations:
                log.emit("citation", "answered", {"citation_id": citation["id"]})
        log.emit(TERMINAL_EVENT[run.state], run.state, {"error_code": run.error_code})
        return bundle
