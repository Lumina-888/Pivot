"""In-process fact backup/restore. Not new ECS; GATE-P0-006 stays unverified."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from pivot.audit.service import AuditService
from pivot.audit.store import AppendOnlyAuditStore
from pivot.auth.ports import UserAccount
from pivot.http.memory import InMemoryUserDirectory, MemoryDocumentObjects, UtcClock
from pivot.retrieval.fakes import HashingQueryEmbedder
from pivot.storage.adapters.qdrant import QdrantVectorStore

_ROOT = Path(__file__).resolve().parents[3]
_OPS = str(_ROOT / "ops")
if _OPS not in sys.path:
    sys.path.insert(0, _OPS)
from fact_backup import (  # noqa: E402
    FACT_STORES,
    REBUILDABLE_STORES,
    capture_facts,
    restore_facts,
)

_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "capacity-backup.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_RUNBOOK = _ROOT / "ops" / "runbook-backup-restore.md"
_BACKUP_SRC = _ROOT / "ops" / "fact_backup.py"


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
            score = sum(a * b for a, b in zip(query, vector, strict=False))
            hits.append(SimpleNamespace(id=pid, score=score, payload=payload))
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def delete(self, collection_name, points_selector=None) -> None:
        return None


def _user() -> UserAccount:
    return UserAccount(
        id="usr_restore",
        username="restore-admin",
        password_hash="$argon2id$restore",
        role="admin",
        status="active",
        token_version=1,
    )


def _vector_point(embedder: HashingQueryEmbedder) -> dict:
    text = "late three times written warning."
    return {
        "vector": embedder.embed([text])[0],
        "version_id": "ver_restore",
        "chunk_id": "chk_restore",
        "document_id": "doc_restore",
        "text": text,
        "title": "Attendance Policy",
        "ready": True,
        "current": True,
        "allowed": True,
    }


def test_NFR_DR_restore_roundtrip_users_objects_vectors_audit():
    users = InMemoryUserDirectory([_user()])
    objects = MemoryDocumentObjects()
    objects.put("docs/policy.pdf", b"%PDF-1.4 restore")
    embedder = HashingQueryEmbedder(dimension=4)
    client = _StoringQdrantClient()
    store = QdrantVectorStore(
        client,
        collection="pivot-chunks",
        ensure_collection=True,
        vector_size=4,
        distance="Cosine",
    )
    point = _vector_point(embedder)
    store.upsert([point])
    audits = AppendOnlyAuditStore()
    clock = UtcClock()
    service = AuditService(audits, clock)
    service.record(
        actor="usr_restore",
        action="document.upload",
        target="doc_restore",
        result="ok",
        request_id="req_seed",
    )
    backup = capture_facts(
        users=users,
        object_store=objects,
        vector_points=(point,),
        audit_store=audits,
    )

    restored_users = InMemoryUserDirectory()
    restored_objects = MemoryDocumentObjects()
    restored_client = _StoringQdrantClient()
    restored_vectors = QdrantVectorStore(
        restored_client,
        collection="pivot-chunks",
        ensure_collection=True,
        vector_size=4,
        distance="Cosine",
    )
    restored_audits = AppendOnlyAuditStore()
    restore_facts(
        backup,
        users=restored_users,
        object_store=restored_objects,
        vector_store=restored_vectors,
        audit_store=restored_audits,
    )
    restored_service = AuditService(restored_audits, clock)
    restored_service.record(
        actor="system",
        action="ops.backup_restore",
        target="fixture",
        result="ok",
        request_id="req_restore",
    )

    found = restored_users.get_by_username("restore-admin")
    assert found is not None
    assert found.password_hash == "$argon2id$restore"
    assert restored_objects.get("docs/policy.pdf") == b"%PDF-1.4 restore"
    hits = restored_vectors.search(point["vector"], limit=4)
    assert hits[0]["chunk_id"] == "chk_restore"
    actions = {event.action for event in restored_audits.list()}
    assert "document.upload" in actions
    assert "ops.backup_restore" in actions


def test_NFR_DR_redis_is_not_a_fact_in_backup():
    assert "redis" in REBUILDABLE_STORES
    assert "redis" not in FACT_STORES
    assert "postgres" in FACT_STORES
    assert "minio" in FACT_STORES
    assert "qdrant" in FACT_STORES
    assert "audit" in FACT_STORES
    source = _BACKUP_SRC.read_text(encoding="utf-8")
    assert "FACT_STORES" in source
    assert "redis" in source.lower()


def test_NFR_DR_restore_records_backup_audit():
    runbook = _RUNBOOK.read_text(encoding="utf-8")
    assert "ops.backup_restore" in runbook or "审计" in runbook
    assert "PostgreSQL" in runbook
    assert "MinIO" in runbook
    assert "Qdrant" in runbook


def test_NFR_DR_does_not_freeze_rpo_rto():
    source = _BACKUP_SRC.read_text(encoding="utf-8")
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "24" not in source
    assert "RPO" not in source
    assert "RTO" not in source
    assert "TBD-P0" in evidence
    assert "unverified" in evidence.lower()


def test_GATE_P0_006_not_verified_by_in_process_restore():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    limits = _LIMITS.read_text(encoding="utf-8")
    runbook = _RUNBOOK.read_text(encoding="utf-8")
    assert "GATE-P0-006" in evidence
    assert "unverified" in evidence.lower()
    assert "新 ECS" in runbook or "new ECS" in runbook.lower()
    line = next(item for item in limits.splitlines() if "GATE-P0-006" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
