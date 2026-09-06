"""SSE envelopes (SPEC §3.3 / sse.schema.json)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pivot.shared.time import utc_now

EVENT_TYPES = (
    "run_started",
    "stage",
    "token",
    "citation",
    "warning",
    "completed",
    "uncertain",
    "refused",
    "failed",
    "cancelled",
)
TERMINAL_EVENTS = frozenset({"completed", "uncertain", "refused", "failed", "cancelled"})
PUBLIC_STAGES = frozenset(
    {
        "normalize",
        "classify",
        "retrieve",
        "rerank",
        "build_evidence",
        "draft_answer",
        "verify_claims",
        "finalize",
        "refuse",
        "received",
        "planning",
        "retrieving",
        "drafting",
        "verifying",
        "answered",
        "uncertain",
        "refused",
        "failed",
        "cancelled",
        "waiting_for_user",
    }
)
FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {"system_prompt", "thinking", "thought", "tool_args", "secret", "api_key"}
)


def envelope(
    *,
    run_id: str,
    message_id: str,
    seq: int,
    stage: str,
    payload: dict[str, Any] | None = None,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    body = dict(payload or {})
    if FORBIDDEN_PAYLOAD_KEYS.intersection(body):
        raise ValueError("payload must not expose prompts, thinking, or secrets")
    ts = timestamp or utc_now()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return {
        "run_id": run_id,
        "message_id": message_id,
        "seq": seq,
        "timestamp": ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage": stage,
        "payload": body,
    }
