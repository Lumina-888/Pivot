"""Deterministic retrievers for tests. No provider URLs or keys."""

from __future__ import annotations

from collections.abc import Sequence

from pivot.retrieval.models import ChunkRecord, RankedHit
from pivot.retrieval.ports import RetrieverError


class HashingQueryEmbedder:
    """Injected Fake query embedder. Dimension is not a frozen production default."""

    def __init__(self, dimension: int) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.dimension = dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            seed = float((len(text) + sum(ord(ch) for ch in text[:8])) % 97 or 1)
            vectors.append([seed / (index + 1) for index in range(self.dimension)])
        return vectors


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
