"""HTTP adapter for ConversationService. No QA graph lives here."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from pivot.auth.errors import invalid_credentials
from pivot.auth.http import resolve_request_id
from pivot.auth.service import AuthService
from pivot.runs.conversations import ConversationService


class CreateConversationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1)
    scope_type: Literal["global", "document"] = "global"
    scope_document_id: str | None = None


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


def build_conversations_router(
    conversations: ConversationService, auth: AuthService
) -> APIRouter:
    router = APIRouter()

    @router.get("/conversations")
    def list_conversations(request: Request) -> dict[str, object]:
        _request_id, principal = _principal(request, auth)
        items = [
            conversations.to_summary(record)
            for record in conversations.list_for_owner(principal.user_id)
        ]
        return {"items": items, "pagination": None}

    @router.post("/conversations")
    def create_conversation(body: CreateConversationBody, request: Request) -> JSONResponse:
        request_id, principal = _principal(request, auth)
        record = conversations.create(
            owner_id=principal.user_id,
            title=body.title,
            request_id=request_id,
            scope_type=body.scope_type,
            scope_document_id=body.scope_document_id,
        )
        auth.ensure_conversation_owner(principal, record.id, request_id)
        return JSONResponse(conversations.to_summary(record), status_code=201)

    @router.get("/conversations/{id}")
    def get_conversation(request: Request, id: str) -> dict[str, str | None]:
        request_id, principal = _principal(request, auth)
        auth.authorize_conversation(principal, id, request_id)
        record = conversations.get(id, request_id)
        return conversations.to_summary(record)

    @router.delete("/conversations/{id}")
    def delete_conversation(request: Request, id: str) -> Response:
        request_id, principal = _principal(request, auth)
        auth.authorize_conversation(principal, id, request_id)
        conversations.hide(id, request_id)
        return Response(status_code=204)

    @router.get("/conversations/{id}/messages")
    def list_messages(request: Request, id: str) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        auth.authorize_conversation(principal, id, request_id)
        return {"items": conversations.list_messages(id, request_id)}

    return router
