"""Injectable retrieval sizes. SPEC numeric windows remain TBD-P0."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalPolicy:
    dense_k: int
    bm25_k: int
    rrf_k: int
    evidence_limit: int
    # Relevance gate (ADR-014). Every field defaults to off, which keeps
    # the pre-gate behavior bit for bit. Values stay TBD-P0 until the
    # score-distribution calibration (line-three D) produces candidates
    # for the Owner to freeze under DR-010.
    rerank_floor: float | None = None
    dense_floor: float | None = None
    rerank_pool: int | None = None
    per_doc_cap: int | None = None

    def __post_init__(self) -> None:
        if min(self.dense_k, self.bm25_k, self.rrf_k, self.evidence_limit) <= 0:
            raise ValueError("retrieval policy sizes must be positive")
        for floor in (self.rerank_floor, self.dense_floor):
            if floor is not None and not math.isfinite(floor):
                raise ValueError("retrieval relevance floors must be finite")
        for size in (self.rerank_pool, self.per_doc_cap):
            if size is not None and size <= 0:
                raise ValueError("retrieval pool and per-document cap must be positive")
