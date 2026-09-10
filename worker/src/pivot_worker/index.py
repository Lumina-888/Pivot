"""Index generation publish buffer. Uses M03 payload contract, not Qdrant SDK."""

from __future__ import annotations

from dataclasses import dataclass, field

from pivot.parsing.errors import ParseError, parse_error
from pivot.storage.adapters.qdrant import build_payload, validate_payload
from pivot.storage.protocols import VectorStore


@dataclass
class VectorRecord:
    chunk_id: str
    version_id: str
    vector: list[float]
    payload: dict


@dataclass
class IndexGeneration:
    id: str
    dimension: int
    embedding_model_version: str
    status: str = "building"
    vectors: list[VectorRecord] = field(default_factory=list)


def _metadata_value(value: object) -> object:
    if isinstance(value, tuple):
        return [item for item in value]
    return value


class IndexPublisher:
    def __init__(self, store: VectorStore | None = None) -> None:
        self._store = store
        self._generations: dict[str, IndexGeneration] = {}
        self._published: dict[str, IndexGeneration] = {}

    def start(
        self, generation_id: str, dimension: int, embedding_model_version: str
    ) -> IndexGeneration:
        generation = IndexGeneration(
            id=generation_id,
            dimension=dimension,
            embedding_model_version=embedding_model_version,
        )
        self._generations[generation_id] = generation
        return generation

    def add_vector(
        self,
        generation_id: str,
        *,
        version_id: str,
        chunk_id: str,
        vector: list[float],
        text_hash: str,
        **metadata: object,
    ) -> None:
        generation = self._generations[generation_id]
        if generation.status != "building":
            raise RuntimeError("generation is not writable")
        extra = {
            key: _metadata_value(value)
            for key, value in metadata.items()
            if value is not None
        }
        payload = build_payload(
            version_id=version_id, chunk_id=chunk_id, text_hash=text_hash, **extra
        )
        validate_payload(payload)
        generation.vectors.append(
            VectorRecord(
                chunk_id=chunk_id, version_id=version_id, vector=vector, payload=payload
            )
        )

    def publish(self, generation_id: str) -> IndexGeneration:
        generation = self._generations[generation_id]
        if generation.status != "building":
            raise RuntimeError("generation is not writable")
        if self._store is not None:
            self._require_document_ids(generation)
            try:
                self._store.upsert(
                    ({"vector": record.vector, **record.payload} for record in generation.vectors)
                )
            except ParseError:
                generation.status = "failed"
                raise
            except Exception as exc:
                generation.status = "failed"
                raise parse_error("PROVIDER_TEMPORARY_ERROR", "vector store upsert failed") from exc
        generation.status = "published"
        self._published[generation_id] = generation
        return generation

    def abort(self, generation_id: str) -> None:
        generation = self._generations.get(generation_id)
        if generation is None:
            return
        generation.status = "failed"
        generation.vectors.clear()

    def published_vectors(self, generation_id: str) -> tuple[VectorRecord, ...]:
        generation = self._published.get(generation_id)
        if generation is None:
            return ()
        return tuple(generation.vectors)

    def _require_document_ids(self, generation: IndexGeneration) -> None:
        for record in generation.vectors:
            document_id = record.payload.get("document_id")
            if not isinstance(document_id, str) or not document_id.strip():
                generation.status = "failed"
                raise parse_error(
                    "RESOURCE_LIMIT", "document_id is required to publish to VectorStore"
                )
