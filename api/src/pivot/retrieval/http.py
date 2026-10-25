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


def build_search_router(
    service: RetrievalService,
    auth: AuthService,
    *,
    authorize_hit=None,
) -> APIRouter:
    """Build the /search router.

    ``authorize_hit`` (principal_id, document_id, version_id) -> bool
    is the live-fact recheck (the QA authorize closure in bootstrap):
    native search payloads are stamped at ingest and never updated by
    folder moves or claims, so the library/exception scope in
    passes_filters alone can over-serve a moved document's title and
    snippet. When given, every hit is rechecked against live facts
    and dropped on denial or on any recheck failure (fail closed);
    exception-granted documents still pass, exactly like the QA path.
    When None (legacy callers, tests without a live fact store) the
    router keeps its previous payload-scope behavior.
    """
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
                # Library scope is derived server-side from the Principal;
                # it is never accepted from the request. The exception
                # channel rides alongside it (ADR-017 D1), and so does
                # the folder scope (ADR-018 D3): chunks in a restricted
                # folder pass only when the folder is visible or the
                # document carries an exception grant.
                library_ids=tuple(sorted(auth.visible_libraries(principal))),
                exception_document_ids=tuple(
                    sorted(auth.exception_document_ids(principal))
                ),
                visible_folder_ids=tuple(
                    sorted(auth.visible_folder_ids(principal))
                ),
            )
        )
        if authorize_hit is not None:
            kept = []
            for hit in hits:
                try:
                    allowed = authorize_hit(
                        principal.user_id, hit.document_id, hit.version_id
                    )
                except Exception:
                    continue
                if allowed is True:
                    kept.append(hit)
            hits = kept
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
