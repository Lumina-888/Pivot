"""SSE framing and long-lived generators. Keepalive interval is not a frozen TBD-P0."""

from __future__ import annotations

import json
from collections.abc import Iterator

from pivot.stream.buffer import EventLog
from pivot.stream.events import TERMINAL_EVENTS

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def format_sse_frame(name: str, data: dict[str, object]) -> str:
    return (
        f"id: {data['seq']}\n"
        f"event: {name}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )


def iter_sse_frames(
    log: EventLog,
    *,
    last_event_id: int | None = None,
    wait_timeout: float = 1.0,
) -> Iterator[str]:
    cursor = 0 if last_event_id is None else last_event_id
    while True:
        frames = log.replay(last_event_id=cursor)
        if frames:
            for name, data in frames:
                cursor = int(data["seq"])
                yield format_sse_frame(name, data)
                if name in TERMINAL_EVENTS:
                    return
            continue
        if log.terminal is not None:
            return
        arrived = log.wait_after(cursor, timeout=wait_timeout)
        if arrived:
            continue
        if log.terminal is not None:
            return
        yield ": keepalive\n\n"
