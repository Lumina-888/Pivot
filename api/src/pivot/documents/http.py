"""HTTP adapter for DocumentService. No document state machine lives here."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from pivot.auth.errors import invalid_credentials
from pivot.auth.http import resolve_request_id
from pivot.auth.service import AuthService
from pivot.documents.errors import DocumentError
from pivot.documents.service import DocumentService

_STATUS = {
    "UNSUPPORTED_EXTENSION": 400,
    "INVALID_FILE_SIGNATURE": 400,
    "RESOURCE_LIMIT": 400,
    "RESOURCE_NOT_FOUND": 404,
    "RESOURCE_FORBIDDEN": 403,
}


def document_error_response(exc: DocumentError) -> JSONResponse:
    return JSONResponse(exc.to_envelope(), status_code=_STATUS.get(exc.code, 400))


def _bearer_token(request: Request, request_id: str) -> str:
    header = request.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        raise invalid_credentials(request_id)
    token = header.removeprefix("Bearer ").strip()
    if not token:
        raise invalid_credentials(request_id)
    return token


def build_documents_router(service: DocumentService, auth: AuthService) -> APIRouter:
    router = APIRouter()

    @router.get("/documents")
    def list_documents(
        request: Request,
        space: str | None = None,
        tags: list[str] | None = Query(default=None),
    ) -> dict[str, object]:
        request_id = resolve_request_id(request)
        principal = auth.authenticate(_bearer_token(request, request_id), request_id)
        items = service.list_library(
            viewer_role=principal.role,
            space=space,
            tags=tuple(tags or ()),
        )
        return {"items": list(items), "pagination": None}

    @router.post("/documents")
    def upload_document(
        request: Request,
        title: str = Form(min_length=1),
        file: UploadFile = File(...),
        space: str = Form(default="shared"),
        classification: str = Form(default=""),
    ) -> JSONResponse:
        request_id = resolve_request_id(request)
        principal = auth.authenticate(_bearer_token(request, request_id), request_id)
        auth.require_admin(principal, request.url.path, request_id)
        content = file.file.read()
        version = service.upload(
            filename=file.filename or "",
            declared_mime=file.content_type or "",
            content=content,
            title=title,
            actor_id=principal.user_id,
            request_id=request_id,
            idempotency_key=_idempotency_key(request),
            space=space or "shared",
            classification=classification,
        )
        return JSONResponse(
            {
                "document_id": version.document_id,
                "version_id": version.id,
                "state": version.state,
            },
            status_code=201,
        )

    return router


def _idempotency_key(request: Request) -> str | None:
    key = (request.headers.get("idempotency-key") or "").strip()
    return key or None
