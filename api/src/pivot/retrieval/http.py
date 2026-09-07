"""HTTP adapter for RetrievalService.search_documents. No ranking lives here."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from pivot.auth.errors import invalid_credentials
from pivot.auth.http import resolve_request_id
from pivot.auth.service import AuthService
from pivot.retrieval.models import RetrievalQuery
from pivot.retrieval.service import RetrievalService


def _bearer_token(request: Request, request_id: str) -> str:
    header = request.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        raise invalid_credentials(request_id)
    token = header.removeprefix("Bearer ").strip()
    if not token:
        raise invalid_credentials(request_id)
    return token


def build_search_router(service: RetrievalService, auth: AuthService) -> APIRouter:
    router = APIRouter()

    @router.get("/search")
    def search_documents(
        request: Request,
        q: str = Query(min_length=1),
        space: str | None = None,
        tag: str | None = None,
    ) -> dict[str, object]:
        request_id = resolve_request_id(request)
        principal = auth.authenticate(_bearer_token(request, request_id), request_id)
        hits = service.search_documents(
            RetrievalQuery(
                text=q,
                principal_id=principal.user_id,
                space=space,
                tags=(tag,) if tag else (),
            )
        )
        items = [
            {
                "document_id": hit.document_id,
                "title": hit.title,
                "space": hit.space,
                "snippet": hit.snippet,
                "version_id": hit.version_id,
            }
            for hit in hits
        ]
        return {"items": items, "pagination": None}

    return router
