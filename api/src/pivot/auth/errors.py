"""Auth domain errors mapped to the public error envelope (SPEC appendix B.1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AuthError(Exception):
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


INVALID_CREDENTIALS_MESSAGE = "账号或密码错误"
FORBIDDEN_MESSAGE = "没有权限执行该操作"
NOT_FOUND_MESSAGE = "资源不存在"


def invalid_credentials(request_id: str) -> AuthError:
    return AuthError("AUTH_INVALID_CREDENTIALS", INVALID_CREDENTIALS_MESSAGE, request_id)


def forbidden(request_id: str) -> AuthError:
    return AuthError("AUTH_FORBIDDEN", FORBIDDEN_MESSAGE, request_id)


def password_change_required(request_id: str) -> AuthError:
    return AuthError(
        "AUTH_PASSWORD_CHANGE_REQUIRED",
        "首次登录或密码重置后必须先修改密码",
        request_id,
    )


def not_found(request_id: str) -> AuthError:
    return AuthError("RESOURCE_NOT_FOUND", NOT_FOUND_MESSAGE, request_id)


def resource_forbidden(request_id: str) -> AuthError:
    return AuthError("RESOURCE_FORBIDDEN", FORBIDDEN_MESSAGE, request_id)
