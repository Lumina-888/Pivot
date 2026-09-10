"""HTTP adapter for DocumentService. No document state machine lives here."""

from __future__ import annotations

from typing import Protocol
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from pivot.auth.errors import invalid_credentials
from pivot.auth.http import resolve_request_id
from pivot.auth.service import AuthService
from pivot.documents.errors import DocumentError
from pivot.documents.ports import FileContent
from pivot.documents.service import DocumentService


class IngestSubmitter(Protocol):
    def __call__(self, version_id: str, request_id: str, actor_id: str) -> object: ...

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


def build_documents_router(
    service: DocumentService,
    auth: AuthService,
    ingest: IngestSubmitter | None = None,
) -> APIRouter:
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
        envelope = {
            "document_id": version.document_id,
            "version_id": version.id,
            "state": version.state,
        }
        if ingest is not None:
            ingest(version.id, request_id, principal.user_id)
        return JSONResponse(envelope, status_code=201)

    @router.get("/documents/{id}")
    def get_document(request: Request, id: str) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        return service.get_detail(id, viewer_role=principal.role, request_id=request_id)

    @router.get("/documents/{id}/versions")
    def list_document_versions(request: Request, id: str) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        items = service.list_versions(id, viewer_role=principal.role, request_id=request_id)
        return {"items": list(items), "pagination": None}

    @router.post("/documents/{id}/retry")
    def retry_document(request: Request, id: str) -> JSONResponse:
        request_id, principal = _principal(request, auth)
        auth.require_admin(principal, request.url.path, request_id)
        version = service.retry_document(id, request_id, principal.user_id)
        if ingest is not None:
            ingest(version.id, request_id, principal.user_id)
        return JSONResponse({"document_id": id, "accepted": True}, status_code=202)

    @router.post("/documents/{id}/delete")
    def delete_document(request: Request, id: str) -> JSONResponse:
        request_id, principal = _principal(request, auth)
        auth.require_admin(principal, request.url.path, request_id)
        service.request_delete(id, request_id, principal.user_id)
        return JSONResponse({"document_id": id, "accepted": True}, status_code=202)

    @router.get("/documents/{id}/preview")
    def preview_document(request: Request, id: str) -> Response:
        return _file_response(_open(request, auth, service, id, "preview"))

    @router.get("/documents/{id}/download")
    def download_document(request: Request, id: str) -> Response:
        return _file_response(_open(request, auth, service, id, "download"))

    return router


def _open(
    request: Request,
    auth: AuthService,
    service: DocumentService,
    document_id: str,
    purpose: str,
) -> FileContent:
    request_id, principal = _principal(request, auth)
    return service.open_content(
        document_id,
        viewer_role=principal.role,
        request_id=request_id,
        purpose=purpose,
        actor_id=principal.user_id,
    )


def _file_response(payload: FileContent) -> Response:
    return Response(
        content=payload.body,
        media_type=payload.media_type,
        headers={
            "Content-Disposition": _content_disposition(payload.disposition, payload.filename),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


def _content_disposition(disposition: str, filename: str) -> str:
    ascii_name = filename.encode("ascii", "ignore").decode("ascii").strip() or "document"
    if "." in filename and "." not in ascii_name:
        ascii_name = f"document{filename[filename.rfind('.'):]}"
    return (
        f'{disposition}; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )


def _principal(request: Request, auth: AuthService):
    request_id = resolve_request_id(request)
    principal = auth.authenticate(_bearer_token(request, request_id), request_id)
    return request_id, principal


def _idempotency_key(request: Request) -> str | None:
    key = (request.headers.get("idempotency-key") or "").strip()
    return key or None
