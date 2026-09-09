"""Uvicorn target: `uvicorn pivot.http.main:app --factory` with PYTHONPATH=api/src."""

from __future__ import annotations

from fastapi import FastAPI


def app() -> FastAPI:
    from pivot.http.bootstrap import assemble_runtime_app

    return assemble_runtime_app()
