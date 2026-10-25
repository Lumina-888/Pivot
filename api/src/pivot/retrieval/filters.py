"""Server-side retrieval filters (FR-RAG-002/003). Prompt text is ignored."""

from __future__ import annotations

from pivot.retrieval.models import ChunkRecord, RetrievalQuery


def passes_filters(chunk: ChunkRecord, query: RetrievalQuery) -> bool:
    if not chunk.ready or not chunk.current or chunk.expired or chunk.deleted:
        return False
    if not chunk.allowed:
        return False
    if query.library_ids is not None:
        # Library scope, plus the exception channel (ADR-017 D1): a
        # chunk whose document carries a live exception grant for the
        # caller passes even when its library is not visible. Exceptions
        # never widen a library, only the granted document.
        if (
            chunk.library_id not in query.library_ids
            and chunk.document_id not in query.exception_document_ids
        ):
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
