"""Deterministic retrievers for tests. No provider URLs or keys."""

from __future__ import annotations

from pivot.retrieval.models import ChunkRecord, RankedHit
from pivot.retrieval.ports import RetrieverError


class KeywordRetriever:
    def __init__(self, corpus: tuple[ChunkRecord, ...], source: str) -> None:
        self._corpus = corpus
        self._source = source

    def search(self, query: str, k: int) -> tuple[RankedHit, ...]:
        terms = [term.lower() for term in query.split() if term.strip()]
        scored: list[RankedHit] = []
        for chunk in self._corpus:
            blob = f"{chunk.title} {chunk.text}".lower()
            score = sum(blob.count(term) for term in terms)
            if score > 0:
                scored.append(
                    RankedHit(
                        chunk_id=chunk.chunk_id, score=float(score), source=self._source
                    )
                )
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return tuple(scored[:k])


class FailingRetriever:
    def __init__(self, code: str = "PROVIDER_TEMPORARY_ERROR") -> None:
        self._code = code

    def search(self, query: str, k: int) -> tuple[RankedHit, ...]:
        raise RetrieverError(self._code, f"{self._code} from {query[:12]}")


class OverlapReranker:
    def rerank(
        self, query: str, chunk_ids: tuple[str, ...], texts: dict[str, str], limit: int
    ) -> tuple[RankedHit, ...]:
        terms = [term.lower() for term in query.split() if term.strip()]
        ranked = []
        for chunk_id in chunk_ids:
            blob = texts.get(chunk_id, "").lower()
            score = sum(blob.count(term) for term in terms)
            ranked.append(RankedHit(chunk_id=chunk_id, score=float(score), source="rerank"))
        ranked.sort(key=lambda hit: hit.score, reverse=True)
        return tuple(ranked[:limit])
