"""stdlib BM25. k1/b/tokenizer are injected; this is not a vendor sparse encoder."""

from __future__ import annotations

import logging
import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace as _replace_record

from pivot.retrieval.models import ChunkRecord, RankedHit
from pivot.retrieval.ports import RetrieverError
from pivot.retrieval.tokenize import Tokenizer
from pivot.retrieval.vector import chunk_record_from_payload


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
            self._tokens[chunk.chunk_id] = self._tokenizer.tokenize(f"{chunk.title} {chunk.text}")
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


class LiveBm25Retriever(Bm25Retriever):
    """Query-time BM25 over the base (native) collection.

    The /search BM25 leg used to be a startup snapshot: bootstrap
    scrolled the base collection once at assembly, so documents
    ingested after startup (sync or Celery) did not enter the leg
    until the next restart (2026-11-03 local-real-deps defect 2
    residual). This wrapper rebuilds from the base collection on
    every search() instead, so it sees ingest, claim and move
    without a restart, in a single process or many: every process
    rebuilds from the same persistent collection, so no in-process
    add() can be missed by another process, and no persistent
    sparse index (storage, versions, migrations) is needed at the
    current corpus scale.

    Records are built with chunk_record_from_payload, then
    backfilled with the same live library/folder resolvers the
    /search dense leg uses (defect 1): a library resolver that
    returns a non-empty string wins, a folder resolver result
    (None = default folder) always wins. When version_is_live is
    given, a record is kept only when its version is live: the
    version exists, is current, and its document is not deleted.
    That filter is required, not defensive: the base collection
    is never cleaned on delete or supersede (IndexPublisher has
    no delete; request_delete only flips DB flags), so old points
    still sit in the collection with stale ready/current payload
    flags, and passes_filters alone would keep serving them.

    A scroll/rebuild failure logs and returns an empty leg, so
    the dense leg keeps serving (same degradation as the old
    startup snapshot when its population failed). add() is kept
    for the pre-existing assembly.bm25.add() callers: manually
    added records are merged into each rebuild, with live scroll
    records winning on a chunk_id collision.
    """

    def __init__(
        self,
        load_payloads: Callable[[], tuple[Mapping, ...]],
        tokenizer: Tokenizer,
        *,
        k1: float,
        b: float,
        library_id_for: Callable[[str], str | None] | None = None,
        folder_id_for: Callable[[str], str | None] | None = None,
        version_is_live: Callable[[str], bool] | None = None,
        source: str = "bm25",
    ) -> None:
        super().__init__(tokenizer, k1=k1, b=b, source=source)
        self._load_payloads = load_payloads
        self._library_id_for = library_id_for
        self._folder_id_for = folder_id_for
        self._version_is_live = version_is_live
        self._manual: dict[str, ChunkRecord] = {}
        self._resolved: dict[str, ChunkRecord] = {}

    def add(self, chunks: Sequence[ChunkRecord]) -> None:
        for chunk in chunks:
            self._manual[chunk.chunk_id] = chunk
            self._resolved[chunk.chunk_id] = chunk

    def search(self, query: str, k: int) -> tuple[RankedHit, ...]:
        if k <= 0:
            raise RetrieverError("PROVIDER_TEMPORARY_ERROR", "k must be positive")
        try:
            records = self._rebuild_records()
        except Exception:
            logging.getLogger(__name__).exception(
                "failed to rebuild /search BM25 index from base collection; "
                "dense leg still serves, BM25 leg stays empty for this query"
            )
            self._resolved = {}
            return ()
        self._chunks = dict(records)
        self._tokens = {
            chunk_id: self._tokenizer.tokenize(f"{chunk.title} {chunk.text}")
            for chunk_id, chunk in records.items()
        }
        self._rebuild()
        self._resolved = dict(records)
        return super().search(query, k)

    def resolve(self, chunk_id: str) -> ChunkRecord | None:
        return self._resolved.get(chunk_id)

    def _rebuild_records(self) -> dict[str, ChunkRecord]:
        records: dict[str, ChunkRecord] = dict(self._manual)
        for payload in self._load_payloads():
            record = chunk_record_from_payload(payload)
            if record is None:
                continue
            if self._version_is_live is not None:
                try:
                    live = self._version_is_live(record.version_id)
                except Exception:
                    live = False
                if not live:
                    continue
            library_id = record.library_id
            folder_id = record.folder_id
            if self._library_id_for is not None:
                try:
                    resolved = self._library_id_for(record.version_id)
                except Exception:
                    resolved = None
                if isinstance(resolved, str) and resolved.strip():
                    library_id = resolved
            if self._folder_id_for is not None:
                try:
                    resolved_folder = self._folder_id_for(record.version_id)
                except Exception:
                    resolved_folder = None
                if resolved_folder is None or (
                    isinstance(resolved_folder, str) and resolved_folder.strip()
                ):
                    folder_id = resolved_folder
            if library_id != record.library_id or folder_id != record.folder_id:
                record = _replace_record(
                    record, library_id=library_id, folder_id=folder_id
                )
            records[record.chunk_id] = record
        return records


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
            chunk_id: self._tokenizer.tokenize(texts.get(chunk_id, "")) for chunk_id in chunk_ids
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
