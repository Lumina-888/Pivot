"""Append-only audit recording, admin listing and QA replay (FR-AUDIT-001~003)."""

from __future__ import annotations

from typing import Any

from pivot.audit.catalog import canonicalize
from pivot.audit.errors import auth_forbidden, not_found
from pivot.audit.models import AuditEventRecord
from pivot.audit.ports import Actor, Clock
from pivot.audit.redaction import redact_metadata
from pivot.audit.store import AppendOnlyAuditStore
from pivot.shared.ids import new_id


class AuditService:
    def __init__(self, store: AppendOnlyAuditStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def record(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        result: str,
        request_id: str,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> AuditEventRecord:
        event = AuditEventRecord(
            id=new_id("audit"),
            actor=actor,
            action=canonicalize(action),
            target=target,
            result=result,
            request_id=request_id,
            run_id=run_id,
            metadata=redact_metadata(metadata),
            created_at=self._clock.now(),
        )
        self._store.append(event)
        return event

    def record_qa(
        self,
        *,
        actor: str,
        request_id: str,
        run_id: str,
        state: str,
        hit_documents: tuple[str, ...] | list[str],
        citations: tuple[str, ...] | list[str],
        model: str | None,
        prompt_version: str | None,
        role_card_version: str | None,
        retrieval_params: dict[str, Any] | None,
        index_generation: str | None,
        retry_count: int,
        duration_ms: int | None,
        result: str = "ok",
    ) -> AuditEventRecord:
        return self.record(
            actor=actor,
            action="qa.run",
            target=run_id,
            result=result,
            request_id=request_id,
            run_id=run_id,
            metadata={
                "state": state,
                "hit_documents": list(hit_documents),
                "citations": list(citations),
                "model": model,
                "prompt_version": prompt_version,
                "role_card_version": role_card_version,
                "retrieval_params": retrieval_params or {},
                "index_generation": index_generation,
                "retry_count": retry_count,
                "duration_ms": duration_ms,
            },
        )

    def list_events(
        self,
        actor: Actor,
        request_id: str,
        *,
        filter_actor: str | None = None,
        filter_action: str | None = None,
    ) -> dict[str, Any]:
        if actor.status != "active" or not actor.is_admin:
            raise auth_forbidden(request_id)
        self.record(
            actor=actor.user_id,
            action="admin.debug_access",
            target="audit-events",
            result="ok",
            request_id=request_id,
            metadata={"filter_actor": filter_actor, "filter_action": filter_action},
        )
        events = self._store.query(actor=filter_actor, action=filter_action)
        return {
            "items": [event.to_info() for event in events],
            "pagination": None,
        }

    def replay(
        self,
        actor: Actor,
        request_id: str,
        *,
        replay_request_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        if actor.status != "active" or not actor.is_admin:
            raise auth_forbidden(request_id)
        if not replay_request_id and not run_id:
            raise not_found(request_id)
        matches = self._store.query(request_id=replay_request_id, run_id=run_id)
        qa_events = [event for event in matches if event.action == "qa.run"]
        if not qa_events:
            raise not_found(request_id)
        event = qa_events[-1]
        metadata = event.metadata
        return {
            "request_id": event.request_id,
            "run_id": event.run_id,
            "actor": event.actor,
            "state": metadata.get("state"),
            "hit_documents": metadata.get("hit_documents") or [],
            "citations": metadata.get("citations") or [],
            "model": metadata.get("model"),
            "prompt_version": metadata.get("prompt_version"),
            "role_card_version": metadata.get("role_card_version"),
            "retrieval_params": metadata.get("retrieval_params") or {},
            "index_generation": metadata.get("index_generation"),
            "retry_count": metadata.get("retry_count"),
            "duration_ms": metadata.get("duration_ms"),
        }

    def events(self) -> tuple[AuditEventRecord, ...]:
        return self._store.list()
