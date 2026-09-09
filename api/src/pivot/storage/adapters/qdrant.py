"""Qdrant-backed VectorStore. Endpoint and collection are injected.

Payload traceability (version_id + chunk_id) stays in this module so M07 can
validate rebuildable points without importing the Qdrant SDK.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from pivot.storage.config import VectorStoreConfig
from pivot.storage.protocols import VectorStore

__all__ = [
    "QdrantVectorStore",
    "VectorStore",
    "build_payload",
    "connect_qdrant_client",
    "validate_payload",
]

_REQUIRED_PAYLOAD_KEYS = frozenset({"version_id", "chunk_id"})


def build_payload(
    *, version_id: str, chunk_id: str, text_hash: str | None = None, **metadata
) -> dict:
    """Build a traceable vector payload from persisted identifiers."""
    if not version_id or not chunk_id:
        raise ValueError("version_id and chunk_id are required")
    payload = {"version_id": version_id, "chunk_id": chunk_id}
    if text_hash is not None:
        payload["text_hash"] = text_hash
    payload.update(metadata)
    return payload


def validate_payload(payload: Mapping) -> bool:
    """Validate the minimum Qdrant payload traceability invariant."""
    if not isinstance(payload, Mapping) or not _REQUIRED_PAYLOAD_KEYS <= payload.keys():
        raise ValueError("Qdrant payload must contain version_id and chunk_id")
    if not all(isinstance(payload[key], str) and payload[key] for key in _REQUIRED_PAYLOAD_KEYS):
        raise ValueError("version_id and chunk_id must be non-empty strings")
    return True


class QdrantClient(Protocol):
    def collection_exists(self, collection_name: str) -> bool: ...
    def create_collection(
        self, collection_name: str, *, vector_size: int, distance: str
    ) -> None: ...
    def upsert(self, collection_name: str, points) -> None: ...
    def search(
        self, collection_name, query_vector, limit=10, query_filter=None
    ) -> list: ...
    def delete(self, collection_name, points_selector=None) -> None: ...


def _normalize_endpoint(endpoint: str) -> str:
    raw = endpoint.strip()
    if not raw:
        raise RuntimeError("PIVOT_QDRANT_ENDPOINT is required when PIVOT_VECTOR_STORE=qdrant")
    if "://" not in raw:
        return f"http://{raw.rstrip('/')}"
    return raw.rstrip("/")


def connect_qdrant_client(*, endpoint: str, api_key: str | None = None):
    url = _normalize_endpoint(endpoint)
    try:
        from qdrant_client import QdrantClient as SdkQdrantClient
    except ImportError as exc:
        raise RuntimeError("qdrant extra is not installed; pip install -e ./api[qdrant]") from exc
    kwargs: dict[str, object] = {"url": url}
    if api_key:
        kwargs["api_key"] = api_key
    return _SdkQdrantClient(SdkQdrantClient(**kwargs))


class _SdkQdrantClient:
    """Translate port-shaped calls into qdrant-client models."""

    def __init__(self, client) -> None:
        self._client = client

    def collection_exists(self, collection_name: str) -> bool:
        return bool(self._client.collection_exists(collection_name=collection_name))

    def create_collection(self, collection_name: str, *, vector_size: int, distance: str) -> None:
        from qdrant_client.http.models import Distance, VectorParams

        self._client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance(distance)),
        )

    def upsert(self, collection_name: str, points) -> None:
        from qdrant_client.http.models import PointStruct

        converted = [
            PointStruct(
                id=point["id"],
                vector=list(point["vector"]),
                payload=dict(point["payload"]),
            )
            for point in points
        ]
        self._client.upsert(collection_name=collection_name, points=converted)

    def search(self, collection_name, query_vector, limit=10, query_filter=None):
        qfilter = _sdk_filter(query_filter)
        return self._client.search(
            collection_name=collection_name,
            query_vector=list(query_vector),
            limit=limit,
            query_filter=qfilter,
        )

    def delete(self, collection_name, points_selector=None) -> None:
        from qdrant_client.http.models import FilterSelector

        qfilter = _sdk_filter(points_selector)
        if qfilter is None:
            raise ValueError("points_selector is required")
        self._client.delete(
            collection_name=collection_name,
            points_selector=FilterSelector(filter=qfilter),
        )


def _sdk_filter(selector: Mapping | None):
    if not selector:
        return None
    from qdrant_client.http.models import FieldCondition, Filter, MatchValue

    must = [
        FieldCondition(key=condition["key"], match=MatchValue(value=condition["match"]["value"]))
        for condition in selector.get("must", ())
    ]
    if not must:
        return None
    return Filter(must=must)


class QdrantVectorStore:
    """VectorStore that talks to an injected Qdrant-compatible client."""

    def __init__(
        self,
        client: QdrantClient,
        *,
        collection: str,
        ensure_collection: bool = False,
        vector_size: int | None = None,
        distance: str | None = None,
    ) -> None:
        if not collection.strip():
            raise ValueError("collection is required")
        self._client = client
        self._collection = collection
        if ensure_collection and not client.collection_exists(collection):
            if vector_size is None or vector_size <= 0 or not (distance or "").strip():
                raise ValueError("vector_size and distance are required to ensure collection")
            client.create_collection(
                collection, vector_size=vector_size, distance=distance.strip()
            )

    @classmethod
    def connect(
        cls,
        config: VectorStoreConfig,
        *,
        api_key: str | None = None,
        ensure_collection: bool = False,
        vector_size: int | None = None,
        distance: str | None = None,
    ) -> "QdrantVectorStore":
        client = connect_qdrant_client(endpoint=config.endpoint, api_key=api_key)
        return cls(
            client,
            collection=config.collection,
            ensure_collection=ensure_collection,
            vector_size=vector_size,
            distance=distance,
        )

    def healthy(self) -> bool:
        try:
            return bool(self._client.collection_exists(self._collection))
        except Exception:
            return False

    def upsert(self, points: Iterable[Mapping]) -> None:
        converted: list[dict] = []
        for point in points:
            payload = _point_payload(point)
            validate_payload(payload)
            vector = _point_vector(point)
            converted.append(
                {
                    "id": _point_id(str(payload["chunk_id"])),
                    "vector": vector,
                    "payload": payload,
                }
            )
        if converted:
            self._client.upsert(self._collection, converted)

    def search(
        self, vector: Iterable[float], *, limit: int, filters: Mapping | None = None
    ) -> list[Mapping]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        hits = self._client.search(
            self._collection,
            list(vector),
            limit=limit,
            query_filter=_payload_selector(filters),
        )
        return [_hit_mapping(hit) for hit in hits]

    def delete(self, *, version_id: str | None = None, chunk_id: str | None = None) -> None:
        selector = _payload_selector(
            {
                key: value
                for key, value in {"version_id": version_id, "chunk_id": chunk_id}.items()
                if value
            }
        )
        if selector is None:
            raise ValueError("version_id or chunk_id is required")
        self._client.delete(self._collection, points_selector=selector)


def _point_payload(point: Mapping) -> dict:
    nested = point.get("payload")
    source = dict(nested) if isinstance(nested, Mapping) else dict(point)
    version_id = source.get("version_id")
    chunk_id = source.get("chunk_id")
    extra = {
        key: value
        for key, value in source.items()
        if key not in {"id", "vector", "payload", "version_id", "chunk_id", "text_hash"}
    }
    return build_payload(
        version_id="" if version_id is None else str(version_id),
        chunk_id="" if chunk_id is None else str(chunk_id),
        text_hash=source.get("text_hash"),
        **extra,
    )


def _point_vector(point: Mapping) -> list[float]:
    vector = point.get("vector")
    if vector is None:
        raise ValueError("vector is required")
    values = [float(item) for item in vector]
    if not values:
        raise ValueError("vector is required")
    return values


def _point_id(chunk_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"pivot:chunk:{chunk_id}"))


def _payload_selector(filters: Mapping | None) -> dict | None:
    if not filters:
        return None
    must = [
        {"key": key, "match": {"value": value}}
        for key, value in filters.items()
        if value is not None and value != ""
    ]
    if not must:
        return None
    return {"must": must}


def _hit_mapping(hit) -> dict:
    if isinstance(hit, Mapping):
        payload = dict(hit.get("payload") or {})
        identifier = hit.get("id")
        score = hit.get("score")
    else:
        payload = dict(getattr(hit, "payload", None) or {})
        identifier = getattr(hit, "id", None)
        score = getattr(hit, "score", None)
    return {
        "id": identifier,
        "score": score,
        "version_id": payload.get("version_id"),
        "chunk_id": payload.get("chunk_id"),
        "payload": payload,
    }
