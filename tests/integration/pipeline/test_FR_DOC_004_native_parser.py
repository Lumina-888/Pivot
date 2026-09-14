"""Native parse extra wiring. Not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pivot.db.documents import SqlAlchemyVersionStore
from pivot.db.models import Base, User
from pivot.db.session import create_db_engine, session_factory
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.parsing.native import (
    OpenpyxlParser,
    PyMuPdfParser,
    PythonDocxParser,
    PythonPptxParser,
)
from pivot_worker.assembly import IngestAssemblySettings, assemble_ingest_runtime

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "native-parsers.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_ASSEMBLY_SRC = _ROOT / "worker" / "src" / "pivot_worker" / "assembly.py"
_BOOTSTRAP = _ROOT / "api" / "src" / "pivot" / "http" / "bootstrap.py"
_NATIVE_SRC = _ROOT / "api" / "src" / "pivot" / "parsing" / "native.py"
_DOCKERFILE = _ROOT / "Dockerfile"
_WORKER_DOCKERFILE = _ROOT / "Dockerfile.worker"
_WORKFLOW = _ROOT / ".github" / "workflows" / "ci.yml"
_POLICY_TEXT = "Late arrival policy"


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


def _native_pdf(text: str = _POLICY_TEXT) -> bytes:
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    payload = doc.tobytes()
    doc.close()
    return payload


def _runtime_settings(**overrides: object) -> RuntimeSettings:
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
        "parser": "native",
    }
    values.update(overrides)
    return RuntimeSettings(**values)


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_native_login"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_NFR_OBS_runtime_native_wires_parser():
    assembly = assemble_runtime(_runtime_settings())
    assert assembly.parsers is not None
    assert isinstance(assembly.parsers._parsers["pdf"], PyMuPdfParser)
    assert isinstance(assembly.parsers._parsers["docx"], PythonDocxParser)
    assert isinstance(assembly.parsers._parsers["pptx"], PythonPptxParser)
    assert isinstance(assembly.parsers._parsers["xlsx"], OpenpyxlParser)


def test_FR_DOC_004_runtime_native_ingest_uses_libraries():
    assembly = assemble_runtime(_runtime_settings())
    client = TestClient(assembly.app, base_url="https://testserver")
    token = _login(client)
    uploaded = client.post(
        "/api/v1/documents",
        data={"title": "Attendance Policy", "space": "hr"},
        files={"file": ("policy.pdf", _native_pdf(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_native_up"},
    )
    assert uploaded.status_code == 201
    detail = client.get(
        f"/api/v1/documents/{uploaded.json()['document_id']}",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_native_detail"},
    )
    assert detail.status_code == 200
    version = detail.json()["versions"][0]
    assert version["state"] == "ready"
    assert version["current"] is True


def test_FR_DOC_004_worker_native_ingest_uses_libraries(tmp_path):
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
    content = _native_pdf()
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
            object_store_client=_FakeMinioClient(),
            parser="native",
        )
    )
    version = worker.documents.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=content,
        title="Attendance Policy",
        actor_id="usr_admin",
        request_id="req_worker_native_up",
        space="hr",
    )
    result = worker.runner(version.id, "req_worker_native_ingest", "usr_admin")
    assert result is not None
    assert result["status"] == "ok"
    ready = SqlAlchemyVersionStore(session_factory(engine)).get(version.id)
    assert ready is not None
    assert ready.state == "ready"


def test_NFR_OBS_api_dockerfile_installs_parse_extra():
    text = _DOCKERFILE.read_text(encoding="utf-8")
    assert "worker[celery,parse]" in text


def test_NFR_OBS_worker_dockerfile_installs_parse_extra():
    text = _WORKER_DOCKERFILE.read_text(encoding="utf-8")
    assert "worker[celery,parse]" in text


def test_NFR_OBS_ci_installs_parse_extra():
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "worker[celery,parse]" in text


def test_GATE_P0_003_not_verified_by_native_parser():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assembly = _ASSEMBLY_SRC.read_text(encoding="utf-8")
    bootstrap = _BOOTSTRAP.read_text(encoding="utf-8")
    native = _NATIVE_SRC.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "heuristic" in evidence.lower() or "stdlib" in evidence.lower()
    for text in (assembly, bootstrap, native, evidence):
        lowered = text.lower()
        assert "max_pages" not in lowered
        assert "page_limit" not in lowered
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
