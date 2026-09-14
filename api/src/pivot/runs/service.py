"""Run create/cancel/idempotency (FR-STREAM-001/004)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Protocol

from pivot.runs.errors import conflict, not_found
from pivot.runs.machine import apply, is_terminal
from pivot.runs.models import RunBundle, RunRecord, run_fingerprint
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now
from pivot.stream.buffer import EventLog


class RunStore(Protocol):
    def save(self, bundle: RunBundle, log: EventLog | None = None) -> None: ...

    def get(self, run_id: str) -> RunBundle | None: ...

    def get_by_idempotency(
        self, conversation_id: str, idempotency_key: str
    ) -> RunBundle | None: ...

    def list_for_conversation(self, conversation_id: str) -> tuple[RunBundle, ...]: ...

    def get_log(self, run_id: str, message_id: str) -> EventLog | None: ...


class InMemoryRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, RunBundle] = {}
        self._by_key: dict[tuple[str, str], str] = {}
        self._logs: dict[str, EventLog] = {}

    def save(self, bundle: RunBundle, log: EventLog | None = None) -> None:
        run = bundle.run
        self._runs[run.id] = bundle
        self._by_key[(run.conversation_id, run.idempotency_key)] = run.id
        if log is not None:
            self._logs[run.id] = log

    def get(self, run_id: str) -> RunBundle | None:
        return self._runs.get(run_id)

    def get_by_idempotency(self, conversation_id: str, idempotency_key: str) -> RunBundle | None:
        run_id = self._by_key.get((conversation_id, idempotency_key))
        if run_id is None:
            return None
        return self._runs.get(run_id)

    def list_for_conversation(self, conversation_id: str) -> tuple[RunBundle, ...]:
        items = [
            bundle
            for bundle in self._runs.values()
            if bundle.run.conversation_id == conversation_id
        ]
        items.sort(key=lambda bundle: bundle.run.created_at or datetime.min.replace(tzinfo=UTC))
        return tuple(items)

    def get_log(self, run_id: str, message_id: str) -> EventLog | None:
        return self._logs.get(run_id)


class RunService:
    def __init__(self, store: RunStore | None = None) -> None:
        self._store = store or InMemoryRunStore()
        self._runs: dict[str, RunBundle] = {}
        self._by_key: dict[tuple[str, str], str] = {}
        self.logs: dict[str, EventLog] = {}
        self._executing: set[str] = set()
        self._executing_lock = threading.Lock()

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
        fingerprint = run_fingerprint(question, scope_type, scope_document_id)
        existing = self._lookup_by_key(conversation_id, idempotency_key)
        if existing is not None:
            if existing.run.fingerprint != fingerprint:
                raise conflict(request_id)
            return existing
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
        log = EventLog(run.id, run.message_id)
        self._remember(bundle, log)
        self._store.save(bundle, log)
        return bundle

    def get(self, run_id: str, request_id: str) -> RunBundle:
        cached = self._runs.get(run_id)
        if cached is not None:
            return cached
        bundle = self._store.get(run_id)
        if bundle is None:
            raise not_found(request_id)
        self._remember(bundle, self._store.get_log(run_id, bundle.run.message_id))
        return bundle

    def list_for_conversation(self, conversation_id: str) -> tuple[RunBundle, ...]:
        items = self._store.list_for_conversation(conversation_id)
        for bundle in items:
            self._remember(bundle, self._store.get_log(bundle.run.id, bundle.run.message_id))
        return items

    def cancel(self, run_id: str, request_id: str) -> RunBundle:
        bundle = self.get(run_id, request_id)
        if is_terminal(bundle.run.state):
            return bundle
        bundle.run.state = apply(bundle.run.state, "cancel", request_id)
        log = self.log(run_id)
        if log.terminal is None:
            log.emit("cancelled", "cancelled", {})
        self.commit(bundle)
        return bundle

    def log(self, run_id: str) -> EventLog:
        cached = self.logs.get(run_id)
        if cached is not None:
            return cached
        bundle = self._runs.get(run_id) or self._store.get(run_id)
        if bundle is None:
            raise KeyError(run_id)
        log = self._store.get_log(run_id, bundle.run.message_id)
        if log is None:
            log = EventLog(run_id, bundle.run.message_id)
        self.logs[run_id] = log
        return log

    def begin_execution(self, run_id: str) -> bool:
        with self._executing_lock:
            if run_id in self._executing:
                return False
            log = self.logs.get(run_id)
            if log is not None and (log.terminal is not None or log.replay()):
                return False
            self._executing.add(run_id)
            return True

    def commit(self, bundle: RunBundle) -> None:
        self._remember(bundle, self.logs.get(bundle.run.id))
        self._store.save(bundle, self.logs.get(bundle.run.id))

    def _lookup_by_key(self, conversation_id: str, idempotency_key: str) -> RunBundle | None:
        cached_id = self._by_key.get((conversation_id, idempotency_key))
        if cached_id is not None:
            return self._runs.get(cached_id)
        bundle = self._store.get_by_idempotency(conversation_id, idempotency_key)
        if bundle is None:
            return None
        self._remember(bundle, self._store.get_log(bundle.run.id, bundle.run.message_id))
        return bundle

    def _remember(self, bundle: RunBundle, log: EventLog | None) -> None:
        self._runs[bundle.run.id] = bundle
        self._by_key[(bundle.run.conversation_id, bundle.run.idempotency_key)] = bundle.run.id
        if log is not None:
            self.logs[bundle.run.id] = log
