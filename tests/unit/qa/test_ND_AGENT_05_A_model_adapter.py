"""ND-AGENT-05-A: Agent model adapter injection, fallback and attempts.

All transports are fakes; no network is touched. The adapter must take
its endpoint, model and key purely from injected settings (ADR-011), it
must preserve tool results and assistant tool calls when converting
messages, it must switch to the fallback model only on retryable
failures (timeout, 429, 5xx), and it must report every attempt through
the injected sink with usage or an explicit unknown.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pivot.qa.agent_model import (
    AgentModel,
    AgentModelConfig,
    AgentModelSettings,
    FallbackAgentModel,
    classify_model_error,
    is_retryable_error,
)


class _StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code


class _FakeTransport:
    def __init__(self, *script) -> None:
        self._script = list(script)
        self.calls: list[tuple[list, list]] = []

    def invoke(self, messages, tools):
        self.calls.append((messages, tools))
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _config(model: str = "deepseek-flash", **overrides) -> AgentModelConfig:
    values = {"model": model, "api_key": "test-key", "base_url": "https://example.test/v1"}
    values.update(overrides)
    return AgentModelConfig(**values)


def _ai(content: str = "ok", **kwargs) -> AIMessage:
    return AIMessage(content=content, **kwargs)


# --- configuration -------------------------------------------------------


def test_ND_AGENT_05_A_config_rejects_empty_model_or_key():
    with pytest.raises(ValueError):
        _config(model="")
    with pytest.raises(ValueError):
        _config(api_key="")


def test_ND_AGENT_05_A_settings_require_the_primary_trio():
    with pytest.raises(RuntimeError):
        AgentModelSettings.from_env({})
    with pytest.raises(RuntimeError) as excinfo:
        AgentModelSettings.from_env({"PIVOT_AGENT_MODEL_MODEL": "deepseek-flash"})
    assert "PIVOT_AGENT_MODEL_API_KEY" in str(excinfo.value)


def test_ND_AGENT_05_A_settings_build_primary_and_fallback():
    env = {
        "PIVOT_AGENT_MODEL_ENDPOINT": "https://example.test/v1",
        "PIVOT_AGENT_MODEL_MODEL": "deepseek-flash",
        "PIVOT_AGENT_MODEL_API_KEY": "k1",
        "PIVOT_AGENT_MODEL_FALLBACK_ENDPOINT": "https://fallback.test/v1",
        "PIVOT_AGENT_MODEL_FALLBACK_MODEL": "mimo-v2.6",
        "PIVOT_AGENT_MODEL_FALLBACK_API_KEY": "k2",
    }
    settings = AgentModelSettings.from_env(env)
    assert settings.primary.model == "deepseek-flash"
    assert settings.primary.role == "primary"
    assert settings.fallback is not None
    assert settings.fallback.model == "mimo-v2.6"
    assert settings.fallback.role == "fallback"
    with pytest.raises(RuntimeError):
        AgentModelSettings.from_env(
            {**env, "PIVOT_AGENT_MODEL_FALLBACK_MODEL": ""}
        )
    with pytest.raises(RuntimeError):
        AgentModelSettings.from_env(
            {**env, "PIVOT_AGENT_MODEL_TIMEOUT_SECONDS": "abc"}
        )


def test_ND_AGENT_05_A_default_transport_disables_silent_retries(monkeypatch):
    captured: dict = {}

    class _Chat:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            return _ai()

    monkeypatch.setattr("pivot.qa.agent_model.ChatOpenAI", _Chat)
    model = AgentModel(_config(timeout_seconds=12.5))
    model.decide(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert captured["model"] == "deepseek-flash"
    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "https://example.test/v1"
    assert captured["request_timeout"] == 12.5
    assert captured["max_retries"] == 0


# --- message conversion ----------------------------------------------------


def test_ND_AGENT_05_A_decide_preserves_tool_results_and_tool_calls():
    transport = _FakeTransport(_ai())
    model = AgentModel(_config(), transport=transport)
    model.decide(
        messages=[
            {"role": "system", "content": "rules"},
            {"role": "user", "content": "考勤制度是什么"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_1", "name": "search_knowledge", "args": {"query": "考勤"}}
                ],
            },
            {"role": "tool", "content": "证据正文", "tool_call_id": "call_1"},
        ],
        tools=[{"type": "function", "function": {"name": "search_knowledge"}}],
    )
    (messages, _tools), = transport.calls
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert isinstance(messages[2], AIMessage)
    assert messages[2].tool_calls[0]["id"] == "call_1"
    assert messages[2].tool_calls[0]["name"] == "search_knowledge"
    assert isinstance(messages[3], ToolMessage)
    assert messages[3].tool_call_id == "call_1"
    assert messages[3].content == "证据正文"


def test_ND_AGENT_05_A_decide_rejects_non_ai_transport_result():
    model = AgentModel(_config(), transport=_FakeTransport("not-a-message"))
    with pytest.raises(TypeError):
        model.decide(messages=[{"role": "user", "content": "hi"}], tools=[])


# --- attempt accounting ------------------------------------------------------


def test_ND_AGENT_05_A_attempt_sink_records_usage_or_unknown():
    records: list[dict] = []
    usage = {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}
    model = AgentModel(
        _config(),
        transport=_FakeTransport(_ai(usage_metadata=usage)),
        attempt_sink=records.append,
    )
    model.decide(messages=[{"role": "user", "content": "hi"}], tools=[])
    (record,) = records
    assert record["role"] == "primary"
    assert record["model"] == "deepseek-flash"
    assert record["outcome"] == "success"
    assert record["usage"] == {"input_tokens": 11, "output_tokens": 7}
    assert record["error_kind"] is None

    records.clear()
    model = AgentModel(
        _config(), transport=_FakeTransport(_ai()), attempt_sink=records.append
    )
    model.decide(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert records[0]["usage"] is None


def test_ND_AGENT_05_A_attempt_sink_records_errors_and_reraises():
    records: list[dict] = []
    model = AgentModel(
        _config(),
        transport=_FakeTransport(_StatusError(503)),
        attempt_sink=records.append,
    )
    with pytest.raises(_StatusError):
        model.decide(messages=[{"role": "user", "content": "hi"}], tools=[])
    (record,) = records
    assert record["outcome"] == "error"
    assert record["error_kind"] == "server"
    assert record["usage"] is None


# --- error classification and fallback --------------------------------------


def test_ND_AGENT_05_A_error_classification():
    assert classify_model_error(TimeoutError("slow")) == "timeout"
    assert classify_model_error(_StatusError(429)) == "rate_limit"
    assert classify_model_error(_StatusError(500)) == "server"
    assert classify_model_error(_StatusError(401)) == "client"
    assert classify_model_error(RuntimeError("boom")) == "unknown"
    assert is_retryable_error(_StatusError(429))
    assert is_retryable_error(_StatusError(503))
    assert is_retryable_error(TimeoutError("slow"))
    assert not is_retryable_error(_StatusError(400))
    assert not is_retryable_error(RuntimeError("boom"))


def test_ND_AGENT_05_A_fallback_switches_only_on_retryable_errors():
    records: list[dict] = []
    primary = AgentModel(
        _config(), transport=_FakeTransport(_StatusError(429)), attempt_sink=records.append
    )
    fallback = AgentModel(
        _config(model="mimo-v2.6", role="fallback"),
        transport=_FakeTransport(_ai("from-fallback")),
        attempt_sink=records.append,
    )
    model = FallbackAgentModel(primary, fallback)
    response = model.decide(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert response.content == "from-fallback"
    assert [r["role"] for r in records] == ["primary", "fallback"]
    assert records[0]["outcome"] == "error"
    assert records[1]["outcome"] == "success"


def test_ND_AGENT_05_A_fallback_not_used_for_client_errors():
    fallback_transport = _FakeTransport(_ai("unused"))
    model = FallbackAgentModel(
        AgentModel(_config(), transport=_FakeTransport(_StatusError(400))),
        AgentModel(
            _config(model="mimo-v2.6", role="fallback"), transport=fallback_transport
        ),
    )
    with pytest.raises(_StatusError):
        model.decide(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert fallback_transport.calls == []


def test_ND_AGENT_05_A_fallback_failure_propagates():
    model = FallbackAgentModel(
        AgentModel(_config(), transport=_FakeTransport(_StatusError(503))),
        AgentModel(
            _config(model="mimo-v2.6", role="fallback"),
            transport=_FakeTransport(_StatusError(500)),
        ),
    )
    with pytest.raises(_StatusError) as excinfo:
        model.decide(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert excinfo.value.status_code == 500


def test_ND_AGENT_05_A_settings_build_returns_fallback_wrapper():
    env = {
        "PIVOT_AGENT_MODEL_ENDPOINT": "https://example.test/v1",
        "PIVOT_AGENT_MODEL_MODEL": "deepseek-flash",
        "PIVOT_AGENT_MODEL_API_KEY": "k1",
        "PIVOT_AGENT_MODEL_FALLBACK_ENDPOINT": "https://fallback.test/v1",
        "PIVOT_AGENT_MODEL_FALLBACK_MODEL": "mimo-v2.6",
        "PIVOT_AGENT_MODEL_FALLBACK_API_KEY": "k2",
    }
    settings = AgentModelSettings.from_env(env)
    primary_only = AgentModelSettings.from_env(
        {k: v for k, v in env.items() if "FALLBACK" not in k}
    ).build(transport=_FakeTransport(_ai()))
    assert isinstance(primary_only, AgentModel)
    wrapped = settings.build(
        transport=_FakeTransport(_ai()), fallback_transport=_FakeTransport(_ai())
    )
    assert isinstance(wrapped, FallbackAgentModel)
