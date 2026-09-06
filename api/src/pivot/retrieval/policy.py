"""Injectable retrieval sizes. SPEC numeric windows remain TBD-P0."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalPolicy:
    dense_k: int
    bm25_k: int
    rrf_k: int
    evidence_limit: int

    def __post_init__(self) -> None:
        if min(self.dense_k, self.bm25_k, self.rrf_k, self.evidence_limit) <= 0:
            raise ValueError("retrieval policy sizes must be positive")
