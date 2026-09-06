"""契约测试：SSE 事件 schema（SPEC §3.3、§5.6）。

事件 JSON data 负载信封字段固定为 run_id/message_id/seq/timestamp/stage/payload；
事件名（SSE event: 行）与终态集合在 schema 的 x-* 扩展中声明，
顺序/唯一终态约束见 test_contract_sse_sequence.py。
"""

from conftest import validate

# SPEC §3.3 事件类型全集
EXPECTED_EVENT_TYPES = [
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
]

# SPEC §3.3：终态事件集合（终态最多一个）
EXPECTED_TERMINAL_EVENT_TYPES = ["completed", "uncertain", "refused", "failed", "cancelled"]

# SPEC §5.6 事件示例（data 负载）
EVENT_EXAMPLE = {
    "run_id": "run_001",
    "message_id": "msg_001",
    "seq": 17,
    "timestamp": "2026-09-06T08:00:00Z",
    "stage": "verifying",
    "payload": {},
}


def test_sse_schema_metadata(sse_schema):
    assert sse_schema["type"] == "object"
    assert sse_schema.get("$schema")
    assert "SSE" in sse_schema["title"] or "SSE" in sse_schema["description"]


def test_sse_envelope_required_fields(sse_schema):
    required = set(sse_schema.get("required", []))
    assert {"run_id", "message_id", "seq", "timestamp", "stage", "payload"} <= required


def test_sse_envelope_field_types(sse_schema):
    props = sse_schema["properties"]
    assert props["run_id"]["type"] == "string"
    assert props["message_id"]["type"] == "string"
    assert props["seq"]["type"] == "integer"
    assert props["seq"].get("minimum", 0) >= 1, "seq 从 1 起且单调递增"
    assert props["timestamp"]["type"] == "string"
    assert props["timestamp"].get("format") == "date-time"
    assert props["payload"]["type"] == "object"


def test_sse_event_types_machine_readable(sse_schema):
    """事件名以 x-event-types 暴露给序列测试与消费者。"""
    assert sse_schema["x-event-types"] == EXPECTED_EVENT_TYPES


def test_sse_terminal_event_types_machine_readable(sse_schema):
    assert sse_schema["x-terminal-event-types"] == EXPECTED_TERMINAL_EVENT_TYPES


def test_sse_example_from_spec_validates(sse_schema):
    validate(EVENT_EXAMPLE, sse_schema)


def test_sse_unknown_envelope_field_rejected(sse_schema):
    import pytest

    bad = dict(EVENT_EXAMPLE, event="completed")
    with pytest.raises(Exception):
        validate(bad, sse_schema)


def test_sse_missing_required_field_rejected(sse_schema):
    import pytest

    bad = {k: v for k, v in EVENT_EXAMPLE.items() if k != "seq"}
    with pytest.raises(Exception):
        validate(bad, sse_schema)
