"""Refresh cookie attributes (FR-AUTH-001, NFR-SEC-005)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Cookie:
    name: str
    value: str
    httponly: bool
    secure: bool
    samesite: str
    path: str
    max_age: int
    clears_cookie: bool = False

    def as_set_cookie(self) -> str:
        parts = [
            f"{self.name}={self.value}",
            f"Max-Age={self.max_age}",
            f"Path={self.path}",
            f"SameSite={self.samesite}",
        ]
        if self.httponly:
            parts.append("HttpOnly")
        if self.secure:
            parts.append("Secure")
        return "; ".join(parts)


REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def refresh_cookie(value: str, max_age: int) -> Cookie:
    return Cookie(
        name=REFRESH_COOKIE_NAME,
        value=value,
        httponly=True,
        secure=True,
        samesite="Strict",
        path=REFRESH_COOKIE_PATH,
        max_age=max_age,
    )


def clear_refresh_cookie() -> Cookie:
    cookie = refresh_cookie("", max_age=0)
    return Cookie(
        name=cookie.name,
        value="",
        httponly=cookie.httponly,
        secure=cookie.secure,
        samesite=cookie.samesite,
        path=cookie.path,
        max_age=0,
        clears_cookie=True,
    )
