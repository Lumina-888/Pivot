"""Dense/BM25/rerank ports. BM25 is stdlib; dense/rerank vendors stay injected fakes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pivot.retrieval.models import RankedHit


class Retriever(Protocol):
    def search(self, query: str, k: int) -> tuple[RankedHit, ...]: ...


class QueryEmbedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class Reranker(Protocol):
    def rerank(
        self, query: str, chunk_ids: tuple[str, ...], texts: dict[str, str], limit: int
    ) -> tuple[RankedHit, ...]: ...


class RetrieverError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
