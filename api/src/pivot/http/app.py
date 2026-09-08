"""FastAPI factory: health probes plus optional injected domain routers."""

from __future__ import annotations

from typing import Protocol

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pivot.audit.errors import AuditError
from pivot.audit.service import AuditService
from pivot.auth.errors import AuthError
from pivot.auth.service import AuthService
from pivot.documents.errors import DocumentError
from pivot.documents.service import DocumentService
from pivot.exports.errors import ExportError
from pivot.exports.service import ExportService
from pivot.qa.orchestrator import QaOrchestrator
from pivot.retrieval.service import RetrievalService
from pivot.runs.errors import RunError
from pivot.runs.service import RunService

_CHECKS = ("postgres", "minio", "qdrant", "redis")


class DependencyProbes(Protocol):
    def postgres(self) -> bool: ...
    def minio(self) -> bool: ...
    def qdrant(self) -> bool: ...
    def redis(self) -> bool: ...


def create_app(
    probes: DependencyProbes | None = None,
    auth: AuthService | None = None,
    documents: DocumentService | None = None,
    retrieval: RetrievalService | None = None,
    runs: RunService | None = None,
    qa: QaOrchestrator | None = None,
    exports: ExportService | None = None,
    audits: AuditService | None = None,
) -> FastAPI:
    """Create the HTTP assembly. Missing probes make /readyz fail closed.

    Domain routes are mounted only when their services are injected.
    Document, search, run, export and audit routes additionally require AuthService
    (fail closed).
    """

    app = FastAPI(
        title="Pivot health",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.exception_handler(AuthError)
    async def handle_auth_error(_request: Request, exc: AuthError) -> JSONResponse:
        from pivot.auth.http import auth_error_response

        return auth_error_response(exc)

    @app.exception_handler(DocumentError)
    async def handle_document_error(_request: Request, exc: DocumentError) -> JSONResponse:
        from pivot.documents.http import document_error_response

        return document_error_response(exc)

    @app.exception_handler(RunError)
    async def handle_run_error(_request: Request, exc: RunError) -> JSONResponse:
        from pivot.runs.http import run_error_response

        return run_error_response(exc)

    @app.exception_handler(ExportError)
    async def handle_export_error(_request: Request, exc: ExportError) -> JSONResponse:
        from pivot.exports.http import export_error_response

        return export_error_response(exc)

    @app.exception_handler(AuditError)
    async def handle_audit_error(_request: Request, exc: AuditError) -> JSONResponse:
        from pivot.audit.http import audit_error_response

        return audit_error_response(exc)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        checks: dict[str, bool] = {}
        ready = probes is not None
        if probes is None:
            checks = {name: False for name in _CHECKS}
        else:
            for name in _CHECKS:
                ok = bool(getattr(probes, name)())
                checks[name] = ok
                if not ok:
                    ready = False
        return JSONResponse(
            {"status": "ready" if ready else "not_ready", "checks": checks},
            status_code=200 if ready else 503,
        )

    if auth is not None:
        from pivot.auth.http import build_auth_router

        app.include_router(build_auth_router(auth), prefix="/api/v1")

    if documents is not None and auth is not None:
        from pivot.documents.http import build_documents_router

        app.include_router(build_documents_router(documents, auth), prefix="/api/v1")

    if retrieval is not None and auth is not None:
        from pivot.retrieval.http import build_search_router

        app.include_router(build_search_router(retrieval, auth), prefix="/api/v1")

    if runs is not None and qa is not None and auth is not None:
        from pivot.runs.http import build_runs_router

        app.include_router(build_runs_router(runs, qa, auth), prefix="/api/v1")

    if exports is not None and auth is not None:
        from pivot.exports.http import build_exports_router

        app.include_router(build_exports_router(exports, auth), prefix="/api/v1")

    if audits is not None and auth is not None:
        from pivot.audit.http import build_audit_router

        app.include_router(build_audit_router(audits, auth), prefix="/api/v1")

    return app
