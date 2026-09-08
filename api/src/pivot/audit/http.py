"""HTTP adapter for AuditService. No audit catalog or redaction lives here."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from pivot.audit.errors import AuditError
from pivot.audit.ports import Actor
from pivot.audit.service import AuditService
from pivot.auth.errors import invalid_credentials
from pivot.auth.http import resolve_request_id
from pivot.auth.ports import Principal
from pivot.auth.service import AuthService

_STATUS = {
    "AUTH_FORBIDDEN": 403,
    "RESOURCE_NOT_FOUND": 404,
    "RESOURCE_FORBIDDEN": 403,
}


def audit_error_response(exc: AuditError) -> JSONResponse:
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


def build_audit_router(audits: AuditService, auth: AuthService) -> APIRouter:
    router = APIRouter()

    @router.get("/admin/audit-events")
    def list_audit_events(
        request: Request,
        actor: str | None = None,
        action: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        auth.require_admin(principal, request.url.path, request_id)
        _ = (page, page_size)
        listed = audits.list_events(
            _actor(principal),
            request_id,
            filter_actor=actor,
            filter_action=action,
        )
        listed["pagination"] = None
        return listed

    return router
