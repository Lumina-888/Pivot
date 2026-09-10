"""Worker ingest publishes to the same Qdrant port API retrieval consumes.

Not GATE-P0 verified. CI uses a Fake Qdrant client.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from harness import POLICY_TEXT, policy_pdf
from pivot.db.models import Base, User
from pivot.db.session import create_db_engine, session_factory
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.retrieval.fakes import HashingQueryEmbedder
from pivot.storage.adapters.qdrant import QdrantVectorStore
from pivot_worker.assembly import IngestAssemblySettings, assemble_ingest_runtime
from pivot_worker.index import IndexPublisher
from pivot_worker.runtime import DocumentIngestRunner

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "worker-qdrant.md"
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


class _StoringQdrantClient:
    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.points: dict[str, dict[str, tuple[list[float], dict]]] = {}

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(self, collection_name: str, *, vector_size: int, distance: str) -> None:
        self.collections.add(collection_name)
        self.points.setdefault(collection_name, {})

    def upsert(self, collection_name: str, points) -> None:
        bucket = self.points.setdefault(collection_name, {})
        for point in points:
            bucket[str(point["id"])] = (list(point["vector"]), dict(point["payload"]))

    def search(self, collection_name, query_vector, limit=10, query_filter=None):
        query = list(query_vector)
        hits = []
        for pid, (vector, payload) in self.points.get(collection_name, {}).items():
            if not _payload_matches(payload, query_filter):
                continue
            hits.append(SimpleNamespace(id=pid, score=_dot(query, vector), payload=payload))
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def delete(self, collection_name, points_selector=None) -> None:
        return None


def _payload_matches(payload: dict, selector: dict | None) -> bool:
    if not selector:
        return True
    for condition in selector.get("must", ()):
        if payload.get(condition["key"]) != condition["match"]["value"]:
            return False
    return True


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


def _worker_settings(
    url: str,
    minio: _FakeMinioClient,
    qdrant: _StoringQdrantClient,
    **overrides: object,
) -> IngestAssemblySettings:
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
        "object_store_client": minio,
        "vector_store": "qdrant",
        "qdrant_endpoint": "vectors.test:443",
        "qdrant_collection": "pivot-chunks",
        "qdrant_ensure_collection": True,
        "qdrant_vector_size": 4,
        "qdrant_distance": "Cosine",
        "vector_store_client": qdrant,
    }
    values.update(overrides)
    return IngestAssemblySettings(**values)


def _http_settings(qdrant: _StoringQdrantClient) -> RuntimeSettings:
    return RuntimeSettings(
        storage="memory",
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
        vector_store="qdrant",
        qdrant_endpoint="vectors.test:443",
        qdrant_collection="pivot-chunks",
        qdrant_ensure_collection=True,
        qdrant_vector_size=4,
        qdrant_distance="Cosine",
        vector_store_client=qdrant,
    )


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


def test_FR_DOC_006_worker_qdrant_publish_wires_index_publisher(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    worker = assemble_ingest_runtime(
        _worker_settings(url, _FakeMinioClient(), _StoringQdrantClient())
    )
    assert worker.vector_store == "qdrant"
    assert isinstance(worker.runner, DocumentIngestRunner)
    assert isinstance(worker.vectors, QdrantVectorStore)
    assert isinstance(worker.index, IndexPublisher)
    assert isinstance(worker.embedding, HashingQueryEmbedder)
    assert worker.embedding.dimension == 4


def test_FR_DOC_006_worker_qdrant_publish_search_roundtrip(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    _seed_user(url)
    shared_minio = _FakeMinioClient()
    shared_qdrant = _StoringQdrantClient()
    worker = assemble_ingest_runtime(
        _worker_settings(url, shared_minio, shared_qdrant, create_schema=False)
    )
    version = worker.documents.upload(
        filename="policy.pdf",
        declared_mime="application/pdf",
        content=policy_pdf(),
        title="Attendance Policy",
        actor_id="usr_admin",
        request_id="req_worker_qdrant_up",
        space="hr",
    )
    result = worker.runner(version.id, "req_worker_qdrant_ingest", "usr_admin")
    assert result is not None
    assert result["status"] == "ok"

    assembly = assemble_runtime(_http_settings(shared_qdrant))
    client = TestClient(assembly.app, base_url="https://testserver")
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_worker_qdrant_login"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    response = client.get(
        "/api/v1/search",
        params={"q": POLICY_TEXT},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_worker_qdrant_search",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    hit = body["items"][0]
    assert hit["document_id"] == version.document_id
    assert hit["title"] == "Attendance Policy"
    dumped = str(body).lower() + str(response.headers).lower()
    assert "vectors.test" not in dumped
    assert "qdrant" not in dumped


def test_GATE_P0_002_not_verified_by_worker_qdrant():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-002" in evidence
    assert "unverified" in evidence.lower()
    assert "fake" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-002" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
