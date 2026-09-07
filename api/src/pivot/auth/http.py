"""HTTP adapter for AuthService. No business state machine lives here."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from pivot.auth.cookies import REFRESH_COOKIE_NAME, Cookie
from pivot.auth.errors import AuthError, invalid_credentials
from pivot.auth.service import AuthService

_STATUS = {
    "AUTH_INVALID_CREDENTIALS": 401,
    "AUTH_FORBIDDEN": 403,
    "RESOURCE_NOT_FOUND": 404,
    "RESOURCE_FORBIDDEN": 403,
}


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


def resolve_request_id(request: Request) -> str:
    header = (request.headers.get("x-request-id") or "").strip()
    if header:
        return header
    return "req_" + secrets.token_urlsafe(16)


def auth_error_response(exc: AuthError) -> JSONResponse:
    return JSONResponse(exc.to_envelope(), status_code=_STATUS.get(exc.code, 400))


def apply_cookie(response: Response, cookie: Cookie) -> None:
    response.set_cookie(
        key=cookie.name,
        value=cookie.value,
        max_age=cookie.max_age,
        path=cookie.path,
        httponly=cookie.httponly,
        secure=cookie.secure,
        samesite=cookie.samesite.lower(),
    )


def _bearer_token(request: Request, request_id: str) -> str:
    header = request.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        raise invalid_credentials(request_id)
    token = header.removeprefix("Bearer ").strip()
    if not token:
        raise invalid_credentials(request_id)
    return token


def build_auth_router(service: AuthService) -> APIRouter:
    router = APIRouter(prefix="/auth")

    @router.post("/login")
    def login(body: LoginBody, request: Request) -> JSONResponse:
        request_id = resolve_request_id(request)
        result = service.login(body.username, body.password, request_id)
        response = JSONResponse(result.to_login_success())
        apply_cookie(response, result.cookie)
        return response

    @router.post("/refresh")
    def refresh(request: Request) -> JSONResponse:
        request_id = resolve_request_id(request)
        token = request.cookies.get(REFRESH_COOKIE_NAME, "")
        result = service.refresh(token, request_id)
        response = JSONResponse(result.to_login_success())
        apply_cookie(response, result.cookie)
        return response

    @router.post("/logout")
    def logout(request: Request) -> Response:
        request_id = resolve_request_id(request)
        access = _bearer_token(request, request_id)
        service.authenticate(access, request_id)
        cookie = service.logout(request.cookies.get(REFRESH_COOKIE_NAME, ""), request_id)
        response = Response(status_code=204)
        apply_cookie(response, cookie)
        return response

    return router
