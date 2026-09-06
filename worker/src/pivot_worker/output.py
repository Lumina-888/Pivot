"""Worker output envelope (SPEC §5.7 / worker.schema.json)."""

from __future__ import annotations

from typing import Any


def worker_ok(content: dict[str, Any], stage: str, duration_ms: int = 0) -> dict[str, Any]:
    return {
        "status": "ok",
        "content": content,
        "citations": [],
        "confidence": None,
        "error_code": None,
        "trace": {"stage": stage, "duration_ms": duration_ms},
    }


def worker_insufficient(stage: str, duration_ms: int = 0) -> dict[str, Any]:
    return {
        "status": "insufficient",
        "content": None,
        "citations": [],
        "confidence": None,
        "error_code": None,
        "trace": {"stage": stage, "duration_ms": duration_ms},
    }


def worker_failed(error_code: str, stage: str, duration_ms: int = 0) -> dict[str, Any]:
    return {
        "status": "failed",
        "content": None,
        "citations": [],
        "confidence": None,
        "error_code": error_code,
        "trace": {"stage": stage, "duration_ms": duration_ms},
    }
