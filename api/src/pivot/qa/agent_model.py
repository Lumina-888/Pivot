"""Agent 模型适配器（ND-AGENT-05-A）

按 ADR-011 的选型提供原生工具调用模型。endpoint、model 与 api_key
全部经注入配置进入，不设源码默认值；未配置完整即在构建时失败。

每次调用都经 attempt_sink 上报一条尝试记录，形状为：role（primary
或 fallback）、model、outcome（success 或 error）、usage（input 与
output token 数，未知时为 None）、error_kind 与 latency_ms。该记录
是收费模型调用的统一记账接缝：决策调用先行接入，其他收费调用
（收尾、重写）后续按同一形状上报。供应商返回的用量缺失时记为
None（明确未知），不记零。

主备切换只发生在可重试失败：超时、429 与 5xx。其余失败直接抛出，
不静默切换，不回退到旧线性实现（AGENT-INTERNAL-0.1.0）。
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI

AttemptSink = Callable[[dict[str, Any]], None]

_PRIMARY_ENV = (
    "PIVOT_AGENT_MODEL_ENDPOINT",
    "PIVOT_AGENT_MODEL_MODEL",
    "PIVOT_AGENT_MODEL_API_KEY",
)
_FALLBACK_ENV = (
    "PIVOT_AGENT_MODEL_FALLBACK_ENDPOINT",
    "PIVOT_AGENT_MODEL_FALLBACK_MODEL",
    "PIVOT_AGENT_MODEL_FALLBACK_API_KEY",
)
_TIMEOUT_ENV = "PIVOT_AGENT_MODEL_TIMEOUT_SECONDS"
_DEFAULT_TIMEOUT_SECONDS = 60.0


def classify_model_error(exc: BaseException) -> str:
    """Classify a provider failure for fallback and reporting."""
    if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower():
        return "timeout"
    status = getattr(exc, "status_code", None)
    if not isinstance(status, int):
        status = getattr(exc, "status", None)
    if isinstance(status, int):
        if status == 429:
            return "rate_limit"
        if status >= 500:
            return "server"
        if status >= 400:
            return "client"
    if "ratelimit" in type(exc).__name__.lower().replace("_", ""):
        return "rate_limit"
    return "unknown"


def is_retryable_error(exc: BaseException) -> bool:
    """Only timeouts, rate limits and server failures may switch models."""
    return classify_model_error(exc) in {"timeout", "rate_limit", "server"}


@dataclass(frozen=True)
class AgentModelConfig:
    """One injected model endpoint. No field carries a code default."""

    model: str
    api_key: str
    base_url: str | None = None
    temperature: float = 0.0
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    role: str = "primary"

    def __post_init__(self) -> None:
        if not self.model or not self.model.strip():
            raise ValueError("agent model name must be injected, not defaulted")
        if not self.api_key or not self.api_key.strip():
            raise ValueError("agent model api_key must be injected, not defaulted")
        if self.timeout_seconds <= 0:
            raise ValueError("agent model timeout_seconds must be positive")


class ModelTransport(Protocol):
    def invoke(self, messages: list[BaseMessage], tools: list[dict[str, Any]]): ...


class _ChatOpenAITransport:
    """Default transport: ChatOpenAI with silent SDK retries disabled."""

    def __init__(self, config: AgentModelConfig) -> None:
        kwargs: dict[str, Any] = {
            "model": config.model,
            "temperature": config.temperature,
            "api_key": config.api_key,
            "request_timeout": config.timeout_seconds,
            "max_retries": 0,
        }
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._chat = ChatOpenAI(**kwargs)

    def invoke(self, messages: list[BaseMessage], tools: list[dict[str, Any]]):
        bound = self._chat.bind_tools(tools) if tools else self._chat
        return bound.invoke(messages)


def _convert_message(msg: dict[str, Any]) -> BaseMessage | None:
    role = msg.get("role") or msg.get("type")
    content = msg.get("content", "")
    if role in ("user", "human"):
        return HumanMessage(content=content)
    if role == "system":
        return SystemMessage(content=content)
    if role in ("assistant", "ai"):
        tool_calls = [
            {
                "name": call.get("name", ""),
                "args": call.get("args") or {},
                "id": call.get("id") or "",
                "type": "tool_call",
            }
            for call in msg.get("tool_calls") or []
        ]
        return AIMessage(content=content, tool_calls=tool_calls)
    if role == "tool":
        return ToolMessage(content=content, tool_call_id=msg.get("tool_call_id") or "")
    return None


def _usage_of(response: AIMessage) -> dict[str, int] | None:
    usage = getattr(response, "usage_metadata", None)
    if not isinstance(usage, dict):
        return None
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if (
        type(input_tokens) is not int
        or type(output_tokens) is not int
        or input_tokens < 0
        or output_tokens < 0
    ):
        return None
    return {"input_tokens": input_tokens, "output_tokens": output_tokens}


class AgentModel:
    """One configured model endpoint speaking the decide protocol."""

    def __init__(
        self,
        config: AgentModelConfig,
        *,
        transport: ModelTransport | None = None,
        attempt_sink: AttemptSink | None = None,
    ) -> None:
        self.config = config
        self._transport = transport or _ChatOpenAITransport(config)
        self._attempt_sink = attempt_sink

    def decide(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AIMessage:
        converted = [
            message
            for message in (_convert_message(item) for item in messages)
            if message is not None
        ]
        started = time.monotonic()
        try:
            response = self._transport.invoke(converted, tools)
        except Exception as exc:
            self._record(started, outcome="error", usage=None, error_kind=classify_model_error(exc))
            raise
        if not isinstance(response, AIMessage):
            self._record(started, outcome="error", usage=None, error_kind="invalid_response")
            raise TypeError(f"Expected AIMessage, got {type(response)}")
        self._record(started, outcome="success", usage=_usage_of(response), error_kind=None)
        return response

    def _record(
        self,
        started: float,
        *,
        outcome: str,
        usage: dict[str, int] | None,
        error_kind: str | None,
    ) -> None:
        if self._attempt_sink is None:
            return
        self._attempt_sink(
            {
                "role": self.config.role,
                "model": self.config.model,
                "outcome": outcome,
                "usage": usage,
                "error_kind": error_kind,
                "latency_ms": int((time.monotonic() - started) * 1000),
            }
        )


class FallbackAgentModel:
    """Primary model with a fallback used only on retryable failures."""

    def __init__(self, primary: AgentModel, fallback: AgentModel) -> None:
        self.primary = primary
        self.fallback = fallback

    def decide(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AIMessage:
        try:
            return self.primary.decide(messages, tools)
        except Exception as exc:
            if not is_retryable_error(exc):
                raise
            return self.fallback.decide(messages, tools)


@dataclass(frozen=True)
class AgentModelSettings:
    """Injected agent model settings, mirroring the PIVOT_LLM_* rules."""

    primary: AgentModelConfig
    fallback: AgentModelConfig | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> AgentModelSettings:
        source: Mapping[str, str] = os.environ if env is None else env

        def _get(name: str) -> str | None:
            value = source.get(name)
            if value is None:
                return None
            value = value.strip()
            return value or None

        timeout_seconds = _DEFAULT_TIMEOUT_SECONDS
        raw_timeout = _get(_TIMEOUT_ENV)
        if raw_timeout is not None:
            try:
                timeout_seconds = float(raw_timeout)
            except ValueError as exc:
                raise RuntimeError(f"{_TIMEOUT_ENV} must be a number") from exc
            if timeout_seconds <= 0:
                raise RuntimeError(f"{_TIMEOUT_ENV} must be positive")

        primary_values = {name: _get(name) for name in _PRIMARY_ENV}
        missing = [name for name, value in primary_values.items() if value is None]
        if missing:
            raise RuntimeError(
                "agent model settings are incomplete; missing " + ", ".join(missing)
            )
        primary = AgentModelConfig(
            primary_values["PIVOT_AGENT_MODEL_MODEL"] or "",
            primary_values["PIVOT_AGENT_MODEL_API_KEY"] or "",
            primary_values["PIVOT_AGENT_MODEL_ENDPOINT"],
            timeout_seconds=timeout_seconds,
            role="primary",
        )

        fallback_values = {name: _get(name) for name in _FALLBACK_ENV}
        present = [name for name, value in fallback_values.items() if value is not None]
        fallback = None
        if present:
            if len(present) != len(_FALLBACK_ENV):
                raise RuntimeError(
                    "PIVOT_AGENT_MODEL_FALLBACK_ENDPOINT, "
                    "PIVOT_AGENT_MODEL_FALLBACK_MODEL and "
                    "PIVOT_AGENT_MODEL_FALLBACK_API_KEY must all be set or all omitted"
                )
            fallback = AgentModelConfig(
                fallback_values["PIVOT_AGENT_MODEL_FALLBACK_MODEL"] or "",
                fallback_values["PIVOT_AGENT_MODEL_FALLBACK_API_KEY"] or "",
                fallback_values["PIVOT_AGENT_MODEL_FALLBACK_ENDPOINT"],
                timeout_seconds=timeout_seconds,
                role="fallback",
            )
        return cls(primary=primary, fallback=fallback)

    def build(
        self,
        *,
        transport: ModelTransport | None = None,
        fallback_transport: ModelTransport | None = None,
        attempt_sink: AttemptSink | None = None,
    ) -> AgentModel | FallbackAgentModel:
        primary = AgentModel(self.primary, transport=transport, attempt_sink=attempt_sink)
        if self.fallback is None:
            return primary
        fallback = AgentModel(
            self.fallback, transport=fallback_transport, attempt_sink=attempt_sink
        )
        return FallbackAgentModel(primary, fallback)


def get_tool_schemas() -> list[dict[str, Any]]:
    """返回工具的 JSON Schema 定义"""
    return [
        {
            "type": "function",
            "function": {
                "name": "search_knowledge",
                "description": "搜索知识库中的相关信息。用于查找文档、政策、规定等内容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索查询词，应该简洁明确地描述需要查找的内容",
                        }
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_evidence",
                "description": (
                    "读取已找到的证据详细内容。必须先通过 search_knowledge 获得证据 ID。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "evidence_id": {
                            "type": "string",
                            "description": "证据 ID（从 search_knowledge 的结果中获得）"
                        }
                    },
                    "required": ["evidence_id"],
                },
            },
        },
    ]
