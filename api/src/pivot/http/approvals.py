"""HTTP adapter for publish approvals. No business logic lives here."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel

from pivot.auth.approvals import ApprovalService
from pivot.auth.errors import invalid_credentials
from pivot.auth.http import resolve_request_id
from pivot.auth.ports import Principal
from pivot.auth.service import AuthService


class RejectBody(BaseModel):
    reason: str = ""


class ResubmitBody(BaseModel):
    target_library_id: str | None = None


class RetargetBody(BaseModel):
    target_library_id: str


def _bearer_token(request: Request, request_id: str) -> str:
    header = request.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        raise invalid_credentials(request_id)
    token = header[len("Bearer "):].strip()
    if not token:
        raise invalid_credentials(request_id)
    return token


def _principal(request: Request, auth: AuthService) -> tuple[str, Principal]:
    request_id = resolve_request_id(request)
    principal = auth.authenticate(_bearer_token(request, request_id), request_id)
    return request_id, principal


def _request_view(request, approvals) -> dict[str, object]:
    return {
        "request_id": request.id,
        "document_id": request.document_id,
        "document_title": approvals.document_title(request.document_id),
        "version_id": request.version_id,
        "target_library_id": request.target_library_id,
        "proposer": request.proposer,
        "status": request.status,
        "reason": request.reason,
        "created_at": None if request.created_at is None else request.created_at.isoformat(),
        "decided_at": None if request.decided_at is None else request.decided_at.isoformat(),
        "decided_by": request.decided_by,
    }


def build_approvals_router(
    auth: AuthService, approvals: ApprovalService
) -> APIRouter:
    router = APIRouter()

    @router.get("/approvals/pending")
    def list_pending(request: Request) -> dict[str, object]:
        _request_id, principal = _principal(request, auth)
        items = approvals.list_pending(principal)
        return {"items": [_request_view(item, approvals) for item in items]}

    @router.get("/approvals/{request_id}")
    def get_request(request: Request, request_id: str) -> dict[str, object]:
        http_request_id, principal = _principal(request, auth)
        found = approvals.get_request(principal, request_id, http_request_id)
        return _request_view(found, approvals)

    @router.post("/approvals/{request_id}/approve")
    def approve_request(request: Request, request_id: str) -> dict[str, object]:
        http_request_id, principal = _principal(request, auth)
        decided = approvals.approve(principal, request_id, http_request_id)
        return _request_view(decided, approvals)

    @router.post("/approvals/{request_id}/reject")
    def reject_request(
        request: Request, request_id: str, body: RejectBody
    ) -> dict[str, object]:
        http_request_id, principal = _principal(request, auth)
        decided = approvals.reject(
            principal, request_id, http_request_id, reason=body.reason
        )
        return _request_view(decided, approvals)

    @router.post("/approvals/{request_id}/withdraw")
    def withdraw_request(request: Request, request_id: str) -> dict[str, object]:
        http_request_id, principal = _principal(request, auth)
        withdrawn = approvals.withdraw(principal, request_id, http_request_id)
        return _request_view(withdrawn, approvals)

    @router.post("/approvals/{request_id}/resubmit")
    def resubmit_request(
        request: Request, request_id: str, body: ResubmitBody
    ) -> dict[str, object]:
        http_request_id, principal = _principal(request, auth)
        reopened = approvals.resubmit(
            principal,
            request_id,
            http_request_id,
            target_library_id=body.target_library_id,
        )
        return _request_view(reopened, approvals)

    @router.post("/approvals/{request_id}/retarget")
    def retarget_request(
        request: Request, request_id: str, body: RetargetBody
    ) -> dict[str, object]:
        http_request_id, principal = _principal(request, auth)
        retargeted = approvals.retarget(
            principal,
            request_id,
            http_request_id,
            target_library_id=body.target_library_id,
        )
        return _request_view(retargeted, approvals)

    @router.get("/approvals/{request_id}/review")
    def review_request(request: Request, request_id: str) -> Response:
        http_request_id, principal = _principal(request, auth)
        payload = approvals.review_read(principal, request_id, http_request_id)
        ascii_name = payload.filename.encode("ascii", "ignore").decode("ascii").strip()
        ascii_name = ascii_name or "document"
        disposition = (
            f"{payload.disposition}; filename=\"{ascii_name}\"; "
            f"filename*=UTF-8''{quote(payload.filename, safe='')}"
        )
        return Response(
            content=payload.body,
            media_type=payload.media_type,
            headers={
                "Content-Disposition": disposition,
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
            },
        )

    return router
