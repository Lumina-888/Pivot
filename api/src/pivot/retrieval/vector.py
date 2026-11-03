"""Dense retriever that consumes a VectorStore. k and distance are injected, not frozen."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace as _replace_record

from pivot.retrieval.models import ChunkRecord, RankedHit
from pivot.retrieval.ports import QueryEmbedder, RetrieverError
from pivot.storage.protocols import VectorStore


def chunk_record_from_payload(hit: Mapping) -> ChunkRecord | None:
    payload = dict(hit.get("payload") or {})
    chunk_id = str(hit.get("chunk_id") or payload.get("chunk_id") or "")
    version_id = str(hit.get("version_id") or payload.get("version_id") or "")
    document_id = str(payload.get("document_id") or hit.get("document_id") or "")
    if not chunk_id or not version_id or not document_id:
        return None
    tags = payload.get("tags") or ()
    if isinstance(tags, str):
        tags = (tags,)
    else:
        tags = tuple(str(item) for item in tags)
    return ChunkRecord(
        chunk_id=chunk_id,
        version_id=version_id,
        document_id=document_id,
        text=str(payload.get("text") or ""),
        title=str(payload.get("title") or ""),
        space=str(payload.get("space") or ""),
        library_id=str(payload.get("library_id") or ""),
        tags=tags,
        ready=_flag(payload, "ready", default=False),
        current=_flag(payload, "current", default=False),
        allowed=_flag(payload, "allowed", default=False),
        expired=_flag(payload, "expired", default=False),
        deleted=_flag(payload, "deleted", default=False),
        index_generation=str(payload.get("index_generation") or ""),
        embedding_model_version=str(payload.get("embedding_model_version") or ""),
        retrieval_config_version=str(payload.get("retrieval_config_version") or ""),
        version_label=str(payload.get("version_label") or "v1"),
    )


def _flag(payload: Mapping, key: str, *, default: bool) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


class VectorStoreRetriever:
    def __init__(
        self,
        store: VectorStore,
        embedder: QueryEmbedder,
        *,
        source: str = "dense",
        library_id_for: Callable[[str], str | None] | None = None,
        folder_id_for: Callable[[str], str | None] | None = None,
    ) -> None:
        """Dense retriever over the native (base) collection.

        The base collection's payload is stamped at ingest and is
        never rewritten by claim/move reconcile (which only updates
        the per-library LlamaIndex collections). When
        ``library_id_for`` is given, a hit's record is backfilled
        from live document facts at build time, so /search's
        passes_filters sees the document's current library instead
        of a stale payload value (2026-11-03 local-real-deps
        defect 1). A resolver failure or an unresolvable version
        keeps the payload value (fail-closed fallback, same as the
        LlamaIndex payload resolver); it never guesses a library.
        ``folder_id_for`` is the same shape: a resolved folder
        (None = default folder) overwrites the payload folder, which
        native payloads do not carry.
        """
        self._store = store
        self._embedder = embedder
        self._source = source
        self._library_id_for = library_id_for
        self._folder_id_for = folder_id_for
        self._resolved: dict[str, ChunkRecord] = {}

    def _backfill(self, record: ChunkRecord) -> ChunkRecord:
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
            # folder_id_for returns None both for "default folder"
            # and for "unresolvable"; native payloads carry no folder,
            # so overwriting with None is safe in both cases, and a
            # resolved folder id is always authoritative.
            if resolved_folder is None or (
                isinstance(resolved_folder, str) and resolved_folder.strip()
            ):
                folder_id = resolved_folder
        if library_id == record.library_id and folder_id == record.folder_id:
            return record
        return _replace_record(
            record, library_id=library_id, folder_id=folder_id
        )

    def search(self, query: str, k: int) -> tuple[RankedHit, ...]:
        if k <= 0:
            raise RetrieverError("PROVIDER_TEMPORARY_ERROR", "k must be positive")
        try:
            vectors = self._embedder.embed([query])
        except Exception as exc:
            raise RetrieverError("PROVIDER_TEMPORARY_ERROR", "query embedding failed") from exc
        if not vectors or not vectors[0]:
            raise RetrieverError("PROVIDER_TEMPORARY_ERROR", "query embedding empty")
        try:
            hits = self._store.search(vectors[0], limit=k)
        except Exception as exc:
            raise RetrieverError("PROVIDER_TEMPORARY_ERROR", "vector search failed") from exc
        ranked: list[RankedHit] = []
        for hit in hits:
            payload = hit if isinstance(hit, Mapping) else {}
            chunk_id = str(payload.get("chunk_id") or "")
            if not chunk_id and isinstance(payload.get("payload"), Mapping):
                chunk_id = str(payload["payload"].get("chunk_id") or "")
            if not chunk_id:
                continue
            record = chunk_record_from_payload(payload)
            if record is not None:
                self._resolved[chunk_id] = self._backfill(record)
            score = payload.get("score")
            ranked.append(
                RankedHit(
                    chunk_id=chunk_id,
                    score=float(score or 0.0),
                    source=self._source,
                )
            )
        return tuple(ranked)

    def resolve(self, chunk_id: str) -> ChunkRecord | None:
        return self._resolved.get(chunk_id)
