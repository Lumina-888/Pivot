"""MinIO ObjectStore adapter. Default CI uses an injected client, not Compose."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pivot.storage.adapters.minio import MinioObjectStore
from pivot.storage.config import ObjectStoreConfig


class FakeMinioClient:
    def __init__(self) -> None:
        self.buckets: set[str] = set()
        self.objects: dict[tuple[str, str], tuple[bytes, str | None]] = {}

    def bucket_exists(self, bucket: str) -> bool:
        return bucket in self.buckets

    def make_bucket(self, bucket: str) -> None:
        self.buckets.add(bucket)

    def put_object(self, bucket, object_name, data, length, content_type=None):
        payload = data.read(length) if hasattr(data, "read") else data
        self.objects[(bucket, object_name)] = (payload, content_type)

    def get_object(self, bucket, object_name):
        payload, _ = self.objects[(bucket, object_name)]
        return _Body(payload)

    def remove_object(self, bucket, object_name):
        self.objects.pop((bucket, object_name), None)

    def stat_object(self, bucket, object_name):
        if (bucket, object_name) not in self.objects:
            raise KeyError(object_name)
        return SimpleNamespace(size=len(self.objects[(bucket, object_name)][0]))

    def list_objects(self, bucket, prefix="", recursive=True):
        for stored_bucket, key in self.objects:
            if stored_bucket == bucket and key.startswith(prefix):
                yield SimpleNamespace(object_name=key)

    def presigned_get_object(self, bucket, object_name, expires=None):
        return f"https://objects.test/{bucket}/{object_name}"


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, *args):
        return self._data

    def close(self) -> None:
        return None

    def release_conn(self) -> None:
        return None


def _store(client: FakeMinioClient | None = None) -> tuple[FakeMinioClient, MinioObjectStore]:
    fake = client or FakeMinioClient()
    return fake, MinioObjectStore(fake, bucket="pivot-docs", ensure_bucket=True)


def test_M03_minio_object_store_roundtrip_with_injected_client():
    fake, store = _store()
    store.put("quarantine/doc_a/ver_a", b"%PDF-1.4\n", content_type="application/pdf")
    assert store.exists("quarantine/doc_a/ver_a") is True
    assert store.get("quarantine/doc_a/ver_a") == b"%PDF-1.4\n"
    assert "quarantine/doc_a/ver_a" in store.keys()
    fake_payload, content_type = fake.objects[("pivot-docs", "quarantine/doc_a/ver_a")]
    assert fake_payload == b"%PDF-1.4\n"
    assert content_type == "application/pdf"
    store.delete("quarantine/doc_a/ver_a")
    assert store.exists("quarantine/doc_a/ver_a") is False
    assert store.get("quarantine/doc_a/ver_a") is None


def test_M03_minio_object_store_get_missing_returns_none():
    _, store = _store()
    assert store.get("missing/key") is None
    assert store.exists("missing/key") is False


def test_M03_minio_object_store_requires_injected_bucket():
    with pytest.raises(ValueError, match="bucket"):
        MinioObjectStore(FakeMinioClient(), bucket="")


def test_M03_minio_object_store_presign_is_not_a_public_download_api():
    _, store = _store()
    store.put("exports/exp_a/a.md", b"hello")
    url = store.presign("exports/exp_a/a.md", expires_seconds=60)
    assert "exports/exp_a/a.md" in url
    assert "127.0.0.1" not in url
    assert ":9000" not in url


def test_M03_minio_adapter_source_has_no_hardcoded_endpoint():
    root = Path(__file__).resolve().parents[3]
    source = (root / "api" / "src" / "pivot" / "storage" / "adapters" / "minio.py").read_text(
        encoding="utf-8"
    )
    assert "127.0.0.1" not in source
    assert "localhost" not in source
    assert ":9000" not in source
    config = ObjectStoreConfig(endpoint="objects.test:443", bucket="pivot-docs")
    assert config.endpoint == "objects.test:443"
