"""HTTP adapter for admin metrics and tasks. No business logic lives here."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from fastapi import APIRouter, Request

from pivot.auth.http import resolve_request_id
from pivot.auth.service import AuthService


class DependencyProbes(Protocol):
    """Health check protocol for external dependencies."""

    def postgres(self) -> bool: ...
    def minio(self) -> bool: ...
    def qdrant(self) -> bool: ...
    def redis(self) -> bool: ...


class DocumentStats(Protocol):
    """Protocol for document service statistics."""

    def count_total(self) -> int: ...
    def count_indexed(self) -> int: ...
    def count_pending(self) -> int: ...
    def count_failed(self) -> int: ...


class RunStats(Protocol):
    """Protocol for run service statistics."""

    def count_total(self) -> int: ...
    def count_completed(self) -> int: ...
    def count_failed(self) -> int: ...
    def count_in_progress(self) -> int: ...


def _bearer_token(request: Request, request_id: str) -> str:
    from pivot.auth.errors import invalid_credentials

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


def build_admin_router(
    auth: AuthService,
    probes: DependencyProbes | None = None,
    document_stats: DocumentStats | None = None,
    run_stats: RunStats | None = None,
) -> APIRouter:
    """Build admin routes for metrics and tasks.

    All routes require admin role. Missing stats providers return default values.
    """
    router = APIRouter()

    @router.get("/admin/metrics")
    def get_metrics(request: Request) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        auth.require_admin(principal, request.url.path, request_id)

        # Storage health from probes
        storage_status = {
            "postgres": probes.postgres() if probes else False,
            "minio": probes.minio() if probes else False,
            "qdrant": probes.qdrant() if probes else False,
            "redis": probes.redis() if probes else False,
        }

        # System operational if all storage is up
        system_operational = all(storage_status.values())

        # Document statistics
        doc_stats = {
            "total": document_stats.count_total() if document_stats else 0,
            "indexed": document_stats.count_indexed() if document_stats else 0,
            "pending": document_stats.count_pending() if document_stats else 0,
            "failed": document_stats.count_failed() if document_stats else 0,
        }

        # Run statistics
        qa_stats = {
            "total_runs": run_stats.count_total() if run_stats else 0,
            "completed": run_stats.count_completed() if run_stats else 0,
            "failed": run_stats.count_failed() if run_stats else 0,
            "in_progress": run_stats.count_in_progress() if run_stats else 0,
        }

        return {
            "system": {
                "status": "operational" if system_operational else "degraded",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "qa": qa_stats,
            "documents": doc_stats,
            "storage": storage_status,
        }

    @router.get("/admin/tasks")
    def get_tasks(request: Request) -> dict[str, object]:
        request_id, principal = _principal(request, auth)
        auth.require_admin(principal, request.url.path, request_id)

        # Initial implementation returns empty task list
        # M07 worker will provide task query interface in future
        return {
            "tasks": [],
            "pagination": None,
        }

    return router
