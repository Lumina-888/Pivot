"""Worker unblock batch (2026-11-04 retest v1.2, Q1A/Q2/Q3C/Q4/Q5).

Covers D8-17 (worker image missing the http extra), D8-18 (example
missing PIVOT_QDRANT_DISTANCE), D8-05 (missing bucket/collection
misreported as unreachable), D8-04 (example web origin) and the Q5
qdrant probe budget. Not GATE-P0 verified.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pivot.retrieval.fakes import HashingQueryEmbedder
from pivot_worker.assembly import _llama_document_sync, _open_minio_store, _open_qdrant_store

_ROOT = Path(__file__).resolve().parents[3]
_DOCKERFILE = _ROOT / "Dockerfile.worker"
_EXAMPLE = _ROOT / "ops" / "compose.env.example"


def _example_assignment(text: str, key: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(key + "="):
            return stripped.split("=", 1)[1].strip()
    return None


def test_D8_17_worker_dockerfile_includes_http_extra() -> None:
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert "./api[postgres,minio,qdrant,redis,http]" in text


def test_D8_18_example_sets_qdrant_distance_cosine() -> None:
    text = _EXAMPLE.read_text(encoding="utf-8")
    assert _example_assignment(text, "PIVOT_QDRANT_DISTANCE") == "Cosine"


def test_D8_05_example_enables_ensure_flags_by_default() -> None:
    text = _EXAMPLE.read_text(encoding="utf-8")
    assert _example_assignment(text, "PIVOT_QDRANT_ENSURE_COLLECTION") == "1"
    assert _example_assignment(text, "PIVOT_MINIO_ENSURE_BUCKET") == "1"


def test_D8_04_example_api_origin_is_api_service_hostname() -> None:
    text = _EXAMPLE.read_text(encoding="utf-8")
    assert _example_assignment(text, "PIVOT_API_ORIGIN") == "http://api:8000"


class _FakeStore:
    def scroll(self, *, limit: int, offset: str | None):  # noqa: ARG002
        return [], None


class _FakeMinioClient:
    def __init__(self, *, exists: bool | None) -> None:
        self._exists = exists

    def bucket_exists(self, bucket: str) -> bool:  # noqa: ARG002
        if self._exists is None:
            raise ConnectionError("minio down")
        return self._exists


class _FakeQdrantClient:
    def __init__(self, *, exists: bool | None) -> None:
        self._exists = exists

    def collection_exists(self, collection: str) -> bool:  # noqa: ARG002
        if self._exists is None:
            raise ConnectionError("qdrant down")
        return self._exists


def _worker_minio_settings(client: object) -> SimpleNamespace:
    return SimpleNamespace(
        minio_endpoint="minio:9000",
        minio_bucket="pivot-docs",
        object_store_client=client,
        minio_access_key="pivotminio",
        minio_secret_key="pivot_dev_only",
        minio_secure=False,
        minio_ensure_bucket=False,
    )


def _worker_qdrant_settings(client: object) -> SimpleNamespace:
    return SimpleNamespace(
        qdrant_endpoint="qdrant:6333",
        qdrant_collection="pivot",
        vector_store_client=client,
        qdrant_api_key=None,
        qdrant_ensure_collection=False,
        qdrant_vector_size=4,
        qdrant_distance="Cosine",
    )


def test_D8_05_worker_missing_bucket_names_the_bucket() -> None:
    with pytest.raises(RuntimeError, match="bucket pivot-docs is missing"):
        _open_minio_store(_worker_minio_settings(_FakeMinioClient(exists=False)))


def test_D8_05_worker_unreachable_minio_keeps_unreachable_message() -> None:
    with pytest.raises(RuntimeError, match="minio is not reachable"):
        _open_minio_store(_worker_minio_settings(_FakeMinioClient(exists=None)))


def test_D8_05_worker_missing_collection_names_the_collection() -> None:
    with pytest.raises(RuntimeError, match="collection pivot is missing"):
        _open_qdrant_store(_worker_qdrant_settings(_FakeQdrantClient(exists=False)))


def test_D8_05_worker_unreachable_qdrant_keeps_unreachable_message() -> None:
    with pytest.raises(RuntimeError, match="qdrant is not reachable"):
        _open_qdrant_store(_worker_qdrant_settings(_FakeQdrantClient(exists=None)))


def test_D8_05_api_missing_bucket_and_collection_name_the_resource() -> None:
    pytest.importorskip("fastapi")
    from pivot.http.bootstrap import _open_minio_store as api_open_minio
    from pivot.http.bootstrap import _open_qdrant_store as api_open_qdrant

    api_minio = SimpleNamespace(
        minio_endpoint="minio:9000",
        minio_bucket="pivot-docs",
        object_store_client=_FakeMinioClient(exists=False),
        minio_access_key="pivotminio",
        minio_secret_key="pivot_dev_only",
        minio_secure=False,
        minio_ensure_bucket=False,
    )
    with pytest.raises(RuntimeError, match="bucket pivot-docs is missing"):
        api_open_minio(api_minio)
    api_qdrant = SimpleNamespace(
        qdrant_endpoint="qdrant:6333",
        qdrant_collection="pivot",
        vector_store_client=_FakeQdrantClient(exists=False),
        qdrant_api_key=None,
        qdrant_ensure_collection=False,
        qdrant_vector_size=4,
        qdrant_distance="Cosine",
    )
    with pytest.raises(RuntimeError, match="collection pivot is missing"):
        api_open_qdrant(api_qdrant)


def test_D8_18_worker_llama_sync_falls_back_to_cosine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pivot.retrieval.llama_qdrant_index import LlamaLibraryIndexSet

    captured: dict[str, object] = {}

    @classmethod
    def _fake_open(cls, **kwargs: object) -> object:  # noqa: ARG001
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(LlamaLibraryIndexSet, "open", _fake_open)
    settings = SimpleNamespace(
        llama_qdrant_client=object(),
        qdrant_endpoint="qdrant:6333",
        qdrant_api_key=None,
        qdrant_distance=None,
        qdrant_collection="pivot",
        qdrant_vector_size=4,
        embedding_model="hash-embedding",
    )
    _llama_document_sync(
        settings,
        store=_FakeStore(),
        document_rows={},
        version_rows={},
        embedding=HashingQueryEmbedder(dimension=4),
    )
    assert captured["distance"] == "Cosine"
