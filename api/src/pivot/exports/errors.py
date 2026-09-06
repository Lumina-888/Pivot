"""Export domain errors mapped to the public envelope (SPEC appendix B.1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportError(Exception):
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


def not_found(request_id: str) -> ExportError:
    return ExportError("RESOURCE_NOT_FOUND", "资源不存在或不可见", request_id)


def resource_forbidden(request_id: str) -> ExportError:
    return ExportError("RESOURCE_FORBIDDEN", "无权访问该资源", request_id)


def auth_forbidden(request_id: str) -> ExportError:
    return ExportError("AUTH_FORBIDDEN", "无权限", request_id)


def export_expired(request_id: str) -> ExportError:
    return ExportError("EXPORT_EXPIRED", "导出已过期", request_id)
