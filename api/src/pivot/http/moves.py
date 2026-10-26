"""HTTP adapter for cross-library moves. No business logic lives here."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from pivot.auth.errors import invalid_credentials
from pivot.auth.http import resolve_request_id
from pivot.auth.moves import MoveService
from pivot.auth.ports import Principal
from pivot.auth.service import AuthService


class ProposeBody(BaseModel):
    document_id: str
    target_library_id: str
    reason: str = ""
    rollback_of: str | None = None


class RejectBody(BaseModel):
    reason: str = ""


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


def _move_view(request, moves) -> dict[str, object]:
    return {
        "request_id": request.id,
        "document_id": request.document_id,
        "document_title": moves.document_title(request.document_id),
        "source_library_id": request.source_library_id,
        "target_library_id": request.target_library_id,
        "proposer": request.proposer,
        "status": request.status,
        "reason": request.reason,
        "reconcile_status": request.reconcile_status,
        "reconcile_attempts": request.reconcile_attempts,
        "created_at": None if request.created_at is None else request.created_at.isoformat(),
        "decided_at": None if request.decided_at is None else request.decided_at.isoformat(),
        "decided_by": request.decided_by,
    }


def build_moves_router(auth: AuthService, moves: MoveService) -> APIRouter:
    router = APIRouter()

    @router.get("/moves/pending")
    def list_pending(request: Request) -> dict[str, object]:
        _request_id, principal = _principal(request, auth)
        items = moves.list_pending(principal)
        return {"items": [_move_view(item, moves) for item in items]}

    @router.get("/moves/{request_id}")
    def get_request(request: Request, request_id: str) -> dict[str, object]:
        http_request_id, principal = _principal(request, auth)
        found = moves.get_request(principal, request_id, http_request_id)
        return _move_view(found, moves)

    @router.post("/moves")
    def propose_move(request: Request, body: ProposeBody) -> dict[str, object]:
        http_request_id, principal = _principal(request, auth)
        proposed = moves.propose(
            principal,
            body.document_id,
            body.target_library_id,
            http_request_id,
            reason=body.reason,
            rollback_of=body.rollback_of,
        )
        return _move_view(proposed, moves)

    @router.post("/moves/{request_id}/approve")
    def approve_move(request: Request, request_id: str) -> dict[str, object]:
        http_request_id, principal = _principal(request, auth)
        decided = moves.approve(principal, request_id, http_request_id)
        return _move_view(decided, moves)

    @router.post("/moves/{request_id}/reject")
    def reject_move(
        request: Request, request_id: str, body: RejectBody
    ) -> dict[str, object]:
        http_request_id, principal = _principal(request, auth)
        decided = moves.reject(
            principal, request_id, http_request_id, reason=body.reason
        )
        return _move_view(decided, moves)

    @router.post("/moves/{request_id}/withdraw")
    def withdraw_move(request: Request, request_id: str) -> dict[str, object]:
        http_request_id, principal = _principal(request, auth)
        withdrawn = moves.withdraw(principal, request_id, http_request_id)
        return _move_view(withdrawn, moves)

    return router
