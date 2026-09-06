"""契约测试：SSE 序列约束（SPEC §3.3、FR-STREAM-002/003）。

单条 schema 无法表达跨事件约束，此处用事件序列纯函数验证：
- seq 在一个 Run 内单调递增（严格递增）；
- 终态事件最多一个，且一旦出现即为该 Run 最后一条；
- 断线后按 Last-Event-ID 补发：仅补发 seq 大于 last_event_id 的事件，无重复。

这些函数同时也是消费者（M05/M08/M11）可复用的序列校验工具。
"""

from conftest import validate
from test_contract_sse_schema import EXPECTED_TERMINAL_EVENT_TYPES


def _event(seq, stage="retrieving"):
    return {
        "run_id": "run_001",
        "message_id": "msg_001",
        "seq": seq,
        "timestamp": "2026-09-06T08:00:00Z",
        "stage": stage,
        "payload": {},
    }


def seq_violations(events, schema):
    """返回事件序列的约束违规描述列表；空列表表示序列合法。

    规则（SPEC §3.3）：
    1. 每条事件必须满足 sse.schema.json；
    2. seq 严格递增；
    3. 终态事件最多一个且必须是最后一条。
    """
    violations = []
    last_seq = None
    terminal_seen = False
    for event in events:
        try:
            validate(event, schema)
        except Exception as exc:  # noqa: BLE001
            violations.append(f"事件不符合 schema：{exc}")
            continue
        seq = event["seq"]
        if last_seq is not None and seq <= last_seq:
            violations.append(f"seq 必须严格递增：{last_seq} -> {seq}")
        last_seq = seq
        if terminal_seen:
            violations.append(f"终态事件后出现新事件（seq={seq}）")
        if event["stage"] in EXPECTED_TERMINAL_EVENT_TYPES:
            if terminal_seen:
                violations.append(f"终态事件多于一个（seq={seq}）")
            terminal_seen = True
    return violations


def valid_sequence():
    return [_event(1, "planning"), _event(2), _event(3, "drafting"), _event(4, "verifying"), _event(5, "completed")]


def resume_events(events, last_event_id):
    """Last-Event-ID 补发语义（SPEC §3.3、FR-STREAM-003）：仅补发 seq > last_event_id。"""
    return [e for e in events if e["seq"] > last_event_id]


def test_sequence_valid_when_increasing_with_single_terminal_last(sse_schema):
    assert seq_violations(valid_sequence(), sse_schema) == []


def test_sequence_rejects_duplicate_seq(sse_schema):
    events = [_event(1), _event(1)]
    assert any("严格递增" in v for v in seq_violations(events, sse_schema))


def test_sequence_rejects_decreasing_seq(sse_schema):
    events = [_event(2), _event(1)]
    assert any("严格递增" in v for v in seq_violations(events, sse_schema))


def test_sequence_rejects_two_terminal_events(sse_schema):
    events = [_event(1), _event(2, "completed"), _event(3, "failed")]
    assert any("多于一个" in v for v in seq_violations(events, sse_schema))


def test_sequence_rejects_event_after_terminal(sse_schema):
    events = [_event(1, "completed"), _event(2, "drafting")]
    assert any("终态事件后" in v for v in seq_violations(events, sse_schema))


def test_sequence_rejects_schema_violation(sse_schema):
    events = [{**_event(1), "seq": "not-an-int"}]
    assert any("schema" in v for v in seq_violations(events, sse_schema))


def test_last_event_id_resume_without_duplicates(sse_schema):
    events = valid_sequence()  # seq 1..5，终态 completed 在最后
    resent = resume_events(events, last_event_id=3)
    assert [e["seq"] for e in resent] == [4, 5]
    assert seq_violations(resent, sse_schema) == []


def test_last_event_id_full_replay_from_zero(sse_schema):
    events = valid_sequence()
    resent = resume_events(events, last_event_id=0)
    assert [e["seq"] for e in resent] == [1, 2, 3, 4, 5]
    assert seq_violations(resent, sse_schema) == []


def test_last_event_id_equals_terminal_returns_empty(sse_schema):
    events = valid_sequence()
    assert resume_events(events, last_event_id=5) == []


def test_last_event_id_before_reconnect_prefix_keeps_terminal(sse_schema):
    """断线发生在终态之前时，补发序列必须仍以终态收尾。"""
    events = valid_sequence()
    resent = resume_events(events, last_event_id=2)
    assert resent[-1]["stage"] == "completed"
    assert seq_violations(resent, sse_schema) == []
