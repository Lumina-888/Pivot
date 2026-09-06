"""Audit domain errors mapped to the public envelope (SPEC appendix B.1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditError(Exception):
    code: str
    message: str
    request_id: str
    retryable: bool = False

    def __str__(self) -> str:
        return self.message

    def to_envelope(self) -> dict[str, str | bool | dict]:
        return {
            "code": self.code,
            "message": self.message,
            "request_id": self.request_id,
            "details": {},
            "retryable": self.retryable,
        }


def auth_forbidden(request_id: str) -> AuditError:
    return AuditError("AUTH_FORBIDDEN", "无权限", request_id)


def not_found(request_id: str) -> AuditError:
    return AuditError("RESOURCE_NOT_FOUND", "资源不存在或不可见", request_id)


def append_only(request_id: str = "req_audit") -> AuditError:
    return AuditError("RESOURCE_FORBIDDEN", "审计记录不可修改或删除", request_id)
