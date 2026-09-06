"""Run/QA errors mapped to public contract codes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunError(Exception):
    code: str
    message: str
    request_id: str

    def __str__(self) -> str:
        return self.message


def conflict(request_id: str) -> RunError:
    return RunError("IDEMPOTENCY_CONFLICT", "幂等键与参数不一致", request_id)


def not_found(request_id: str) -> RunError:
    return RunError("RESOURCE_NOT_FOUND", "资源不存在", request_id)
