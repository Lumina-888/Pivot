"""ProviderCall / cost metadata. Does not persist prompts or completions (SPEC §2.2)."""

from __future__ import annotations

from typing import Any

from pivot.audit.models import ProviderCallRecord
from pivot.shared.ids import new_id

_DROPPED_KEYS = frozenset(
    {
        "prompt",
        "system_prompt",
        "messages",
        "response",
        "completion",
        "thinking",
        "chain_of_thought",
        "tool_parameters",
        "secret",
        "api_key",
    }
)


class ProviderCallRecorder:
    def __init__(self) -> None:
        self._items: dict[str, ProviderCallRecord] = {}

    def record(
        self,
        *,
        provider: str,
        model: str,
        operation: str,
        status: str,
        request_id: str | None = None,
        run_id: str | None = None,
        tokens: int | None = None,
        latency_ms: int | None = None,
        retry_count: int = 0,
        estimated_cost: float | None = None,
        **ignored: Any,
    ) -> ProviderCallRecord:
        extra = {key: value for key, value in ignored.items() if key not in _DROPPED_KEYS}
        item = ProviderCallRecord(
            id=new_id("provider_call"),
            provider=provider,
            model=model,
            operation=operation,
            status=status,
            request_id=request_id,
            run_id=run_id,
            tokens=tokens,
            latency_ms=latency_ms,
            retry_count=retry_count,
            estimated_cost=estimated_cost,
            extra=extra,
        )
        self._items[item.id] = item
        return item

    def list(self) -> tuple[ProviderCallRecord, ...]:
        return tuple(self._items.values())

    def list_for_run(self, run_id: str) -> tuple[ProviderCallRecord, ...]:
        return tuple(item for item in self._items.values() if item.run_id == run_id)
