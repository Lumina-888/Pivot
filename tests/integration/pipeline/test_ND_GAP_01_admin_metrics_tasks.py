"""ND-GAP-01: Admin metrics and tasks HTTP routes."""

from __future__ import annotations

from fastapi.testclient import TestClient
from harness import Pipeline
from pivot.http import create_app


class FakeProbes:
    """Fake probes for testing admin metrics."""

    def postgres(self) -> bool:
        return True

    def minio(self) -> bool:
        return True

    def qdrant(self) -> bool:
        return True

    def redis(self) -> bool:
        return True


def test_FR_RBAC_001_admin_metrics_forbidden_to_user():
    """普通用户访问 /admin/metrics 返回 403."""
    pipeline = Pipeline()
    client = TestClient(
        create_app(
            auth=pipeline.auth,
            probes=FakeProbes(),
            documents=pipeline.documents,
            runs=pipeline.runs,
        ),
        base_url="https://testserver",
    )

    # Login as user and get token
    login = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "correct-password"}
    )
    user_token = login.json()["access_token"]

    response = client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "AUTH_FORBIDDEN"


def test_FR_RBAC_001_admin_tasks_forbidden_to_user():
    """普通用户访问 /admin/tasks 返回 403."""
    pipeline = Pipeline()
    client = TestClient(
        create_app(
            auth=pipeline.auth,
            probes=FakeProbes(),
            documents=pipeline.documents,
            runs=pipeline.runs,
        ),
        base_url="https://testserver",
    )

    # Login as user and get token
    login = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "correct-password"}
    )
    user_token = login.json()["access_token"]

    response = client.get(
        "/api/v1/admin/tasks",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "AUTH_FORBIDDEN"


def test_NFR_OBS_005_admin_metrics_returns_structure():
    """管理员可以获取系统指标，响应包含必需结构."""
    pipeline = Pipeline()
    client = TestClient(
        create_app(
            auth=pipeline.auth,
            probes=FakeProbes(),
            documents=pipeline.documents,
            runs=pipeline.runs,
        ),
        base_url="https://testserver",
    )

    # Login as admin and get token
    login = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    admin_token = login.json()["access_token"]

    response = client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()

    # Verify structure
    assert "system" in body
    assert "status" in body["system"]
    assert body["system"]["status"] in ("operational", "degraded")
    assert "timestamp" in body["system"]

    assert "qa" in body
    assert "total_runs" in body["qa"]
    assert "completed" in body["qa"]
    assert "failed" in body["qa"]
    assert "in_progress" in body["qa"]

    assert "documents" in body
    assert "total" in body["documents"]
    assert "indexed" in body["documents"]
    assert "pending" in body["documents"]
    assert "failed" in body["documents"]

    assert "storage" in body
    assert "postgres" in body["storage"]
    assert "minio" in body["storage"]
    assert "qdrant" in body["storage"]
    assert "redis" in body["storage"]

    # All values should be integers or booleans
    for key in ("total_runs", "completed", "failed", "in_progress"):
        assert isinstance(body["qa"][key], int)
    for key in ("total", "indexed", "pending", "failed"):
        assert isinstance(body["documents"][key], int)
    for key in ("postgres", "minio", "qdrant", "redis"):
        assert isinstance(body["storage"][key], bool)


def test_NFR_OBS_006_admin_tasks_returns_structure():
    """管理员可以获取任务列表，响应包含必需结构."""
    pipeline = Pipeline()
    client = TestClient(
        create_app(
            auth=pipeline.auth,
            probes=FakeProbes(),
            documents=pipeline.documents,
            runs=pipeline.runs,
        ),
        base_url="https://testserver",
    )

    # Login as admin and get token
    login = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    admin_token = login.json()["access_token"]

    response = client.get(
        "/api/v1/admin/tasks",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()

    # Verify structure
    assert "tasks" in body
    assert isinstance(body["tasks"], list)
    assert "pagination" in body
    # Initial implementation has empty tasks and null pagination


def test_admin_metrics_requires_authentication():
    """未认证访问 /admin/metrics 返回 401."""
    pipeline = Pipeline()
    client = TestClient(
        create_app(
            auth=pipeline.auth,
            probes=FakeProbes(),
            documents=pipeline.documents,
            runs=pipeline.runs,
        ),
        base_url="https://testserver",
    )
    response = client.get("/api/v1/admin/metrics")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "AUTH_INVALID_CREDENTIALS"


def test_admin_tasks_requires_authentication():
    """未认证访问 /admin/tasks 返回 401."""
    pipeline = Pipeline()
    client = TestClient(
        create_app(
            auth=pipeline.auth,
            probes=FakeProbes(),
            documents=pipeline.documents,
            runs=pipeline.runs,
        ),
        base_url="https://testserver",
    )
    response = client.get("/api/v1/admin/tasks")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "AUTH_INVALID_CREDENTIALS"
