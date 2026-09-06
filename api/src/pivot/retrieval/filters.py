"""Server-side retrieval filters (FR-RAG-002/003). Prompt text is ignored."""

from __future__ import annotations

from pivot.retrieval.models import ChunkRecord, RetrievalQuery


def passes_filters(chunk: ChunkRecord, query: RetrievalQuery) -> bool:
    if not chunk.ready or not chunk.current or chunk.expired or chunk.deleted:
        return False
    if not chunk.allowed:
        return False
    if query.space and chunk.space != query.space:
        return False
    if query.tags and not set(query.tags).issubset(set(chunk.tags)):
        return False
    if query.scope_type == "document":
        if not query.scope_document_id:
            return False
        if chunk.document_id != query.scope_document_id:
            return False
    return True


def filter_corpus(
    corpus: tuple[ChunkRecord, ...], query: RetrievalQuery
) -> tuple[ChunkRecord, ...]:
    return tuple(chunk for chunk in corpus if passes_filters(chunk, query))
