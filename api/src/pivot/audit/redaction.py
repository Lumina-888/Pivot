"""Grade-aware redaction for audit metadata (FR-AUDIT-002). Never persist secrets or prompts."""

from __future__ import annotations

import re
from typing import Any

_SECRET_KEY_MARKERS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "private_key",
)

_PROMPT_KEYS = {
    "prompt",
    "system_prompt",
    "messages",
    "chain_of_thought",
    "thinking",
    "thought",
    "tool_args",
    "tool_parameters",
    "hidden_context",
}

_SECRET_VALUE_RE = re.compile(r"(?i)(api[_-]?key|secret|password|token|authorization)\s*[:=]\s*\S+")
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-+=/]+")
_SK_RE = re.compile(r"sk-[A-Za-z0-9]{8,}")

QUESTION_VISIBLE_CHARS = 24
SNIPPET_VISIBLE_CHARS = 48
REDACTED = "[REDACTED]"


def redact_text(value: str) -> str:
    text = _SECRET_VALUE_RE.sub(REDACTED, value)
    text = _BEARER_RE.sub("Bearer " + REDACTED, text)
    text = _SK_RE.sub(REDACTED, text)
    return text


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "…"


def redact_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    return {str(key): _redact_node(key, value) for key, value in metadata.items()}


def _redact_node(key: str, value: Any) -> Any:
    lowered = key.lower()
    if any(marker in lowered for marker in _SECRET_KEY_MARKERS) or lowered in _PROMPT_KEYS:
        return REDACTED
    if lowered in {"question", "query"} and isinstance(value, str):
        return _truncate(redact_text(value), QUESTION_VISIBLE_CHARS)
    if lowered in {"snippet", "content", "document_text"} and isinstance(value, str):
        return _truncate(redact_text(value), SNIPPET_VISIBLE_CHARS)
    if isinstance(value, dict):
        return redact_metadata(value)
    if isinstance(value, (list, tuple)):
        return [_redact_node(key, item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
