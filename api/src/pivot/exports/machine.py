"""ExportTask state machine (SPEC §3.5, appendix C.5)."""

from __future__ import annotations

from pivot.exports.errors import ExportError

STATES = ("requested", "queued", "generating", "ready", "failed", "expired")

_TRANSITIONS: dict[tuple[str, str], str] = {
    ("requested", "queue"): "queued",
    ("queued", "generate"): "generating",
    ("queued", "fail"): "failed",
    ("generating", "succeed"): "ready",
    ("generating", "fail"): "failed",
    ("ready", "expire"): "expired",
}


def apply(state: str, event: str, request_id: str) -> str:
    nxt = _TRANSITIONS.get((state, event))
    if nxt is None:
        raise ExportError(
            "RESOURCE_FORBIDDEN",
            f"非法导出状态转移: {state} + {event}",
            request_id,
        )
    return nxt


def is_downloadable(state: str) -> bool:
    return state == "ready"
