"""Embedding port. Tests use a deterministic fake; no provider URLs or keys."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pivot.parsing.errors import parse_error


class EmbeddingPort(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class FakeEmbedding:
    def __init__(self, dimension: int, fail: bool = False) -> None:
        self.dimension = dimension
        self.fail = fail

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if self.fail:
            raise parse_error("PROVIDER_TEMPORARY_ERROR", "embedding unavailable")
        vectors = []
        for text in texts:
            seed = float(len(text) % 97)
            vectors.append([seed / (index + 1) for index in range(self.dimension)])
        return vectors


def assert_dimension(vectors: Sequence[Sequence[float]], expected: int) -> None:
    if not vectors:
        raise parse_error("EMPTY_TEXT", "no vectors")
    for vector in vectors:
        if len(vector) != expected:
            raise parse_error("RESOURCE_LIMIT", "embedding dimension mismatch")
