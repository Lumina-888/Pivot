"""Run create/cancel/idempotency (FR-STREAM-001/004)."""

from __future__ import annotations

import hashlib

from pivot.runs.errors import conflict, not_found
from pivot.runs.machine import apply, is_terminal
from pivot.runs.models import RunBundle, RunRecord
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now
from pivot.stream.buffer import EventLog


class RunService:
    def __init__(self) -> None:
        self._runs: dict[str, RunBundle] = {}
        self._by_key: dict[tuple[str, str], str] = {}
        self.logs: dict[str, EventLog] = {}

    def create(
        self,
        *,
        conversation_id: str,
        owner_id: str,
        question: str,
        idempotency_key: str,
        request_id: str,
        scope_type: str = "global",
        scope_document_id: str | None = None,
    ) -> RunBundle:
        fingerprint = _fingerprint(question, scope_type, scope_document_id)
        existing_id = self._by_key.get((conversation_id, idempotency_key))
        if existing_id:
            bundle = self._runs[existing_id]
            if bundle.run.fingerprint != fingerprint:
                raise conflict(request_id)
            return bundle
        run = RunRecord(
            id=new_id("run"),
            conversation_id=conversation_id,
            message_id=new_id("message"),
            owner_id=owner_id,
            question=question,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            scope_type=scope_type,
            scope_document_id=scope_document_id,
            created_at=utc_now(),
        )
        bundle = RunBundle(run=run)
        self._runs[run.id] = bundle
        self._by_key[(conversation_id, idempotency_key)] = run.id
        self.logs[run.id] = EventLog(run.id, run.message_id)
        return bundle

    def get(self, run_id: str, request_id: str) -> RunBundle:
        bundle = self._runs.get(run_id)
        if bundle is None:
            raise not_found(request_id)
        return bundle

    def cancel(self, run_id: str, request_id: str) -> RunBundle:
        bundle = self.get(run_id, request_id)
        if is_terminal(bundle.run.state):
            return bundle
        bundle.run.state = apply(bundle.run.state, "cancel", request_id)
        log = self.logs[run_id]
        if log.terminal is None:
            log.emit("cancelled", "cancelled", {})
        return bundle

    def log(self, run_id: str) -> EventLog:
        return self.logs[run_id]


def _fingerprint(question: str, scope_type: str, scope_document_id: str | None) -> str:
    raw = f"{question}|{scope_type}|{scope_document_id or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
