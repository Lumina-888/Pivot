"""FastAPI factory exposing only /healthz and /readyz."""

from __future__ import annotations

from typing import Protocol

from fastapi import FastAPI
from fastapi.responses import JSONResponse

_CHECKS = ("postgres", "minio", "qdrant", "redis")


class DependencyProbes(Protocol):
    def postgres(self) -> bool: ...
    def minio(self) -> bool: ...
    def qdrant(self) -> bool: ...
    def redis(self) -> bool: ...


def create_app(probes: DependencyProbes | None = None) -> FastAPI:
    """Create the health assembly. Missing probes make /readyz fail closed."""

    app = FastAPI(
        title="Pivot health",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

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

    return app
