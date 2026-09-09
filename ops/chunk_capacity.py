"""Opt-in chunk-capacity retrieve harness. Not GATE-P0-007 verified."""

from __future__ import annotations

import os
import tracemalloc
from collections.abc import Mapping
from dataclasses import dataclass

from fact_backup import synthetic_chunks
from pivot.retrieval.fakes import KeywordRetriever
from pivot.retrieval.models import RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService

_SPEC_CAP_004_COUNT = 100_000  # NFR-CAP-004 target; required only when opt-in


@dataclass(frozen=True)
class ChunkCapacityResult:
    count: int
    status: str
    evidence_count: int
    traced_peak_bytes: int | None = None


def resolve_chunk_count(environ: Mapping[str, str] | None = None) -> int:
    env = os.environ if environ is None else environ
    raw = (env.get("PIVOT_CHUNK_COUNT") or "").strip()
    if not raw:
        raise RuntimeError("PIVOT_CHUNK_COUNT is required")
    try:
        count = int(raw)
    except ValueError as exc:
        raise RuntimeError("PIVOT_CHUNK_COUNT must be a positive integer") from exc
    if count <= 0:
        raise RuntimeError("PIVOT_CHUNK_COUNT must be a positive integer")
    if env.get("PIVOT_REQUIRE_100K") == "1" and count != _SPEC_CAP_004_COUNT:
        raise RuntimeError("PIVOT_REQUIRE_100K=1 requires PIVOT_CHUNK_COUNT=100000")
    return count


def retrieve_synthetic(*, count: int, text: str) -> ChunkCapacityResult:
    if count <= 0:
        raise ValueError("count must be positive")
    tracemalloc.start()
    try:
        chunks = synthetic_chunks(count=count, text=text)
        service = RetrievalService(
            corpus=chunks,
            dense=KeywordRetriever(chunks, "dense"),
            bm25=KeywordRetriever(chunks, "bm25"),
            policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=4, evidence_limit=4),
        )
        outcome = service.retrieve(RetrievalQuery(text=text, principal_id="usr_cap"))
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return ChunkCapacityResult(
        count=count,
        status=outcome.status,
        evidence_count=len(outcome.evidence),
        traced_peak_bytes=peak,
    )
