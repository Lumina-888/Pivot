"""stdlib BM25. k1/b/tokenizer are injected; this is not a vendor sparse encoder."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

from pivot.retrieval.models import ChunkRecord, RankedHit
from pivot.retrieval.ports import RetrieverError
from pivot.retrieval.tokenize import Tokenizer


def _idf(n_docs: int, df: int) -> float:
    return math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))


class Bm25Retriever:
    def __init__(self, tokenizer: Tokenizer, *, k1: float, b: float, source: str = "bm25") -> None:
        if k1 <= 0:
            raise ValueError("k1 must be positive")
        if b < 0 or b > 1:
            raise ValueError("b must be between 0 and 1")
        self._tokenizer = tokenizer
        self._k1 = k1
        self._b = b
        self._source = source
        self._chunks: dict[str, ChunkRecord] = {}
        self._tokens: dict[str, tuple[str, ...]] = {}
        self._df: dict[str, int] = {}
        self._avgdl = 1.0

    def add(self, chunks: Sequence[ChunkRecord]) -> None:
        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk
            self._tokens[chunk.chunk_id] = self._tokenizer.tokenize(
                f"{chunk.title} {chunk.text}"
            )
        self._rebuild()

    def search(self, query: str, k: int) -> tuple[RankedHit, ...]:
        if k <= 0:
            raise RetrieverError("PROVIDER_TEMPORARY_ERROR", "k must be positive")
        try:
            query_tokens = self._tokenizer.tokenize(query)
        except Exception as exc:
            raise RetrieverError("PROVIDER_TEMPORARY_ERROR", "bm25 tokenize failed") from exc
        if not query_tokens or not self._chunks:
            return ()
        n_docs = len(self._chunks)
        scored: list[RankedHit] = []
        for chunk_id, tokens in self._tokens.items():
            score = _bm25_score(
                query_tokens,
                tokens,
                df=self._df,
                n_docs=n_docs,
                avgdl=self._avgdl,
                k1=self._k1,
                b=self._b,
            )
            if score > 0:
                scored.append(RankedHit(chunk_id=chunk_id, score=score, source=self._source))
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return tuple(scored[:k])

    def resolve(self, chunk_id: str) -> ChunkRecord | None:
        return self._chunks.get(chunk_id)

    def _rebuild(self) -> None:
        df: dict[str, int] = {}
        total = 0
        for tokens in self._tokens.values():
            total += len(tokens)
            for term in set(tokens):
                df[term] = df.get(term, 0) + 1
        self._df = df
        self._avgdl = (total / len(self._tokens)) if self._tokens else 1.0


class Bm25Reranker:
    def __init__(self, tokenizer: Tokenizer, *, k1: float, b: float) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be positive")
        if b < 0 or b > 1:
            raise ValueError("b must be between 0 and 1")
        self._tokenizer = tokenizer
        self._k1 = k1
        self._b = b

    def rerank(
        self, query: str, chunk_ids: tuple[str, ...], texts: dict[str, str], limit: int
    ) -> tuple[RankedHit, ...]:
        query_tokens = self._tokenizer.tokenize(query)
        tokenized = {
            chunk_id: self._tokenizer.tokenize(texts.get(chunk_id, ""))
            for chunk_id in chunk_ids
        }
        n_docs = len(tokenized) or 1
        df: dict[str, int] = {}
        total = 0
        for tokens in tokenized.values():
            total += len(tokens)
            for term in set(tokens):
                df[term] = df.get(term, 0) + 1
        avgdl = (total / n_docs) if n_docs else 1.0
        ranked: list[RankedHit] = []
        for chunk_id in chunk_ids:
            score = _bm25_score(
                query_tokens,
                tokenized.get(chunk_id, ()),
                df=df,
                n_docs=n_docs,
                avgdl=avgdl,
                k1=self._k1,
                b=self._b,
            )
            ranked.append(RankedHit(chunk_id=chunk_id, score=score, source="rerank"))
        ranked.sort(key=lambda hit: hit.score, reverse=True)
        return tuple(ranked[:limit])


def _bm25_score(
    query_tokens: Sequence[str],
    doc_tokens: Sequence[str],
    *,
    df: dict[str, int],
    n_docs: int,
    avgdl: float,
    k1: float,
    b: float,
) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    tf_map = Counter(doc_tokens)
    length_norm = 1.0 - b + b * (len(doc_tokens) / (avgdl or 1.0))
    score = 0.0
    seen: set[str] = set()
    for term in query_tokens:
        if term in seen:
            continue
        seen.add(term)
        tf = tf_map.get(term, 0)
        if tf <= 0:
            continue
        denom = tf + k1 * length_norm
        score += _idf(n_docs, df.get(term, 0)) * (tf * (k1 + 1.0) / denom)
    return score
