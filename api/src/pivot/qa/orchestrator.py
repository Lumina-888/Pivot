"""Execute the QA graph against a Run and EventLog."""

from __future__ import annotations

from pivot.qa.draft import draft_from_evidence
from pivot.qa.graph import MAX_CLARIFICATIONS, STAGES
from pivot.qa.ports import Classifier, RetrievalResult, Retriever, Verifier
from pivot.qa.verifier import CandidateVerifier, evidence_ids
from pivot.runs.machine import apply, is_terminal
from pivot.runs.models import RunBundle
from pivot.stream.buffer import EventLog

TERMINAL_EVENT = {
    "answered": "completed",
    "uncertain": "uncertain",
    "refused": "refused",
    "failed": "failed",
    "cancelled": "cancelled",
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
    ) -> None:
        self._retriever = retriever
        self._verifier = verifier or CandidateVerifier()
        self._classifier = classifier or AlwaysClearClassifier()

    def execute(self, bundle: RunBundle, log: EventLog, request_id: str) -> RunBundle:
        run = bundle.run
        if is_terminal(run.state):
            return bundle
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

    def resume(self, bundle: RunBundle, log: EventLog, reply: str, request_id: str) -> RunBundle:
        run = bundle.run
        run.question = f"{run.question} {reply}".strip()
        run.state = apply(run.state, "resume", request_id)
        run.state = apply(run.state, "retrieve", request_id)
        return self._retrieve_and_answer(bundle, log, request_id, from_planning=False)

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
            return self._emit_terminal(bundle, log)
        if result.status == "empty" or not result.evidence:
            run.state = apply(run.state, "refuse", request_id)
            return self._emit_terminal(bundle, log)
        if run.scope_type == "document" and run.scope_document_id:
            if any(hit.document_id != run.scope_document_id for hit in result.evidence):
                run.error_code = "RESOURCE_FORBIDDEN"
                run.state = apply(run.state, "fail", request_id)
                return self._emit_terminal(bundle, log)
        self._stage(log, "build_evidence")
        run.state = apply(run.state, "draft", request_id)
        self._stage(log, "draft_answer")
        markdown, claims, citations = draft_from_evidence(result.evidence)
        for claim in claims:
            log.emit("token", "drafting", {"text": claim["text"][:32]})
        for citation in citations:
            log.emit("citation", "drafting", {"citation_id": citation["id"]})
        run.state = apply(run.state, "verify", request_id)
        self._stage(log, "verify_claims")
        try:
            decision = self._verifier.verify(
                claims, citations, evidence_ids(result.evidence)
            )
        except Exception:
            log.emit("warning", "verify_claims", {"code": "VERIFICATION_UNAVAILABLE"})
            run.error_code = "VERIFICATION_UNAVAILABLE"
            run.state = apply(run.state, "uncertain", request_id)
            return self._emit_terminal(bundle, log)
        bundle.claims = claims  # type: ignore[assignment]
        bundle.citations = citations  # type: ignore[assignment]
        if decision == "answered":
            run.answer_markdown = markdown
            self._stage(log, "finalize")
            run.state = apply(run.state, "answer", request_id)
        else:
            self._stage(log, "refuse")
            event = "refuse" if decision == "refused" else "uncertain"
            run.state = apply(run.state, event, request_id)
        return self._emit_terminal(bundle, log)

    def _retrieve(self, run) -> RetrievalResult:
        return self._retriever.retrieve(
            run.question,
            scope_type=run.scope_type,
            scope_document_id=run.scope_document_id,
            principal_id=run.owner_id,
        )

    def _stage(self, log: EventLog, name: str) -> None:
        if name in STAGES or name == "refuse":
            log.emit("stage", name, {"stage": name})

    def _emit_terminal(self, bundle: RunBundle, log: EventLog) -> RunBundle:
        run = bundle.run
        log.emit(TERMINAL_EVENT[run.state], run.state, {"error_code": run.error_code})
        return bundle
