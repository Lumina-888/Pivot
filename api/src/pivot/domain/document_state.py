"""DocumentVersion state machine (SPEC §3.1, appendix C.3)."""

from __future__ import annotations

from pivot.documents.errors import illegal_state

STATES = frozenset(
    {
        "uploaded",
        "queued",
        "parsing",
        "chunking",
        "embedding",
        "indexed",
        "ready",
        "parse_failed",
        "embed_failed",
        "delete_pending",
        "deleted",
        "delete_failed",
    }
)

TRANSITIONS: dict[tuple[str, str], str] = {
    ("uploaded", "enqueue"): "queued",
    ("queued", "worker_started"): "parsing",
    ("parsing", "parse_ok"): "chunking",
    ("parsing", "parse_error"): "parse_failed",
    ("chunking", "chunk_ok"): "embedding",
    ("embedding", "embedding_ok"): "indexed",
    ("embedding", "embedding_error"): "embed_failed",
    ("indexed", "validation_ok"): "ready",
    ("ready", "delete_requested"): "delete_pending",
    ("delete_pending", "cleanup_ok"): "deleted",
    ("delete_pending", "cleanup_error"): "delete_failed",
    ("parse_failed", "retry"): "queued",
    ("embed_failed", "retry"): "queued",
    ("delete_failed", "retry_cleanup"): "delete_pending",
}

SEARCHABLE_STATES = frozenset({"ready"})
TERMINAL_FAILURE = frozenset({"parse_failed", "embed_failed"})


def next_state(current: str, event: str, request_id: str) -> str:
    if current == "deleted":
        raise illegal_state(request_id, "deleted 版本不可复活")
    nxt = TRANSITIONS.get((current, event))
    if nxt is None:
        raise illegal_state(request_id, f"{current} 不能响应 {event}")
    return nxt


def is_searchable(state: str, current: bool, deleted: bool) -> bool:
    return state in SEARCHABLE_STATES and current and not deleted
