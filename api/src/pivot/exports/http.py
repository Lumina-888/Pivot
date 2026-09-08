"""HTTP adapter for ExportService. No export state machine lives here."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from pivot.audit.ports import Actor
from pivot.auth.errors import invalid_credentials
from pivot.auth.http import resolve_request_id
from pivot.auth.ports import Principal
from pivot.auth.service import AuthService
from pivot.exports.errors import ExportError
from pivot.exports.service import ExportService

_STATUS = {
    "RESOURCE_NOT_FOUND": 404,
    "RESOURCE_FORBIDDEN": 403,
    "AUTH_FORBIDDEN": 403,
    "EXPORT_EXPIRED": 400,
}


class CreateExportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_type: Literal["conversation", "document"]
    source_id: str = Field(min_length=1)
    format: Literal["markdown", "docx"]


def export_error_response(exc: ExportError) -> JSONResponse:
    return JSONResponse(exc.to_envelope(), status_code=_STATUS.get(exc.code, 400))


def _bearer_token(request: Request, request_id: str) -> str:
    header = request.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        raise invalid_credentials(request_id)
    token = header.removeprefix("Bearer ").strip()
    if not token:
        raise invalid_credentials(request_id)
    return token


def _principal(request: Request, auth: AuthService) -> tuple[str, Principal]:
    request_id = resolve_request_id(request)
    principal = auth.authenticate(_bearer_token(request, request_id), request_id)
    return request_id, principal


def _actor(principal: Principal) -> Actor:
    return Actor(
        user_id=principal.user_id,
        username=principal.username,
        role=principal.role,
        status=principal.status,
    )


def build_exports_router(exports: ExportService, auth: AuthService) -> APIRouter:
    router = APIRouter()

    @router.post("/exports")
    def create_export(body: CreateExportBody, request: Request) -> JSONResponse:
        request_id, principal = _principal(request, auth)
        created = exports.create(
            _actor(principal),
            source_type=body.source_type,
            source_id=body.source_id,
            fmt=body.format,
            request_id=request_id,
        )
        return JSONResponse(created, status_code=202)

    @router.get("/exports/{id}")
    def get_export(request: Request, id: str) -> dict[str, str | None]:
        request_id, principal = _principal(request, auth)
        return exports.get(_actor(principal), id, request_id)

    return router
