"""HTTP adapter for RunService and SSE replay. No QA graph lives here."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from pivot.auth.errors import invalid_credentials
from pivot.auth.http import resolve_request_id
from pivot.auth.service import AuthService
from pivot.qa.orchestrator import QaOrchestrator
from pivot.runs.errors import RunError
from pivot.runs.service import RunService

_STATUS = {
    "IDEMPOTENCY_CONFLICT": 409,
    "RESOURCE_NOT_FOUND": 404,
    "RESOURCE_FORBIDDEN": 403,
}


class CreateRunBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    scope_type: str = "global"
    scope_document_id: str | None = None


def run_error_response(exc: RunError) -> JSONResponse:
    return JSONResponse(exc.to_envelope(), status_code=_STATUS.get(exc.code, 400))


def _bearer_token(request: Request, request_id: str) -> str:
    header = request.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        raise invalid_credentials(request_id)
    token = header.removeprefix("Bearer ").strip()
    if not token:
        raise invalid_credentials(request_id)
    return token


def _principal(request: Request, auth: AuthService):
    request_id = resolve_request_id(request)
    principal = auth.authenticate(_bearer_token(request, request_id), request_id)
    return request_id, principal


def _sse_frame(name: str, data: dict[str, object]) -> str:
    return (
        f"id: {data['seq']}\n"
        f"event: {name}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )


def build_runs_router(runs: RunService, qa: QaOrchestrator, auth: AuthService) -> APIRouter:
    router = APIRouter()

    @router.post("/runs")
    def create_run(body: CreateRunBody, request: Request) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        auth.ensure_conversation_owner(principal, body.conversation_id, request_id)
        bundle = runs.create(
            conversation_id=body.conversation_id,
            owner_id=principal.user_id,
            question=body.question,
            idempotency_key=body.idempotency_key,
            request_id=request_id,
            scope_type=body.scope_type,
            scope_document_id=body.scope_document_id,
        )
        log = runs.log(bundle.run.id)
        if not log.replay():
            qa.execute(bundle, log, request_id)
        return {
            "run_id": bundle.run.id,
            "message_id": bundle.run.message_id,
            "initial_state": {"state": bundle.run.state},
            "request_id": request_id,
        }

    @router.get("/runs/{id}")
    def get_run(request: Request, id: str) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        bundle = runs.get(id, request_id)
        auth.authorize_conversation(principal, bundle.run.conversation_id, request_id)
        created = bundle.run.created_at
        return {
            "run_id": bundle.run.id,
            "conversation_id": bundle.run.conversation_id,
            "message_id": bundle.run.message_id,
            "question": bundle.run.question,
            "state": bundle.run.state,
            "created_at": None if created is None else created.isoformat(),
            "error_code": bundle.run.error_code,
            "scope_type": bundle.run.scope_type,
            "scope_document_id": bundle.run.scope_document_id,
        }

    @router.get("/runs/{id}/events")
    def stream_run_events(request: Request, id: str) -> StreamingResponse:
        request_id, principal = _principal(request, auth)
        bundle = runs.get(id, request_id)
        auth.authorize_conversation(principal, bundle.run.conversation_id, request_id)
        last_raw = (request.headers.get("last-event-id") or "").strip()
        last_event_id = int(last_raw) if last_raw.isdigit() else None
        frames = runs.log(id).replay(last_event_id=last_event_id)
        body = "".join(_sse_frame(name, data) for name, data in frames)
        return StreamingResponse(iter([body]), media_type="text/event-stream")

    @router.post("/runs/{id}/cancel")
    def cancel_run(request: Request, id: str) -> dict[str, str]:
        request_id, principal = _principal(request, auth)
        bundle = runs.get(id, request_id)
        auth.authorize_conversation(principal, bundle.run.conversation_id, request_id)
        cancelled = runs.cancel(id, request_id)
        return {"run_id": cancelled.run.id, "state": cancelled.run.state}

    return router
