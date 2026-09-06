"""Hybrid retrieval with server-side filters (FR-SEARCH, FR-RAG)."""

from __future__ import annotations

from collections import defaultdict

from pivot.retrieval.filters import filter_corpus, passes_filters
from pivot.retrieval.models import (
    AskIntent,
    ChunkRecord,
    Evidence,
    ProviderCallNote,
    RetrievalOutcome,
    RetrievalQuery,
    SearchHit,
    VersionConflict,
)
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.ports import Reranker, Retriever, RetrieverError
from pivot.retrieval.rrf import fuse


class RetrievalService:
    def __init__(
        self,
        *,
        corpus: tuple[ChunkRecord, ...],
        dense: Retriever,
        bm25: Retriever,
        policy: RetrievalPolicy,
        reranker: Reranker | None = None,
    ) -> None:
        self._corpus = {chunk.chunk_id: chunk for chunk in corpus}
        self._all = corpus
        self._dense = dense
        self._bm25 = bm25
        self._reranker = reranker
        self._policy = policy
        self.provider_calls: list[ProviderCallNote] = []

    def search_documents(
        self, query: RetrievalQuery, limit: int | None = None
    ) -> tuple[SearchHit, ...]:
        allowed = filter_corpus(self._all, query)
        needle = query.text.lower()
        hits: list[SearchHit] = []
        seen: set[str] = set()
        for chunk in allowed:
            blob = f"{chunk.title} {chunk.text}".lower()
            if needle:
                terms = [term for term in needle.split() if term]
                if needle not in blob and not any(term in blob for term in terms):
                    continue
            if chunk.document_id in seen:
                continue
            seen.add(chunk.document_id)
            hits.append(
                SearchHit(
                    document_id=chunk.document_id,
                    version_id=chunk.version_id,
                    title=chunk.title,
                    snippet=chunk.text[:180],
                    space=chunk.space,
                    index_generation=chunk.index_generation,
                    embedding_model_version=chunk.embedding_model_version,
                    retrieval_config_version=chunk.retrieval_config_version,
                )
            )
        if limit is not None:
            return tuple(hits[:limit])
        return tuple(hits)

    def ask_from_search(self, question: str, hit: SearchHit | None) -> AskIntent:
        if hit is None:
            return AskIntent(question=question, scope_type="global")
        return AskIntent(
            question=question,
            scope_type="document",
            scope_document_id=hit.document_id,
        )

    def retrieve(self, query: RetrievalQuery) -> RetrievalOutcome:
        self.provider_calls.clear()
        warnings: list[str] = []
        dense_hits = self._search_one(
            self._dense, "dense", query.text, self._policy.dense_k, warnings
        )
        bm25_hits = self._search_one(
            self._bm25, "bm25", query.text, self._policy.bm25_k, warnings
        )
        if dense_hits is None and bm25_hits is None:
            return RetrievalOutcome(
                status="failed",
                evidence=(),
                warnings=tuple(warnings),
                error_code="PROVIDER_TEMPORARY_ERROR",
            )
        lists = tuple(hits for hits in (dense_hits, bm25_hits) if hits is not None)
        fused = fuse(lists, self._policy.rrf_k)
        filtered_ids = []
        for hit in fused:
            chunk = self._corpus.get(hit.chunk_id)
            if chunk is None:
                continue
            if not passes_filters(chunk, query):
                continue
            filtered_ids.append(hit.chunk_id)
        if not filtered_ids:
            return RetrievalOutcome(status="empty", evidence=(), warnings=tuple(warnings))
        ordered_ids = tuple(filtered_ids)
        if self._reranker is not None:
            texts = {chunk_id: self._corpus[chunk_id].text for chunk_id in ordered_ids}
            reranked = self._reranker.rerank(
                query.text, ordered_ids, texts, self._policy.evidence_limit
            )
            ordered_ids = tuple(hit.chunk_id for hit in reranked)
        evidence = []
        fused_scores = {hit.chunk_id: hit.score for hit in fused}
        for chunk_id in ordered_ids[: self._policy.evidence_limit]:
            chunk = self._corpus[chunk_id]
            evidence.append(
                Evidence(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    version_id=chunk.version_id,
                    text=chunk.text,
                    score=fused_scores.get(chunk_id, 0.0),
                    index_generation=chunk.index_generation,
                    embedding_model_version=chunk.embedding_model_version,
                    retrieval_config_version=chunk.retrieval_config_version,
                    version_label=chunk.version_label,
                    effective_from=chunk.effective_from,
                )
            )
        return RetrievalOutcome(
            status="ok",
            evidence=tuple(evidence),
            warnings=tuple(warnings),
            conflicts=self._conflicts(tuple(evidence)),
        )

    def _search_one(
        self, retriever: Retriever, name: str, text: str, k: int, warnings: list[str]
    ):
        try:
            hits = retriever.search(text, k)
            self.provider_calls.append(
                ProviderCallNote(provider=name, operation="search", status="ok")
            )
            return hits
        except RetrieverError as error:
            warnings.append(f"{name}_failed")
            self.provider_calls.append(
                ProviderCallNote(
                    provider=name,
                    operation="search",
                    status="failed",
                    error_code=error.code,
                )
            )
            return None

    def _conflicts(self, evidence: tuple[Evidence, ...]) -> tuple[VersionConflict, ...]:
        grouped: dict[str, set[str]] = defaultdict(set)
        for item in evidence:
            grouped[item.document_id].add(item.version_id)
        return tuple(
            VersionConflict(document_id=document_id, versions=tuple(sorted(version_ids)))
            for document_id, version_ids in grouped.items()
            if len(version_ids) > 1
        )
