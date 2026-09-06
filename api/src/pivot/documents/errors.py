"""Document domain errors mapped to public contract codes where they exist."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentError(Exception):
    code: str
    message: str
    request_id: str
    retryable: bool = False

    def __str__(self) -> str:
        return self.message

    def to_envelope(self) -> dict[str, str | bool]:
        return {
            "code": self.code,
            "message": self.message,
            "request_id": self.request_id,
            "retryable": self.retryable,
        }


def unsupported_extension(request_id: str) -> DocumentError:
    return DocumentError("UNSUPPORTED_EXTENSION", "不支持的文件类型", request_id)


def invalid_signature(request_id: str) -> DocumentError:
    return DocumentError("INVALID_FILE_SIGNATURE", "文件签名与声明类型不一致", request_id)


def resource_limit(request_id: str) -> DocumentError:
    return DocumentError("RESOURCE_LIMIT", "超出资源限制", request_id, retryable=False)


def illegal_state(request_id: str, message: str = "非法状态转移") -> DocumentError:
    return DocumentError("RESOURCE_FORBIDDEN", message, request_id)
