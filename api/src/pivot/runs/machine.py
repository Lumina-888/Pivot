"""Run state machine (SPEC §3.2)."""

from __future__ import annotations

from pivot.runs.errors import RunError

NON_TERMINAL = frozenset(
    {
        "received",
        "planning",
        "retrieving",
        "retrying",
        "drafting",
        "verifying",
        "waiting_for_user",
        "resuming",
    }
)
TERMINAL = frozenset({"answered", "uncertain", "refused", "failed", "cancelled"})
TRANSITIONS: dict[tuple[str, str], str] = {
    ("received", "plan"): "planning",
    ("planning", "retrieve"): "retrieving",
    ("planning", "clarify"): "waiting_for_user",
    ("planning", "fail"): "failed",
    ("retrieving", "draft"): "drafting",
    ("retrieving", "retry"): "retrying",
    ("retrieving", "fail"): "failed",
    ("retrieving", "refuse"): "refused",
    ("retrieving", "uncertain"): "uncertain",
    ("retrying", "retrieve"): "retrieving",
    ("retrying", "fail"): "failed",
    ("drafting", "verify"): "verifying",
    ("drafting", "fail"): "failed",
    ("verifying", "answer"): "answered",
    ("verifying", "uncertain"): "uncertain",
    ("verifying", "refuse"): "refused",
    ("verifying", "fail"): "failed",
    ("waiting_for_user", "resume"): "resuming",
    ("resuming", "retrieve"): "retrieving",
}


def apply(state: str, event: str, request_id: str) -> str:
    if state in TERMINAL:
        raise RunError("RESOURCE_FORBIDDEN", "终态不可改写", request_id)
    if event == "cancel":
        return "cancelled"
    nxt = TRANSITIONS.get((state, event))
    if nxt is None:
        raise RunError("RESOURCE_FORBIDDEN", f"{state} 不能响应 {event}", request_id)
    return nxt


def is_terminal(state: str) -> bool:
    return state in TERMINAL
