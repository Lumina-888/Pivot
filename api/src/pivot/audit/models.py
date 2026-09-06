"""Audit event and provider-call views (SPEC §2.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pivot.exports.models import format_utc


@dataclass(frozen=True)
class AuditEventRecord:
    id: str
    actor: str
    action: str
    target: str
    result: str
    request_id: str | None
    run_id: str | None
    metadata: dict[str, Any]
    created_at: datetime

    def to_info(self) -> dict[str, Any]:
        return {
            "audit_event_id": self.id,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "result": self.result,
            "request_id": self.request_id,
            "run_id": self.run_id,
            "metadata": dict(self.metadata),
            "created_at": format_utc(self.created_at),
        }


@dataclass(frozen=True)
class ProviderCallRecord:
    id: str
    provider: str
    model: str
    operation: str
    status: str
    request_id: str | None = None
    run_id: str | None = None
    tokens: int | None = None
    latency_ms: int | None = None
    retry_count: int = 0
    estimated_cost: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)
