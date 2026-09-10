"""HTTP composition root and worker share MinIO bytes. Not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from harness import policy_pdf
from pivot.db.documents import SqlAlchemyVersionStore
from pivot.db.session import create_db_engine, session_factory
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.storage.adapters.minio import MinioObjectStore
from pivot_worker.assembly import IngestAssemblySettings, assemble_ingest_runtime

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "compose-api-shared-storage.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"


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


def _http_settings(url: str, client: _FakeMinioClient) -> RuntimeSettings:
    return RuntimeSettings(
        storage="postgres",
        database_url=url,
        create_schema=True,
        object_store="minio",
        minio_endpoint="objects.test:443",
        minio_bucket="pivot-docs",
        minio_access_key="pivotminio",
        minio_secret_key="pivot_dev_only",
        minio_ensure_bucket=True,
        object_store_client=client,
        token_secret="runtime-test-secret",
        access_ttl=60,
        refresh_ttl=3600,
        export_ttl=3600,
        download_ttl=300,
        export_public_base="https://files.pivot.test",
        bootstrap_username="admin",
        bootstrap_password="runtime-admin-password",
        retrieval_k=4,
        argon2_time_cost=1,
        argon2_memory_cost=8,
        argon2_parallelism=1,
    )


def test_FR_DOC_001_http_and_worker_share_minio_object(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    shared = _FakeMinioClient()
    assembly = assemble_runtime(_http_settings(url, shared))
    client = TestClient(assembly.app, base_url="https://testserver")
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_share_login"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    pdf = policy_pdf()
    uploaded = client.post(
        "/api/v1/documents",
        data={"title": "Attendance Policy", "space": "hr"},
        files={"file": ("handbook.pdf", pdf, "application/pdf")},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_share_up"},
    )
    assert uploaded.status_code == 201
    body = uploaded.json()
    assert body["state"] == "uploaded"
    version_id = body["version_id"]
    worker = assemble_ingest_runtime(
        IngestAssemblySettings(
            storage="postgres",
            database_url=url,
            create_schema=False,
            object_store="minio",
            minio_endpoint="objects.test:443",
            minio_bucket="pivot-docs",
            minio_access_key="pivotminio",
            minio_secret_key="pivot_dev_only",
            minio_ensure_bucket=True,
            object_store_client=shared,
        )
    )
    assert isinstance(worker.objects, MinioObjectStore)
    engine = create_db_engine(url, connect_args={"check_same_thread": False})
    version = SqlAlchemyVersionStore(session_factory(engine)).get(version_id)
    assert version is not None
    assert worker.objects.get(version.storage_key) == pdf
    skipped = worker.runner(version_id, "req_share_ingest", "usr_unused")
    assert skipped is None
    ready = SqlAlchemyVersionStore(session_factory(engine)).get(version_id)
    assert ready is not None
    assert ready.state == "ready"


def test_GATE_P0_008_not_verified_by_compose_api_shared_storage():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-008" in evidence
    assert "unverified" in evidence.lower()
    assert "minio" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-008" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
