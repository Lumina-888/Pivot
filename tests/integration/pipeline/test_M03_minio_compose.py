"""Opt-in MinIO ObjectStore smoke against Compose. Not GATE-P0-003 verified."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "minio-object-store.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_FIXTURE_ENDPOINT = "127.0.0.1:9000"
_FIXTURE_BUCKET = "pivot-docs"
_FIXTURE_ACCESS = "pivotminio"
_FIXTURE_SECRET = "pivot_dev_only"


def _require_compose() -> bool:
    return os.environ.get("PIVOT_REQUIRE_COMPOSE") == "1"


def _minio_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 9000), timeout=0.3):
            return True
    except OSError:
        return False


def _minio_available() -> bool:
    try:
        import minio  # noqa: F401
    except ImportError:
        return False
    return True


def _skip_or_fail(reason: str) -> None:
    if _require_compose():
        pytest.fail(reason)
    pytest.skip(reason)


def test_M03_minio_object_store_when_compose_up():
    if not _minio_reachable():
        _skip_or_fail("compose minio is not reachable on 127.0.0.1:9000")
    if not _minio_available():
        _skip_or_fail("minio extra is not installed; pip install -e ./api[minio]")

    from pivot.storage.adapters.minio import MinioObjectStore
    from pivot.storage.config import ObjectStoreConfig

    endpoint = os.environ.get("PIVOT_MINIO_ENDPOINT", _FIXTURE_ENDPOINT)
    bucket = os.environ.get("PIVOT_MINIO_BUCKET", _FIXTURE_BUCKET)
    access_key = os.environ.get("PIVOT_MINIO_ACCESS_KEY", _FIXTURE_ACCESS)
    secret_key = os.environ.get("PIVOT_MINIO_SECRET_KEY", _FIXTURE_SECRET)
    store = MinioObjectStore.connect(
        ObjectStoreConfig(endpoint=endpoint, bucket=bucket),
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
        ensure_bucket=True,
    )
    key = "quarantine/compose/minio-smoke"
    store.put(key, b"%PDF-1.4\ncompose\n%%EOF\n", content_type="application/pdf")
    try:
        assert store.exists(key) is True
        assert store.get(key) is not None
        assert store.get(key).startswith(b"%PDF")
        assert store.healthy() is True
    finally:
        store.delete(key)


def test_GATE_P0_003_not_verified_by_minio_object_store():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "object store" in evidence.lower() or "对象" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
