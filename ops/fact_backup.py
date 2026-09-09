"""In-process fact backup/restore fixture. Not encrypted OSS and not new ECS."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pivot.audit.models import AuditEventRecord
from pivot.auth.ports import UserAccount
from pivot.retrieval.models import ChunkRecord

FACT_STORES = ("postgres", "minio", "qdrant", "audit", "compose_migrations")
REBUILDABLE_STORES = ("redis",)


@dataclass(frozen=True)
class FactBackup:
    users: tuple[UserAccount, ...]
    objects: tuple[tuple[str, bytes], ...]
    vectors: tuple[dict, ...]
    audits: tuple[AuditEventRecord, ...]


def synthetic_chunks(*, count: int, text: str) -> tuple[ChunkRecord, ...]:
    if count <= 0:
        raise ValueError("count must be positive")
    return tuple(
        ChunkRecord(
            chunk_id=f"chk_{index}",
            version_id=f"ver_{index}",
            document_id=f"doc_{index}",
            text=f"{text} #{index}",
            title="synthetic",
            ready=True,
            current=True,
            allowed=True,
            index_generation="gen_synthetic",
            embedding_model_version="hash-embed-test",
            retrieval_config_version="cap-injected",
        )
        for index in range(count)
    )


def capture_facts(
    *,
    users,
    object_store,
    vector_points: Sequence[Mapping],
    audit_store,
) -> FactBackup:
    listed = tuple(users.list())
    keys = tuple(object_store.keys())
    objects = tuple((key, object_store.get(key)) for key in keys)
    if any(payload is None for _key, payload in objects):
        raise RuntimeError("object backup missing bytes")
    return FactBackup(
        users=listed,
        objects=objects,
        vectors=tuple(dict(point) for point in vector_points),
        audits=tuple(audit_store.list()),
    )


def restore_facts(
    backup: FactBackup,
    *,
    users,
    object_store,
    vector_store,
    audit_store,
) -> None:
    for user in backup.users:
        users.save(user)
    for key, payload in backup.objects:
        _put_object(object_store, key, payload)
    if backup.vectors:
        vector_store.upsert(backup.vectors)
    for event in backup.audits:
        audit_store.append(event)


def _put_object(object_store, key: str, payload: bytes) -> None:
    try:
        object_store.put(key, payload)
    except TypeError:
        object_store.put(key, payload, content_type="application/octet-stream")
