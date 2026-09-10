"""HTTP upload runs in-process ingest. Not Celery and not GATE-P0 verified."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from harness import POLICY_TEXT, policy_pdf
from pivot.http import RuntimeSettings, assemble_runtime
from pivot.retrieval.models import RetrievalQuery
from pivot_worker.runtime import DocumentIngestRunner

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "http-upload-ingest.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"


class _StoringQdrantClient:
    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.points: dict[str, dict[str, tuple[list[float], dict]]] = {}
        self.upsert_calls = 0

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(self, collection_name: str, *, vector_size: int, distance: str) -> None:
        self.collections.add(collection_name)
        self.points.setdefault(collection_name, {})

    def upsert(self, collection_name: str, points) -> None:
        self.upsert_calls += 1
        bucket = self.points.setdefault(collection_name, {})
        for point in points:
            bucket[str(point["id"])] = (list(point["vector"]), dict(point["payload"]))

    def search(self, collection_name, query_vector, limit=10, query_filter=None):
        query = list(query_vector)
        hits = []
        for pid, (vector, payload) in self.points.get(collection_name, {}).items():
            score = sum(a * b for a, b in zip(query, vector, strict=False))
            hits.append(SimpleNamespace(id=pid, score=score, payload=payload))
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def delete(self, collection_name, points_selector=None) -> None:
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


def _qdrant_settings(client: _StoringQdrantClient | None = None) -> RuntimeSettings:
    return _settings(
        vector_store="qdrant",
        qdrant_endpoint="vectors.test:443",
        qdrant_collection="pivot-chunks",
        qdrant_ensure_collection=True,
        qdrant_vector_size=4,
        qdrant_distance="Cosine",
        vector_store_client=client or _StoringQdrantClient(),
    )


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "runtime-admin-password"},
        headers={"X-Request-ID": "req_ingest_login"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _upload(client: TestClient, token: str, title: str = "Attendance Policy", extra: bytes = b""):
    return client.post(
        "/api/v1/documents",
        data={"title": title, "space": "hr"},
        files={"file": (f"{title}.pdf", policy_pdf() + extra, "application/pdf")},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": f"req_up_{title}"},
    )


def test_NFR_OBS_runtime_wires_ingest_runner():
    assembly = assemble_runtime(_settings())
    assert isinstance(assembly.ingest, DocumentIngestRunner)


def test_FR_DOC_001_http_upload_envelope_stays_uploaded():
    assembly = assemble_runtime(_settings())
    client = TestClient(assembly.app, base_url="https://testserver")
    token = _login(client)
    response = _upload(client, token)
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "uploaded"
    assert body["document_id"]
    assert body["version_id"]


def test_FR_DOC_001_runtime_upload_detail_is_ready():
    assembly = assemble_runtime(_settings())
    client = TestClient(assembly.app, base_url="https://testserver")
    token = _login(client)
    uploaded = _upload(client, token)
    detail = client.get(
        f"/api/v1/documents/{uploaded.json()['document_id']}",
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_detail"},
    )
    assert detail.status_code == 200
    version = detail.json()["versions"][0]
    assert version["version_id"] == uploaded.json()["version_id"]
    assert version["state"] == "ready"
    assert version["current"] is True


def test_FR_DOC_006_runtime_upload_search_roundtrip():
    assembly = assemble_runtime(_qdrant_settings())
    client = TestClient(assembly.app, base_url="https://testserver")
    token = _login(client)
    uploaded = _upload(client, token)
    assert uploaded.status_code == 201
    document_id = uploaded.json()["document_id"]
    response = client.get(
        "/api/v1/search",
        params={"q": "late three times written warning."},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_search"},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert items[0]["document_id"] == document_id
    assert items[0]["title"] == "Attendance Policy"
    assert "late three times" in items[0]["snippet"]
    dumped = str(response.json()).lower()
    assert "vectors.test" not in dumped
    outcome = assembly.retrieval.retrieve(
        RetrievalQuery(text=POLICY_TEXT, principal_id="usr_admin")
    )
    assert outcome.status == "ok"
    assert outcome.evidence[0].document_id == document_id


def test_FR_DOC_005_runtime_duplicate_upload_skips_reingest():
    client_store = _StoringQdrantClient()
    assembly = assemble_runtime(_qdrant_settings(client_store))
    client = TestClient(assembly.app, base_url="https://testserver")
    token = _login(client)
    first = _upload(client, token, "one")
    second = _upload(client, token, "two")
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["document_id"] == second.json()["document_id"]
    assert first.json()["version_id"] == second.json()["version_id"]
    assert client_store.upsert_calls == 1


def test_GATE_P0_003_not_verified_by_http_ingest():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "celery" in evidence.lower()
    assert "fake" in evidence.lower() or "进程内" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
