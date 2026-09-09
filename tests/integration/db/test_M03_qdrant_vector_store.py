"""Qdrant VectorStore adapter. Default CI uses an injected client, not Compose."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pivot.storage.adapters.qdrant import QdrantVectorStore
from pivot.storage.config import VectorStoreConfig


class FakeQdrantClient:
    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.points: dict[str, dict[str, tuple[list[float], dict]]] = {}

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(self, collection_name: str, *, vector_size: int, distance: str) -> None:
        if not vector_size or not distance:
            raise ValueError("vector_size and distance are required")
        self.collections.add(collection_name)
        self.points.setdefault(collection_name, {})

    def upsert(self, collection_name: str, points) -> None:
        bucket = self.points.setdefault(collection_name, {})
        for point in points:
            payload = dict(point["payload"])
            bucket[str(point["id"])] = (list(point["vector"]), payload)

    def search(self, collection_name, query_vector, limit=10, query_filter=None):
        query = list(query_vector)
        hits = []
        for pid, (vector, payload) in self.points.get(collection_name, {}).items():
            if not _payload_matches(payload, query_filter):
                continue
            hits.append(SimpleNamespace(id=pid, score=_cosine(query, vector), payload=payload))
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def delete(self, collection_name, points_selector=None):
        bucket = self.points.get(collection_name, {})
        for pid, (_vector, payload) in list(bucket.items()):
            if _payload_matches(payload, points_selector):
                del bucket[pid]


def _payload_matches(payload: dict, selector: dict | None) -> bool:
    if not selector:
        return True
    for condition in selector.get("must", ()):
        if payload.get(condition["key"]) != condition["match"]["value"]:
            return False
    return True


def _cosine(left: list[float], right: list[float]) -> float:
    score = sum(a * b for a, b in zip(left, right, strict=False))
    norm_left = sum(value * value for value in left) ** 0.5
    norm_right = sum(value * value for value in right) ** 0.5
    if norm_left == 0 or norm_right == 0:
        return 0.0
    return score / (norm_left * norm_right)


def _store(client: FakeQdrantClient | None = None) -> tuple[FakeQdrantClient, QdrantVectorStore]:
    fake = client or FakeQdrantClient()
    return fake, QdrantVectorStore(
        fake,
        collection="pivot-chunks",
        ensure_collection=True,
        vector_size=4,
        distance="Cosine",
    )


def test_M03_qdrant_vector_store_requires_injected_collection():
    with pytest.raises(ValueError, match="collection"):
        QdrantVectorStore(FakeQdrantClient(), collection="")


def test_M03_qdrant_vector_store_upsert_requires_version_and_chunk():
    _, store = _store()
    with pytest.raises(ValueError, match="version_id"):
        store.upsert([{"vector": [1.0, 0.0, 0.0, 0.0], "chunk_id": "chk_1"}])
    with pytest.raises(ValueError, match="chunk_id"):
        store.upsert([{"vector": [1.0, 0.0, 0.0, 0.0], "version_id": "ver_1"}])


def test_M03_qdrant_vector_store_roundtrip_search_with_injected_client():
    fake, store = _store()
    store.upsert(
        [
            {
                "vector": [1.0, 0.0, 0.0, 0.0],
                "version_id": "ver_1",
                "chunk_id": "chk_1",
                "text_hash": "hash-1",
            },
            {
                "vector": [0.0, 1.0, 0.0, 0.0],
                "version_id": "ver_1",
                "chunk_id": "chk_2",
            },
        ]
    )
    hits = store.search([1.0, 0.0, 0.0, 0.0], limit=2)
    assert hits[0]["chunk_id"] == "chk_1"
    assert hits[0]["version_id"] == "ver_1"
    assert hits[0]["payload"]["text_hash"] == "hash-1"
    assert hits[0]["score"] > hits[1]["score"]
    assert fake.collection_exists("pivot-chunks") is True
    assert store.healthy() is True


def test_M03_qdrant_vector_store_search_filter_by_version_id():
    _, store = _store()
    store.upsert(
        [
            {"vector": [1.0, 0.0, 0.0, 0.0], "version_id": "ver_keep", "chunk_id": "chk_a"},
            {"vector": [1.0, 0.0, 0.0, 0.0], "version_id": "ver_drop", "chunk_id": "chk_b"},
        ]
    )
    hits = store.search([1.0, 0.0, 0.0, 0.0], limit=8, filters={"version_id": "ver_keep"})
    assert [item["chunk_id"] for item in hits] == ["chk_a"]


def test_M03_qdrant_vector_store_delete_by_chunk_id():
    _, store = _store()
    store.upsert(
        [
            {"vector": [1.0, 0.0, 0.0, 0.0], "version_id": "ver_1", "chunk_id": "chk_keep"},
            {"vector": [0.0, 1.0, 0.0, 0.0], "version_id": "ver_1", "chunk_id": "chk_drop"},
        ]
    )
    store.delete(chunk_id="chk_drop")
    hits = store.search([0.0, 1.0, 0.0, 0.0], limit=8)
    assert [item["chunk_id"] for item in hits] == ["chk_keep"]


def test_M03_qdrant_vector_store_delete_requires_selector():
    _, store = _store()
    store.upsert(
        [{"vector": [1.0, 0.0, 0.0, 0.0], "version_id": "ver_1", "chunk_id": "chk_1"}]
    )
    with pytest.raises(ValueError, match="version_id or chunk_id"):
        store.delete()
    assert store.search([1.0, 0.0, 0.0, 0.0], limit=1)[0]["chunk_id"] == "chk_1"


def test_M03_qdrant_adapter_source_has_no_hardcoded_endpoint():
    root = Path(__file__).resolve().parents[3]
    source = (root / "api" / "src" / "pivot" / "storage" / "adapters" / "qdrant.py").read_text(
        encoding="utf-8"
    )
    assert "127.0.0.1" not in source
    assert "localhost" not in source
    assert ":6333" not in source
    config = VectorStoreConfig(endpoint="vectors.test:443", collection="pivot-chunks")
    assert config.endpoint == "vectors.test:443"
    assert config.collection == "pivot-chunks"
