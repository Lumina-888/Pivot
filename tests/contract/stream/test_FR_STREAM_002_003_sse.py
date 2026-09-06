from __future__ import annotations

from fakes import ok_retriever
from pivot.qa.orchestrator import QaOrchestrator
from pivot.runs.service import RunService
from pivot.stream.events import TERMINAL_EVENTS


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
