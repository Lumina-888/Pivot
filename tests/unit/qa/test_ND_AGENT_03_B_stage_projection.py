"""ND-AGENT-03-B: 内部图节点到公开 Run/SSE 阶段的投影。"""

from __future__ import annotations

import pytest
from pivot.qa.agent_projection import (
    PUBLIC_STAGES,
    is_public_stage_allowed,
    project_stage,
    should_emit_draft_content,
)
from pivot.stream.buffer import EventLog
from pivot.stream.events import PUBLIC_STAGES as SSE_PUBLIC_STAGES


def test_FR_AGENT_008_agent_tools_loop_stays_retrieving():
    nodes = ["agent", "tool_guard", "tools", "execute_tools", "observation_guard"]
    assert {project_stage(node) for node in nodes} == {"retrieving"}


def test_FR_AGENT_008_repair_returns_to_retrieving():
    assert project_stage("verify") == "verifying"
    assert project_stage("repair_feedback") == "retrieving"
    assert "repair_feedback" not in PUBLIC_STAGES


def test_FR_AGENT_008_public_events_hide_internal_messages():
    log = EventLog("run-1", "msg-1")
    for node in ("agent", "tools", "observation_guard"):
        log.emit("stage", project_stage(node), {"stage": project_stage(node)})
    events = log.replay()
    assert [item[1]["stage"] for item in events] == ["retrieving"] * 3
    assert all("tool_args" not in item[1]["payload"] for item in events)
    with pytest.raises(ValueError, match="prompts|thinking|secrets"):
        log.emit("stage", "retrieving", {"thinking": "hidden"})


def test_FR_AGENT_008_draft_not_published_before_verification():
    assert project_stage("structured_finalize") == "verifying"
    assert should_emit_draft_content("verifying", verified=False) is False
    assert should_emit_draft_content("verifying", verified=True) is False


def test_FR_AGENT_008_verified_answer_sends_token_citation():
    assert should_emit_draft_content("answered", verified=True) is True
    assert should_emit_draft_content("answered", verified=False) is False
    log = EventLog("run-1", "msg-1")
    log.emit("stage", "verifying", {"stage": "verifying"})
    if should_emit_draft_content("answered", verified=True):
        log.emit("token", "answered", {"text": "已校验答案"})
        log.emit("citation", "answered", {"citation_id": "cit-1"})
        log.emit("completed", "answered", {"error_code": None})
    names = [name for name, _data in log.replay()]
    assert names == ["stage", "token", "citation", "completed"]


def test_FR_STREAM_002_terminal_event_unique():
    log = EventLog("run-1", "msg-1")
    log.emit("completed", "answered", {})
    with pytest.raises(ValueError, match="terminal"):
        log.emit("completed", "answered", {})
    assert [item[1]["seq"] for item in log.replay()] == [1]


def test_FR_STREAM_003_reconnect_does_not_execute_agent():
    log = EventLog("run-1", "msg-1")
    log.emit("stage", project_stage("tools"), {"stage": "retrieving"})
    log.emit("completed", "answered", {})
    replay = log.replay(last_event_id=1)
    assert [item[0] for item in replay] == ["completed"]
    assert log.replay(last_event_id=2) == ()


def test_stage_projection_maps_internal_to_public():
    mapping = {
        "input_guard": "planning",
        "agent": "retrieving",
        "structured_finalize": "verifying",
        "clarify": "waiting_for_user",
        "authorized_resume": "resuming",
        "persist_result": "answered",
    }
    for internal, public in mapping.items():
        assert project_stage(internal) == public
        assert public in PUBLIC_STAGES
        assert public in SSE_PUBLIC_STAGES or public in {"planning", "resuming"}


def test_forbidden_stages_rejected():
    with pytest.raises(ValueError, match="not public"):
        project_stage("raw_langgraph_event")
    assert is_public_stage_allowed("retrieving") is True
    assert is_public_stage_allowed("agent") is False
    with pytest.raises(ValueError, match="not public"):
        project_stage("persist_result", is_terminal=True, terminal_state="agent")
