"""Index generation publish buffer. Uses M03 payload contract, not Qdrant SDK."""

from __future__ import annotations

from dataclasses import dataclass, field

from pivot.storage.adapters.qdrant import build_payload, validate_payload


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


class IndexPublisher:
    def __init__(self) -> None:
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
    ) -> None:
        generation = self._generations[generation_id]
        if generation.status != "building":
            raise RuntimeError("generation is not writable")
        payload = build_payload(version_id=version_id, chunk_id=chunk_id, text_hash=text_hash)
        validate_payload(payload)
        generation.vectors.append(
            VectorRecord(
                chunk_id=chunk_id, version_id=version_id, vector=vector, payload=payload
            )
        )

    def publish(self, generation_id: str) -> IndexGeneration:
        generation = self._generations[generation_id]
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
