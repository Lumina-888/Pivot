"""Reciprocal rank fusion. The k parameter is injected, not frozen."""

from __future__ import annotations

from collections import defaultdict

from pivot.retrieval.models import RankedHit


def fuse(ranked_lists: tuple[tuple[RankedHit, ...], ...], rrf_k: int) -> tuple[RankedHit, ...]:
    scores: dict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        seen: set[str] = set()
        for rank, hit in enumerate(ranked, start=1):
            if hit.chunk_id in seen:
                continue
            seen.add(hit.chunk_id)
            scores[hit.chunk_id] += 1.0 / (rrf_k + rank)
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return tuple(
        RankedHit(chunk_id=chunk_id, score=score, source="rrf")
        for chunk_id, score in ordered
    )
