"""Opt-in Qdrant VectorStore smoke against Compose. Not GATE-P0-003 verified."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "qdrant-vector-store.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_FIXTURE_ENDPOINT = "127.0.0.1:6333"
_FIXTURE_COLLECTION = "pivot-test-chunks"


def _require_compose() -> bool:
    return os.environ.get("PIVOT_REQUIRE_COMPOSE") == "1"


def _qdrant_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 6333), timeout=0.3):
            return True
    except OSError:
        return False


def _qdrant_available() -> bool:
    try:
        import qdrant_client  # noqa: F401
    except ImportError:
        return False
    return True


def _skip_or_fail(reason: str) -> None:
    if _require_compose():
        pytest.fail(reason)
    pytest.skip(reason)


def test_M03_qdrant_vector_store_when_compose_up():
    if not _qdrant_reachable():
        _skip_or_fail("compose qdrant is not reachable on 127.0.0.1:6333")
    if not _qdrant_available():
        _skip_or_fail("qdrant extra is not installed; pip install -e ./api[qdrant]")

    from pivot.storage.adapters.qdrant import QdrantVectorStore
    from pivot.storage.config import VectorStoreConfig

    endpoint = os.environ.get("PIVOT_QDRANT_ENDPOINT", _FIXTURE_ENDPOINT)
    collection = os.environ.get("PIVOT_QDRANT_COLLECTION", _FIXTURE_COLLECTION)
    store = QdrantVectorStore.connect(
        VectorStoreConfig(endpoint=endpoint, collection=collection),
        ensure_collection=True,
        vector_size=4,
        distance="Cosine",
    )
    store.upsert(
        [
            {
                "vector": [1.0, 0.0, 0.0, 0.0],
                "version_id": "ver_compose",
                "chunk_id": "chk_compose",
            }
        ]
    )
    try:
        hits = store.search([1.0, 0.0, 0.0, 0.0], limit=1)
        assert hits[0]["chunk_id"] == "chk_compose"
        assert hits[0]["version_id"] == "ver_compose"
        assert store.healthy() is True
    finally:
        store.delete(chunk_id="chk_compose")


def test_GATE_P0_003_not_verified_by_qdrant_vector_store():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-003" in evidence
    assert "unverified" in evidence.lower()
    assert "vector" in evidence.lower() or "向量" in evidence
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-003" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
