from __future__ import annotations

import threading
import time

from fakes import ok_retriever
from pivot.qa.orchestrator import QaOrchestrator
from pivot.runs.service import RunService
from pivot.stream.buffer import EventLog
from pivot.stream.events import TERMINAL_EVENTS
from pivot.stream.sse import iter_sse_frames


def test_FR_STREAM_002_seq_monotonic_single_terminal():
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到怎么处理",
        idempotency_key="idem_1",
        request_id="req_1",
    )
    QaOrchestrator(ok_retriever()).execute(bundle, runs.log(bundle.run.id), "req_1")
    frames = runs.log(bundle.run.id).replay()
    seqs = [data["seq"] for _name, data in frames]
    assert seqs == list(range(1, len(seqs) + 1))
    terminals = [name for name, _data in frames if name in TERMINAL_EVENTS]
    assert len(terminals) == 1
    assert frames[-1][0] in TERMINAL_EVENTS
    for _name, data in frames:
        assert set(data) == {"run_id", "message_id", "seq", "timestamp", "stage", "payload"}
        assert data["run_id"] == bundle.run.id


def test_FR_STREAM_003_replays_after_last_event_id():
    runs = RunService()
    bundle = runs.create(
        conversation_id="conv_1",
        owner_id="usr_a",
        question="迟到怎么处理",
        idempotency_key="idem_1",
        request_id="req_1",
    )
    QaOrchestrator(ok_retriever()).execute(bundle, runs.log(bundle.run.id), "req_1")
    log = runs.log(bundle.run.id)
    replayed = log.replay(last_event_id=2)
    assert all(data["seq"] > 2 for _name, data in replayed)
    assert log.terminal is not None


def test_FR_STREAM_002_event_log_notifies_waiters():
    log = EventLog("run_wait", "msg_wait")
    seen: list[int] = []

    def waiter() -> None:
        frames = log.wait_after(0, timeout=1.0)
        seen.extend(int(data["seq"]) for _name, data in frames)

    thread = threading.Thread(target=waiter)
    thread.start()
    time.sleep(0.05)
    log.emit("run_started", "received", {})
    thread.join(timeout=1.0)
    assert not thread.is_alive()
    assert seen == [1]
    assert log.wait_after(1, timeout=0.05) == ()


def test_FR_STREAM_002_iter_sse_yields_before_terminal():
    log = EventLog("run_live", "msg_live")
    names: list[str] = []

    def produce() -> None:
        time.sleep(0.05)
        log.emit("run_started", "received", {})
        time.sleep(0.05)
        log.emit("completed", "answered", {})

    threading.Thread(target=produce, daemon=True).start()
    for chunk in iter_sse_frames(log, wait_timeout=0.2):
        if chunk.startswith(":"):
            continue
        for line in chunk.splitlines():
            if line.startswith("event:"):
                names.append(line.split(":", 1)[1].strip())
    assert names[0] == "run_started"
    assert names[-1] == "completed"
    assert names.count("completed") == 1
