"""Ingest and retrieval share injected HTTP Embedding. Not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from harness import POLICY_TEXT, policy_pdf
from pivot.db.models import Base, User
from pivot.db.session import create_db_engine, session_factory
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.retrieval.fakes import HashingQueryEmbedder, ScriptedJsonHttpClient
from pivot.retrieval.providers import HttpQueryEmbedder
from pivot.storage.adapters.qdrant import QdrantVectorStore
from pivot_worker.assembly import IngestAssemblySettings, assemble_ingest_runtime
from pivot_worker.index import IndexPublisher

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "ingest-http-embedding.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_ASSEMBLY_SRC = _ROOT / "worker" / "src" / "pivot_worker" / "assembly.py"
_BOOTSTRAP = _ROOT / "api" / "src" / "pivot" / "http" / "bootstrap.py"


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


def _http_vectors(payload: dict, dimension: int = 4) -> dict:
    data = []
    for index, text in enumerate(payload.get("input") or ()):
        seed = float((len(text) + sum(ord(ch) for ch in text[:8])) % 97 or 1)
        data.append(
            {
                "index": index,
                "embedding": [seed / (offset + 1) for offset in range(dimension)],
            }
        )
    return {"data": data}


def _http_client() -> ScriptedJsonHttpClient:
    def _handler(url, payload, headers, timeout):
        del url, headers, timeout
        return _http_vectors(payload)

    return ScriptedJsonHttpClient(handler=_handler)


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
        "vector_store": "qdrant",
        "qdrant_endpoint": "vectors.test:443",
        "qdrant_collection": "pivot-chunks",
        "qdrant_ensure_collection": True,
        "qdrant_vector_size": 4,
        "qdrant_distance": "Cosine",
        "vector_store_client": _StoringQdrantClient(),
        "embedding": "http",
        "embedding_endpoint": "https://embed.test/v1/embeddings",
        "embedding_model": "injected-embed-model",
        "embedding_api_key": "secret-embed-key",
        "json_http_client": _http_client(),
    }
    values.update(overrides)
    return RuntimeSettings(**values)


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
        "embedding": "http",
        "embedding_endpoint": "https://embed.test/v1/embeddings",
        "embedding_model": "injected-embed-model",
        "embedding_api_key": "secret-embed-key",
        "json_http_client": _http_client(),
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


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_http_embed_login"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_NFR_OBS_runtime_http_embedding_shared_with_ingest():
    assembly = assemble_runtime(_runtime_settings())
    assert isinstance(assembly.query_embedder, HttpQueryEmbedder)
    assert assembly.ingest_embedding is assembly.query_embedder
    assert not isinstance(assembly.query_embedder, HashingQueryEmbedder)
    assert isinstance(assembly.vectors, QdrantVectorStore)
    assert isinstance(assembly.index, IndexPublisher)


def test_FR_DOC_006_runtime_http_embedding_ingest_search_roundtrip():
    transport = _http_client()
    assembly = assemble_runtime(_runtime_settings(json_http_client=transport))
    client = TestClient(assembly.app, base_url="https://testserver")
    token = _login(client)
    uploaded = client.post(
        "/api/v1/documents",
        data={"title": "Attendance Policy", "space": "hr"},
        files={"file": ("policy.pdf", policy_pdf(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_http_embed_up"},
    )
    assert uploaded.status_code == 201
    document_id = uploaded.json()["document_id"]
    response = client.get(
        "/api/v1/search",
        params={"q": POLICY_TEXT},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_http_embed_search"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert body["items"][0]["document_id"] == document_id
    assert body["items"][0]["title"] == "Attendance Policy"
    dumped = str(body).lower() + str(response.headers).lower()
    assert "embed.test" not in dumped
    assert "secret-embed-key" not in dumped
    assert len(transport.calls) >= 2
    assert all(item["url"] == "https://embed.test/v1/embeddings" for item in transport.calls)
    assert all(item["payload"]["model"] == "injected-embed-model" for item in transport.calls)
    assert any(item["payload"]["input"] == [POLICY_TEXT] for item in transport.calls)


def test_FR_DOC_006_worker_http_embedding_wires_http_embedder(tmp_path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'pivot.db').as_posix()}"
    transport = _http_client()
    worker = assemble_ingest_runtime(
        _worker_settings(
            url, _FakeMinioClient(), _StoringQdrantClient(), json_http_client=transport
        )
    )
    assert isinstance(worker.embedding, HttpQueryEmbedder)
    assert not isinstance(worker.embedding, HashingQueryEmbedder)
    probe = worker.embedding.embed(["迟到书面警告"])
    assert len(probe[0]) == 4
    assert transport.calls[0]["url"] == "https://embed.test/v1/embeddings"
    assert transport.calls[0]["payload"]["model"] == "injected-embed-model"


def test_FR_DOC_006_worker_http_embedding_search_roundtrip(tmp_path):
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
        request_id="req_worker_http_up",
        space="hr",
    )
    result = worker.runner(version.id, "req_worker_http_ingest", "usr_admin")
    assert result is not None
    assert result["status"] == "ok"

    assembly = assemble_runtime(_runtime_settings(vector_store_client=shared_qdrant))
    client = TestClient(assembly.app, base_url="https://testserver")
    token = _login(client)
    response = client.get(
        "/api/v1/search",
        params={"q": POLICY_TEXT},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": "req_worker_http_search",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    hit = body["items"][0]
    assert hit["document_id"] == version.document_id
    assert hit["title"] == "Attendance Policy"
    dumped = str(body).lower() + str(response.headers).lower()
    assert "embed.test" not in dumped
    assert "secret-embed-key" not in dumped
    assert "vectors.test" not in dumped


def test_GATE_P0_002_not_verified_by_ingest_http_embedding():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assembly = _ASSEMBLY_SRC.read_text(encoding="utf-8")
    bootstrap = _BOOTSTRAP.read_text(encoding="utf-8")
    assert "GATE-P0-002" in evidence
    assert "unverified" in evidence.lower()
    assert "fake" in evidence.lower()
    assert "siliconflow" not in assembly.lower()
    assert "siliconflow" not in bootstrap.lower()
    assert "bge-m3" not in assembly.lower()
    assert "bge-m3" not in bootstrap.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-002" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
