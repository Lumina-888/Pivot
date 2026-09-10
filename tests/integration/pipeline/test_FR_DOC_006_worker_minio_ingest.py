"""Worker ingest reads shared MinIO + PG facts. Not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from harness import policy_pdf
from pivot.db.documents import (
    SqlAlchemyChunkStore,
    SqlAlchemyDocumentStore,
    SqlAlchemyTaskStore,
    SqlAlchemyVersionStore,
)
from pivot.db.models import Base, User
from pivot.db.session import create_db_engine, session_factory
from pivot.documents.errors import DocumentError
from pivot.documents.service import DocumentService
from pivot.http.memory import MemoryDocumentAudits, MemoryDocumentObjects
from pivot.storage.adapters.minio import MinioObjectStore
from pivot_worker.assembly import IngestAssemblySettings, assemble_ingest_runtime
from pivot_worker.runtime import DocumentIngestRunner

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "worker-minio-ingest.md"
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


def _settings(url: str, client: _FakeMinioClient, **overrides: object) -> IngestAssemblySettings:
    values: dict[str, object] = {
        "storage": "postgres",
        "database_url": url,
        "create_schema": True,
        "object_store": "minio",
        "minio_endpoint": "objects.test:443",
        "minio_bucket": "pivot-docs",
        "minio_access_key": "pivotminio",
        "minio_secret_key": "pivot_dev_only",
        "minio_ensure_bucket": True,
        "object_store_client": client,
    }
    values.update(overrides)
    return IngestAssemblySettings(**values)


def _seed_user(url: str) -> None:
    engine = create_db_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = session_factory(engine)
    with sessions() as session:
        if session.get(User, "usr_admin") is None:
            session.add(
                User(
                    id="usr_admin",
                    username="admin",
                    password_hash="hash",
                    role="admin",
                    status="active",
                )
            )
            session.commit()


def test_FR_DOC_006_worker_ingest_reads_shared_minio_object(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    _seed_user(url)
    shared = _FakeMinioClient()
    uploader = assemble_ingest_runtime(_settings(url, shared, create_schema=False))
    version = uploader.documents.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=policy_pdf(),
        title="Attendance Policy",
        actor_id="usr_admin",
        request_id="req_shared_up",
        space="hr",
    )
    assert version.state == "uploaded"
    worker = assemble_ingest_runtime(_settings(url, shared, create_schema=False))
    assert isinstance(worker.runner, DocumentIngestRunner)
    assert isinstance(worker.objects, MinioObjectStore)
    result = worker.runner(version.id, "req_shared_ingest", "usr_admin")
    assert result is not None
    assert result["status"] == "ok"
    engine = create_db_engine(url, connect_args={"check_same_thread": False})
    ready = SqlAlchemyVersionStore(session_factory(engine)).get(version.id)
    assert ready is not None
    assert ready.state == "ready"
    assert ready.current is True


def test_FR_DOC_006_worker_ingest_does_not_see_memory_objects(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    _seed_user(url)
    engine = create_db_engine(url, connect_args={"check_same_thread": False})
    sessions = session_factory(engine)
    memory_uploader = DocumentService(
        documents=SqlAlchemyDocumentStore(sessions),
        versions=SqlAlchemyVersionStore(sessions),
        chunks=SqlAlchemyChunkStore(sessions),
        tasks=SqlAlchemyTaskStore(sessions),
        objects=MemoryDocumentObjects(),
        audits=MemoryDocumentAudits(),
    )
    version = memory_uploader.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=policy_pdf(),
        title="Attendance Policy",
        actor_id="usr_admin",
        request_id="req_mem_up",
        space="hr",
    )
    worker = assemble_ingest_runtime(_settings(url, _FakeMinioClient(), create_schema=False))
    with pytest.raises(DocumentError, match="资源不存在"):
        worker.runner(version.id, "req_mem_ingest", "usr_admin")
    pending = SqlAlchemyVersionStore(session_factory(engine)).get(version.id)
    assert pending is not None
    assert pending.state != "ready"


def test_GATE_P0_003_not_verified_by_worker_minio_ingest():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "minio" in evidence.lower()
    assert "sqlite" in evidence.lower() or "fake" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
