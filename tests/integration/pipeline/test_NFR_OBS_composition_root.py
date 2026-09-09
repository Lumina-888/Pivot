"""Runtime composition root. Not GATE-P0 verified. Default create_app() stays bare."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pivot.http import (
    RuntimeSettings,
    assemble_runtime,
    assemble_runtime_app,
    create_app,
)
from pivot.storage.adapters.minio import MinioObjectStore
from pivot.storage.adapters.qdrant import QdrantVectorStore
from pivot.storage.adapters.redis import RedisCacheStore, RedisQueueStore

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "composition-root.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"


def _settings(**overrides: object) -> RuntimeSettings:
    values: dict[str, object] = {
        "storage": "memory",
        "token_secret": "runtime-test-secret",
        "access_ttl": 60,
        "refresh_ttl": 3600,
        "export_ttl": 3600,
        "download_ttl": 300,
        "export_public_base": "https://files.pivot.test",
        "bootstrap_username": "admin",
        "bootstrap_password": "runtime-admin-password",
        "retrieval_k": 4,
        "argon2_time_cost": 1,
        "argon2_memory_cost": 8,
        "argon2_parallelism": 1,
    }
    values.update(overrides)
    return RuntimeSettings(**values)


def _client(settings: RuntimeSettings | None = None) -> TestClient:
    return TestClient(
        assemble_runtime_app(_settings() if settings is None else settings),
        base_url="https://testserver",
    )


def test_NFR_OBS_001_runtime_app_is_alive_without_injected_services():
    client = _client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "nope"},
        headers={"X-Request-ID": "req_runtime_missing"},
    )
    documents = client.get(
        "/api/v1/documents", headers={"X-Request-ID": "req_runtime_docs_anon"}
    )
    search = client.get(
        "/api/v1/search",
        params={"q": "policy"},
        headers={"X-Request-ID": "req_runtime_search_anon"},
    )
    conversations = client.get(
        "/api/v1/conversations", headers={"X-Request-ID": "req_runtime_conv_anon"}
    )
    assert login.status_code == 401
    assert documents.status_code == 401
    assert search.status_code == 401
    assert conversations.status_code == 401


def test_NFR_OBS_002_runtime_readyz_fail_closed_without_infra_probes():
    response = _client().get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"] == {
        "postgres": False,
        "minio": False,
        "qdrant": False,
        "redis": False,
    }


def test_NFR_SEC_004_runtime_bootstrap_password_is_argon2id():
    assembly = assemble_runtime(_settings())
    user = assembly.users.get_by_username("admin")
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert "runtime-admin-password" not in user.password_hash
    assert assembly.hasher.verify("runtime-admin-password", user.password_hash)
    assert not assembly.hasher.verify("wrong-password", user.password_hash)


def test_FR_AUTH_001_runtime_login_without_test_harness():
    client = _client()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_runtime_login"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["refresh_token_cookie"] is True
    assert "refresh_token" not in body
    assert body["access_token"]
    assert "runtime-admin-password" not in body["access_token"]
    token = body["access_token"]
    listed = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_runtime_docs"},
    )
    assert listed.status_code == 200
    assert listed.json()["items"] == []


def test_NFR_OBS_runtime_rejects_unwired_storage():
    with pytest.raises(RuntimeError, match="unsupported PIVOT_STORAGE"):
        assemble_runtime_app(_settings(storage="minio"))


def test_NFR_OBS_runtime_postgres_requires_database_url():
    with pytest.raises(RuntimeError, match="PIVOT_DATABASE_URL"):
        assemble_runtime_app(_settings(storage="postgres"))


def test_NFR_OBS_runtime_postgres_wires_sqlalchemy_user_directory(tmp_path):
    from pivot.db.users import SqlAlchemyUserDirectory

    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    assembly = assemble_runtime(
        _settings(storage="postgres", database_url=url, create_schema=True)
    )
    assert isinstance(assembly.users, SqlAlchemyUserDirectory)
    user = assembly.users.get_by_username("admin")
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")


def test_FR_AUTH_001_runtime_postgres_login_survives_new_assembly(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    first = _client(_settings(storage="postgres", database_url=url, create_schema=True))
    created = first.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_pg_login_1"},
    )
    assert created.status_code == 200
    second = _client(_settings(storage="postgres", database_url=url, create_schema=True))
    replayed = second.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_pg_login_2"},
    )
    assert replayed.status_code == 200
    assert replayed.json()["token_type"] == "Bearer"
    listed = second.get(
        "/api/v1/documents",
        headers={
            "Authorization": f"Bearer {replayed.json()['access_token']}",
            "X-Request-ID": "req_pg_docs",
        },
    )
    assert listed.status_code == 200


def test_NFR_OBS_runtime_postgres_readyz_not_fully_ready(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    response = _client(
        _settings(storage="postgres", database_url=url, create_schema=True)
    ).get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["postgres"] is True
    assert body["checks"]["minio"] is False
    assert body["checks"]["qdrant"] is False
    assert body["checks"]["redis"] is False


class _FakeMinioClient:
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
        return SimpleNamespace(
            read=lambda *args: payload, close=lambda: None, release_conn=lambda: None
        )

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


def _minio_settings(client: _FakeMinioClient) -> RuntimeSettings:
    return _settings(
        object_store="minio",
        minio_endpoint="objects.test:443",
        minio_bucket="pivot-docs",
        minio_access_key="pivotminio",
        minio_secret_key="pivot_dev_only",
        minio_ensure_bucket=True,
        object_store_client=client,
    )


def test_NFR_OBS_runtime_minio_requires_endpoint():
    with pytest.raises(RuntimeError, match="PIVOT_MINIO_ENDPOINT"):
        assemble_runtime_app(_settings(object_store="minio"))


def test_NFR_OBS_runtime_minio_wires_object_store():
    assembly = assemble_runtime(_minio_settings(_FakeMinioClient()))
    assert assembly.object_store == "minio"
    assert assembly.storage == "memory"
    assert isinstance(assembly.objects, MinioObjectStore)


def test_FR_DOC_007_runtime_minio_preview_does_not_leak_endpoint():
    client = _client(_minio_settings(_FakeMinioClient()))
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_minio_login"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    pdf = b"%PDF-1.4\n(policy) Tj\n%%EOF\n"
    uploaded = client.post(
        "/api/v1/documents",
        data={"title": "policy", "space": "shared"},
        files={"file": ("policy.pdf", pdf, "application/pdf")},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_minio_up",
        },
    )
    assert uploaded.status_code == 201
    body = uploaded.json()
    assert "storage_key" not in body
    document_id = body["document_id"]
    preview = client.get(
        f"/api/v1/documents/{document_id}/preview",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_minio_preview",
        },
    )
    assert preview.status_code == 200
    assert preview.content.startswith(b"%PDF")
    dumped = str(preview.headers).lower() + preview.content.decode("latin-1", errors="ignore")
    assert "objects.test" not in dumped
    assert "minio" not in dumped
    assert "pivotminio" not in dumped
    assert "pivot_dev_only" not in dumped
    assert ":9000" not in dumped


def test_NFR_OBS_runtime_minio_readyz_not_fully_ready():
    response = _client(_minio_settings(_FakeMinioClient())).get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["minio"] is True
    assert body["checks"]["postgres"] is False
    assert body["checks"]["qdrant"] is False
    assert body["checks"]["redis"] is False


class _FakeQdrantClient:
    def __init__(self) -> None:
        self.collections: set[str] = set()

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(self, collection_name: str, *, vector_size: int, distance: str) -> None:
        self.collections.add(collection_name)

    def upsert(self, collection_name: str, points) -> None:
        return None

    def search(self, collection_name, query_vector, limit=10, query_filter=None):
        return []

    def delete(self, collection_name, points_selector=None) -> None:
        return None


def _qdrant_settings(client: _FakeQdrantClient) -> RuntimeSettings:
    return _settings(
        vector_store="qdrant",
        qdrant_endpoint="vectors.test:443",
        qdrant_collection="pivot-chunks",
        qdrant_ensure_collection=True,
        qdrant_vector_size=4,
        qdrant_distance="Cosine",
        vector_store_client=client,
    )


def test_NFR_OBS_runtime_qdrant_requires_endpoint():
    with pytest.raises(RuntimeError, match="PIVOT_QDRANT_ENDPOINT"):
        assemble_runtime_app(_settings(vector_store="qdrant"))


def test_NFR_OBS_runtime_qdrant_wires_vector_store():
    assembly = assemble_runtime(_qdrant_settings(_FakeQdrantClient()))
    assert assembly.vector_store == "qdrant"
    assert assembly.storage == "memory"
    assert assembly.object_store == "memory"
    assert isinstance(assembly.vectors, QdrantVectorStore)


def test_NFR_OBS_runtime_qdrant_readyz_not_fully_ready():
    response = _client(_qdrant_settings(_FakeQdrantClient())).get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["qdrant"] is True
    assert body["checks"]["postgres"] is False
    assert body["checks"]["minio"] is False
    assert body["checks"]["redis"] is False


def test_NFR_OBS_runtime_rejects_unwired_vector_store():
    with pytest.raises(RuntimeError, match="unsupported PIVOT_VECTOR_STORE"):
        assemble_runtime_app(_settings(vector_store="redis"))


class _FakeRedisClient:
    def ping(self) -> bool:
        return True

    def get(self, name: str):
        return None

    def set(self, name: str, value, ex=None):
        return True

    def delete(self, *names: str) -> int:
        return 0

    def rpush(self, name: str, *values) -> int:
        return 0

    def lpop(self, name: str):
        return None


def _redis_settings(client: _FakeRedisClient) -> RuntimeSettings:
    return _settings(
        cache_store="redis",
        queue_store="redis",
        redis_endpoint="cache.test:6380",
        redis_client=client,
    )


def test_NFR_OBS_runtime_redis_requires_endpoint():
    with pytest.raises(RuntimeError, match="PIVOT_REDIS_ENDPOINT"):
        assemble_runtime_app(_settings(cache_store="redis"))


def test_NFR_OBS_runtime_redis_wires_cache_and_queue():
    assembly = assemble_runtime(_redis_settings(_FakeRedisClient()))
    assert assembly.cache_store == "redis"
    assert assembly.queue_store == "redis"
    assert isinstance(assembly.cache, RedisCacheStore)
    assert isinstance(assembly.queue, RedisQueueStore)


def test_NFR_OBS_runtime_redis_readyz_not_fully_ready():
    response = _client(_redis_settings(_FakeRedisClient())).get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["redis"] is True
    assert body["checks"]["postgres"] is False
    assert body["checks"]["minio"] is False
    assert body["checks"]["qdrant"] is False


def test_NFR_OBS_runtime_rejects_unwired_cache_store():
    with pytest.raises(RuntimeError, match="unsupported PIVOT_CACHE_STORE"):
        assemble_runtime_app(_settings(cache_store="minio"))


def test_NFR_OBS_runtime_settings_fail_closed_without_token_secret():
    with pytest.raises(RuntimeError, match="PIVOT_TOKEN_SECRET"):
        RuntimeSettings.from_env(
            {
                "PIVOT_STORAGE": "memory",
                "PIVOT_ACCESS_TTL": "60",
                "PIVOT_REFRESH_TTL": "3600",
                "PIVOT_EXPORT_TTL": "3600",
                "PIVOT_DOWNLOAD_TTL": "300",
                "PIVOT_EXPORT_PUBLIC_BASE": "https://files.pivot.test",
                "PIVOT_RETRIEVAL_K": "4",
            }
        )


def test_NFR_OBS_runtime_factory_reads_settings_from_env(monkeypatch):
    from pivot.http.main import app as runtime_factory

    monkeypatch.setenv("PIVOT_TOKEN_SECRET", "runtime-factory-secret")
    monkeypatch.setenv("PIVOT_ACCESS_TTL", "60")
    monkeypatch.setenv("PIVOT_REFRESH_TTL", "3600")
    monkeypatch.setenv("PIVOT_EXPORT_TTL", "3600")
    monkeypatch.setenv("PIVOT_DOWNLOAD_TTL", "300")
    monkeypatch.setenv("PIVOT_EXPORT_PUBLIC_BASE", "https://files.pivot.test")
    monkeypatch.setenv("PIVOT_RETRIEVAL_K", "4")
    monkeypatch.setenv("PIVOT_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("PIVOT_BOOTSTRAP_PASSWORD", "runtime-admin-password")
    client = TestClient(runtime_factory(), base_url="https://testserver")
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_NFR_OBS_default_create_app_does_not_mount_api_v1():
    app = create_app()
    paths = [getattr(route, "path", "") for route in app.routes]
    assert not any(path.startswith("/api/v1") for path in paths)


def test_GATE_P0_008_not_verified_by_runtime_assembly():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-008" in evidence
    assert "unverified" in evidence.lower()
    assert "composition root" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-008" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
