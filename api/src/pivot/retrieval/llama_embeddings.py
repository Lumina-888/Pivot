"""Bridge the existing injectable QueryEmbedder to LlamaIndex."""

from __future__ import annotations

import asyncio
import math

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.bridge.pydantic import PrivateAttr

from pivot.retrieval.ports import QueryEmbedder


class PivotEmbedding(BaseEmbedding):
    """Use the same explicit provider for indexing and queries.

    Provider handles (including credentials) are private, never model fields.
    Callers must pass the same model version/dimension when reloading an index.
    """

    _provider: QueryEmbedder = PrivateAttr()
    _dimension: int = PrivateAttr()

    def __init__(self, provider: QueryEmbedder, *, model_name: str, dimension: int):
        if not model_name.strip() or dimension <= 0:
            raise ValueError("embedding model name and positive dimension are required")
        super().__init__(model_name=model_name)
        self._provider = provider
        self._dimension = dimension

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._provider.embed(texts)
        if len(vectors) != len(texts):
            raise ValueError("embedding response count mismatch")
        result = []
        for vector in vectors:
            if len(vector) != self._dimension or any(not math.isfinite(x) for x in vector):
                raise ValueError("embedding dimension or values invalid")
            if not any(vector):
                raise ValueError("embedding vector must be nonzero")
            result.append(list(vector))
        return result

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._embed([query])[0]

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return await asyncio.to_thread(self._get_query_embedding, query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)
