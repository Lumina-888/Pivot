"""Execute the migration-baseline QA flow with fail-closed answer publication."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

from pivot.qa.draft import render_verified_claims
from pivot.qa.errors import WriterError
from pivot.qa.graph import MAX_CLARIFICATIONS, STAGES
from pivot.qa.ports import Classifier, DraftWriter, RetrievalResult, Retriever, Verifier
from pivot.qa.verifier import CandidateVerifier
from pivot.qa.writer import EvidenceJoinWriter
from pivot.runs.machine import apply, is_terminal
from pivot.runs.models import RunBundle
from pivot.stream.buffer import EventLog

TERMINAL_EVENT = {
    "answered": "completed", "uncertain": "uncertain", "refused": "refused",
    "failed": "failed", "cancelled": "cancelled",
}


class AlwaysClearClassifier:
    def needs_clarification(self, question: str, clarification_count: int) -> bool:
        return False


class ClarifyOnceClassifier:
    def needs_clarification(self, question: str, clarification_count: int) -> bool:
        return ("?" in question or "？" in question) and clarification_count < MAX_CLARIFICATIONS


class QaOrchestrator:
    def __init__(
        self,
        retriever: Retriever,
        verifier: Verifier | None = None,
        classifier: Classifier | None = None,
        writer: DraftWriter | None = None,
    ) -> None:
        self._retriever = retriever
        self._verifier = verifier
        self._classifier = classifier or AlwaysClearClassifier()
        self._writer = writer or EvidenceJoinWriter()

    def execute(
        self, bundle: RunBundle, log: EventLog, request_id: str, *,
        persist_result: Callable[[RunBundle], None] | None = None,
    ) -> RunBundle:
        if is_terminal(bundle.run.state):
            return bundle
        self._execute(bundle, log, request_id)
        return self._publish(bundle, log, persist_result)

    def _execute(self, bundle: RunBundle, log: EventLog, request_id: str) -> RunBundle:
        run = bundle.run
        log.emit("run_started", "received", {})
        run.state = apply(run.state, "plan", request_id)
        self._stage(log, "normalize")
        self._stage(log, "classify")
        if self._classifier.needs_clarification(run.question, run.clarification_count):
            run.clarification_count += 1
            run.state = apply(run.state, "clarify", request_id)
            log.emit("stage", "waiting_for_user", {"awaiting": "clarification"})
            return bundle
        return self._retrieve_and_answer(bundle, log, request_id, from_planning=True)

    def resume(
        self, bundle: RunBundle, log: EventLog, reply: str, request_id: str, *,
        persist_result: Callable[[RunBundle], None] | None = None,
    ) -> RunBundle:
        run = bundle.run
        run.question = f"{run.question} {reply}".strip()
        run.state = apply(run.state, "resume", request_id)
        run.state = apply(run.state, "retrieve", request_id)
        self._retrieve_and_answer(bundle, log, request_id, from_planning=False)
        return self._publish(bundle, log, persist_result)

    def _retrieve_and_answer(
        self, bundle: RunBundle, log: EventLog, request_id: str, from_planning: bool
    ) -> RunBundle:
        run = bundle.run
        if from_planning:
            run.state = apply(run.state, "retrieve", request_id)
        self._stage(log, "retrieve")
        result = self._retrieve(run)
        self._stage(log, "rerank")
        if result.status == "failed":
            run.error_code = result.error_code or "PROVIDER_TEMPORARY_ERROR"
            run.state = apply(run.state, "fail", request_id)
            return bundle
        if result.status == "empty" or not result.evidence:
            run.state = apply(run.state, "refuse", request_id)
            return bundle
        if run.scope_type == "document" and run.scope_document_id:
            if any(hit.document_id != run.scope_document_id for hit in result.evidence):
                run.error_code = "RESOURCE_FORBIDDEN"
                run.state = apply(run.state, "fail", request_id)
                return bundle
        self._stage(log, "build_evidence")
        run.state = apply(run.state, "draft", request_id)
        self._stage(log, "draft_answer")
        try:
            _preview, claims, citations = self._writer.draft(run.question, result.evidence)
        except WriterError as exc:
            run.error_code = exc.code
            if exc.code == "VERIFICATION_UNAVAILABLE":
                run.state = apply(run.state, "verify", request_id)
            event = (
                "refuse" if exc.code == "EXTERNAL_LLM_NOT_ALLOWED"
                else "uncertain" if exc.code == "VERIFICATION_UNAVAILABLE"
                else "fail"
            )
            run.state = apply(run.state, event, request_id)
            return bundle
        run.state = apply(run.state, "verify", request_id)
        self._stage(log, "verify_claims")
        try:
            decision = CandidateVerifier().verify(claims, citations, result.evidence)
            if decision == "answered" and self._verifier is not None:
                judge_claims, judge_citations = deepcopy(claims), deepcopy(citations)
                decision = self._verifier.verify(judge_claims, judge_citations, result.evidence)
                if (
                    type(decision) is not str
                    or decision not in {"answered", "uncertain", "refused"}
                    or judge_claims != claims or judge_citations != citations
                ):
                    raise ValueError("invalid verifier result")
        except Exception:
            log.emit("warning", "verify_claims", {"code": "VERIFICATION_UNAVAILABLE"})
            run.error_code = "VERIFICATION_UNAVAILABLE"
            run.state = apply(run.state, "uncertain", request_id)
            return bundle
        if decision == "answered":
            bundle.claims = claims
            bundle.citations = citations
            run.answer_markdown = render_verified_claims(claims)
            self._stage(log, "finalize")
            run.state = apply(run.state, "answer", request_id)
        else:
            self._stage(log, "refuse")
            event = "refuse" if decision == "refused" else "uncertain"
            run.state = apply(run.state, event, request_id)
        return bundle

    def _retrieve(self, run) -> RetrievalResult:
        return self._retriever.retrieve(
            run.question, scope_type=run.scope_type,
            scope_document_id=run.scope_document_id, principal_id=run.owner_id,
        )

    def _stage(self, log: EventLog, name: str) -> None:
        if name in STAGES or name == "refuse":
            log.emit("stage", name, {"stage": name})

    def _publish(
        self, bundle: RunBundle, log: EventLog,
        persist_result: Callable[[RunBundle], None] | None,
    ) -> RunBundle:
        run = bundle.run
        # Direct callers may use the in-memory fixture. HTTP supplies a commit boundary.
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
