"""Deterministic retrievers for tests. No provider URLs or keys."""

from __future__ import annotations

from collections.abc import Sequence

from pivot.retrieval.models import ChunkRecord, RankedHit
from pivot.retrieval.ports import RetrieverError


class ScriptedJsonHttpClient:
    """Injected Fake JSON transport. No network and no provider URLs."""

    def __init__(
        self,
        responses: list[dict] | None = None,
        *,
        error: Exception | None = None,
        handler=None,
    ) -> None:
        self.calls: list[dict] = []
        self._responses = list(responses or [])
        self._error = error
        self._handler = handler

    def post_json(self, url: str, payload: dict, headers, timeout: float | None = None) -> dict:
        self.calls.append(
            {
                "url": url,
                "payload": payload,
                "headers": dict(headers),
                "timeout": timeout,
            }
        )
        if self._error is not None:
            raise self._error
        if self._handler is not None:
            return self._handler(url, payload, headers, timeout)
        if not self._responses:
            raise RuntimeError("no scripted JSON response")
        return self._responses.pop(0)


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


class FailingReranker:
    def __init__(self, code: str = "PROVIDER_TEMPORARY_ERROR") -> None:
        self._code = code

    def rerank(
        self, query: str, chunk_ids: tuple[str, ...], texts: dict[str, str], limit: int
    ) -> tuple[RankedHit, ...]:
        raise RetrieverError(self._code, "rerank unavailable")


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
