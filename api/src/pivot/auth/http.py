"""HTTP adapter for AuthService. No business state machine lives here."""

from __future__ import annotations

import secrets
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class ChangePasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class AdminUserCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1)
    initial_password: str = Field(min_length=8)


class AdminUserUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["active", "disabled"] | None = None
    role: Literal["admin", "user"] | None = None
    reset_password: bool | None = None

    @model_validator(mode="after")
    def require_one_field(self) -> AdminUserUpdateBody:
        if self.status is None and self.role is None and self.reset_password is None:
            raise ValueError("status, role or reset_password required")
        return self


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


def _principal(request: Request, service: AuthService):
    request_id = resolve_request_id(request)
    principal = service.authenticate(_bearer_token(request, request_id), request_id)
    return request_id, principal


def generate_initial_password() -> str:
    return secrets.token_urlsafe(16)


def build_auth_router(service: AuthService) -> APIRouter:
    router = APIRouter()
    auth = APIRouter(prefix="/auth")

    @auth.post("/login")
    def login(body: LoginBody, request: Request) -> JSONResponse:
        request_id = resolve_request_id(request)
        result = service.login(body.username, body.password, request_id)
        response = JSONResponse(result.to_login_success())
        apply_cookie(response, result.cookie)
        return response

    @auth.post("/refresh")
    def refresh(request: Request) -> JSONResponse:
        request_id = resolve_request_id(request)
        token = request.cookies.get(REFRESH_COOKIE_NAME, "")
        result = service.refresh(token, request_id)
        response = JSONResponse(result.to_login_success())
        apply_cookie(response, result.cookie)
        return response

    @auth.post("/logout")
    def logout(request: Request) -> Response:
        request_id = resolve_request_id(request)
        access = _bearer_token(request, request_id)
        service.authenticate(access, request_id)
        cookie = service.logout(request.cookies.get(REFRESH_COOKIE_NAME, ""), request_id)
        response = Response(status_code=204)
        apply_cookie(response, cookie)
        return response

    @auth.post("/change-password")
    def change_password(body: ChangePasswordBody, request: Request) -> Response:
        request_id = resolve_request_id(request)
        access = _bearer_token(request, request_id)
        service.change_password(access, body.current_password, body.new_password, request_id)
        return Response(status_code=204)

    @router.get("/admin/users")
    def list_users(request: Request) -> dict[str, object]:
        request_id, principal = _principal(request, service)
        service.require_admin(principal, request.url.path, request_id)
        items = service.list_users(principal.user_id, request_id)
        return {"items": list(items), "pagination": None}

    @router.post("/admin/users")
    def create_user(body: AdminUserCreateBody, request: Request) -> JSONResponse:
        request_id, principal = _principal(request, service)
        service.require_admin(principal, request.url.path, request_id)
        created = service.create_user(
            principal.user_id,
            body.username,
            body.initial_password,
            request_id,
        )
        return JSONResponse(service.admin_user(created.id, request_id), status_code=201)

    @router.patch("/admin/users/{id}")
    def update_user(id: str, body: AdminUserUpdateBody, request: Request) -> dict[str, str]:
        request_id, principal = _principal(request, service)
        service.require_admin(principal, request.url.path, request_id)
        payload: dict[str, str] | None = None
        if body.role is not None:
            user = service.change_role(principal.user_id, id, body.role, request_id)
            payload = service.to_admin_user(user)
        if body.status is not None:
            user = service.set_user_status(principal.user_id, id, body.status, request_id)
            payload = service.to_admin_user(user)
        initial_password: str | None = None
        if body.reset_password:
            initial_password = generate_initial_password()
            reset = service.reset_password(
                principal.user_id, id, initial_password, request_id
            )
            payload = service.admin_user(reset.id, request_id)
        if payload is None:
            payload = service.admin_user(id, request_id)
        if initial_password is not None:
            payload = {**payload, "initial_password": initial_password}
        return payload

    router.include_router(auth)
    return router
