"""Injected worker process settings. Queue names and concurrency are not frozen TBD-P0."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


def _require(environ: Mapping[str, str], key: str) -> str:
    value = (environ.get(key) or "").strip()
    if not value:
        raise RuntimeError(f"{key} is required for the worker process")
    return value


def _require_positive_int(environ: Mapping[str, str], key: str) -> int:
    raw = _require(environ, key)
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{key} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{key} must be a positive integer")
    return value


@dataclass(frozen=True)
class WorkerSettings:
    parse_queue: str
    online_queue: str
    concurrency: int
    health_host: str = "0.0.0.0"
    health_port: int = 8001

    def __post_init__(self) -> None:
        if not self.parse_queue.strip() or not self.online_queue.strip():
            raise RuntimeError("parse and online queues are required")
        if self.parse_queue == self.online_queue:
            raise RuntimeError("parse and online queues must be isolated")
        if self.concurrency <= 0:
            raise RuntimeError("worker concurrency must be a positive integer")
        if self.health_port <= 0:
            raise RuntimeError("worker health port must be a positive integer")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> WorkerSettings:
        env = os.environ if environ is None else environ
        host = (env.get("PIVOT_WORKER_HEALTH_HOST") or "0.0.0.0").strip() or "0.0.0.0"
        port_raw = (env.get("PIVOT_WORKER_HEALTH_PORT") or "").strip()
        health_port = 8001 if not port_raw else int(port_raw)
        return cls(
            parse_queue=_require(env, "PIVOT_PARSE_QUEUE"),
            online_queue=_require(env, "PIVOT_ONLINE_QUEUE"),
            concurrency=_require_positive_int(env, "PIVOT_WORKER_CONCURRENCY"),
            health_host=host,
            health_port=health_port,
        )
