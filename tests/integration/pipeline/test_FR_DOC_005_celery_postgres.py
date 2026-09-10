"""Celery ingest can load PG version/task. Not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from harness import policy_pdf
from pivot.chunking import ChunkingPolicy, ChunkSplitter
from pivot.db.documents import (
    SqlAlchemyChunkStore,
    SqlAlchemyDocumentStore,
    SqlAlchemyTaskStore,
    SqlAlchemyVersionStore,
)
from pivot.db.models import Base, CeleryTask, User
from pivot.db.session import create_db_engine, session_factory
from pivot.documents.service import DocumentService
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.http.memory import MemoryDocumentAudits, MemoryDocumentObjects
from pivot.retrieval.fakes import HashingQueryEmbedder
from pivot_worker.celery_app import CeleryIngestSubmitter
from pivot_worker.index import IndexPublisher
from pivot_worker.runtime import DocumentIngestRunner
from sqlalchemy import select

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "celery-ingest.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"


class _MemoryStore:
    def __init__(self) -> None:
        self.points: list[dict] = []

    def upsert(self, points) -> None:
        self.points.extend(dict(point) for point in points)

    def search(self, vector, *, limit: int, filters=None):
        return []

    def delete(self, *, version_id=None, chunk_id=None) -> None:
        return None


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


def _celery_settings(**overrides: object) -> RuntimeSettings:
    return _settings(
        ingest_backend="celery",
        parse_queue="parse",
        online_queue="online",
        worker_concurrency=1,
        celery_broker="memory://",
        celery_always_eager=True,
        **overrides,
    )


def _login(client: TestClient, request_id: str = "req_celery_login") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": request_id},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _document_service(sessions, objects: MemoryDocumentObjects) -> DocumentService:
    return DocumentService(
        documents=SqlAlchemyDocumentStore(sessions),
        versions=SqlAlchemyVersionStore(sessions),
        chunks=SqlAlchemyChunkStore(sessions),
        tasks=SqlAlchemyTaskStore(sessions),
        objects=objects,
        audits=MemoryDocumentAudits(),
    )


def test_NFR_OBS_runtime_celery_requires_queues_and_broker():
    with pytest.raises(RuntimeError, match="PIVOT_PARSE_QUEUE|parse and online"):
        assemble_runtime(_settings(ingest_backend="celery"))
    with pytest.raises(RuntimeError, match="PIVOT_CELERY_BROKER"):
        assemble_runtime(
            _settings(
                ingest_backend="celery",
                parse_queue="parse",
                online_queue="online",
                worker_concurrency=1,
            )
        )


def test_NFR_OBS_runtime_celery_wires_eager_submitter():
    assembly = assemble_runtime(_celery_settings())
    assert assembly.ingest_backend == "celery"
    assert isinstance(assembly.ingest, CeleryIngestSubmitter)
    assert assembly.ingest.task_queue == "parse"
    default = assemble_runtime(_settings())
    assert default.ingest_backend == "sync"
    assert not isinstance(default.ingest, CeleryIngestSubmitter)


def test_FR_DOC_001_http_celery_envelope_stays_uploaded():
    assembly = assemble_runtime(_celery_settings())
    client = TestClient(assembly.app, base_url="https://testserver")
    token = _login(client)
    response = client.post(
        "/api/v1/documents",
        data={"title": "Attendance Policy", "space": "hr"},
        files={"file": ("handbook.pdf", policy_pdf(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_celery_up"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "uploaded"
    assert body["document_id"]
    assert body["version_id"]


def test_FR_DOC_001_http_celery_eager_detail_is_ready():
    assembly = assemble_runtime(_celery_settings())
    client = TestClient(assembly.app, base_url="https://testserver")
    token = _login(client)
    uploaded = client.post(
        "/api/v1/documents",
        data={"title": "Attendance Policy", "space": "hr"},
        files={"file": ("handbook.pdf", policy_pdf(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_celery_up2"},
    )
    assert uploaded.status_code == 201
    detail = client.get(
        f"/api/v1/documents/{uploaded.json()['document_id']}",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_celery_detail"},
    )
    assert detail.status_code == 200
    version = detail.json()["versions"][0]
    assert version["version_id"] == uploaded.json()["version_id"]
    assert version["state"] == "ready"
    assert version["current"] is True


def test_FR_DOC_005_celery_loads_postgres_version_and_task(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    engine = create_db_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = session_factory(engine)
    with sessions() as session:
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
    objects = MemoryDocumentObjects()
    uploader = _document_service(sessions, objects)
    version = uploader.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=policy_pdf(),
        title="Attendance Policy",
        actor_id="usr_admin",
        request_id="req_pg_up",
        space="hr",
    )
    seen = SqlAlchemyVersionStore(sessions).get(version.id)
    assert seen is not None
    assert seen.state == "uploaded"
    worker = _document_service(sessions, objects)
    submitter = CeleryIngestSubmitter(
        DocumentIngestRunner(
            worker,
            embedding=HashingQueryEmbedder(dimension=4),
            index=IndexPublisher(store=_MemoryStore()),
            dimension=4,
            splitter=ChunkSplitter(ChunkingPolicy(max_chars=80, overlap_chars=8)),
        ),
        parse_queue="parse",
        online_queue="online",
        concurrency=1,
        broker_url="memory://",
        always_eager=True,
    )
    result = submitter(version.id, "req_pg_ingest", "usr_admin")
    assert result is not None
    assert result["status"] == "ok"
    ready = SqlAlchemyVersionStore(sessions).get(version.id)
    assert ready is not None
    assert ready.state == "ready"
    assert ready.current is True
    with sessions() as session:
        tasks = list(
            session.scalars(select(CeleryTask).where(CeleryTask.entity_id == version.id))
        )
    assert tasks
    assert {row.entity_id for row in tasks} == {version.id}
    assert {row.entity_type for row in tasks} <= {"document_version", "chunk"}


def test_GATE_P0_003_not_verified_by_celery_ingest():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "celery" in evidence.lower()
    assert "eager" in evidence.lower() or "memory://" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
