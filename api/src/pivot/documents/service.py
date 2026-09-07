"""Document ingest domain service (FR-DOC-001~008). Parsing execution belongs to M07."""

from __future__ import annotations

import hashlib
from datetime import datetime

from pivot.documents.errors import (
    invalid_signature,
    resource_limit,
    unsupported_extension,
)
from pivot.documents.ports import (
    AuditDraft,
    AuditSink,
    ChunkRecord,
    ChunkStore,
    DocumentRecord,
    DocumentStore,
    ObjectStore,
    ResourceLimits,
    TaskRecord,
    TaskStore,
    VersionRecord,
    VersionStore,
)
from pivot.documents.signatures import normalize_filename, validate_upload
from pivot.domain.document_state import is_searchable, next_state
from pivot.shared.ids import new_id
from pivot.shared.time import utc_now


class DocumentService:
    def __init__(
        self,
        documents: DocumentStore,
        versions: VersionStore,
        chunks: ChunkStore,
        tasks: TaskStore,
        objects: ObjectStore,
        audits: AuditSink,
        limits: ResourceLimits | None = None,
        clock=utc_now,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._chunks = chunks
        self._tasks = tasks
        self._objects = objects
        self._audits = audits
        self._limits = limits or ResourceLimits()
        self._clock = clock

    def upload(
        self,
        *,
        filename: str,
        declared_mime: str,
        content: bytes,
        title: str,
        actor_id: str,
        request_id: str,
        idempotency_key: str | None = None,
        space: str = "shared",
        classification: str = "",
        tags: tuple[str, ...] = (),
    ) -> VersionRecord:
        try:
            normalize_filename(filename)
            validate_upload(filename, declared_mime, content)
        except ValueError as exc:
            code = str(exc)
            self._audit(actor_id, "doc.upload_rejected", filename, "denied", request_id)
            if code == "UNSUPPORTED_EXTENSION":
                raise unsupported_extension(request_id) from exc
            raise invalid_signature(request_id) from exc
        if self._limits.max_bytes is not None and len(content) > self._limits.max_bytes:
            raise resource_limit(request_id)
        digest = hashlib.sha256(content).hexdigest()
        if idempotency_key:
            existing = self._versions.find_by_idempotency(idempotency_key)
            if existing is not None:
                return existing
        duplicate = self._versions.find_by_sha(digest)
        if duplicate is not None:
            self._audit(actor_id, "doc.upload_idempotent", duplicate.id, "ok", request_id)
            return duplicate
        document = DocumentRecord(
            id=new_id("document"),
            title=title,
            space=space,
            created_by=actor_id,
            classification=classification,
            created_at=self._now(),
            tags=tags,
        )
        version_id = new_id("version")
        version = VersionRecord(
            id=version_id,
            document_id=document.id,
            content_sha256=digest,
            storage_key=f"quarantine/{document.id}/{version_id}",
            state="uploaded",
            current=False,
            idempotency_key=idempotency_key,
        )
        self._objects.put(version.storage_key, content)
        self._documents.save(document)
        self._versions.save(version)
        self._audit(actor_id, "doc.upload", version.id, "ok", request_id)
        return version

    def enqueue(self, version_id: str, request_id: str, actor_id: str = "system") -> TaskRecord:
        version = self._require_version(version_id, request_id)
        version.state = next_state(version.state, "enqueue", request_id)
        task = TaskRecord(
            id=new_id("task"),
            entity_id=version.id,
            entity_type="document_version",
            attempt=1,
            state="queued",
        )
        self._versions.save(version)
        self._tasks.save(task)
        self._audit(actor_id, "doc.enqueue", version.id, "ok", request_id)
        return task

    def worker_started(self, version_id: str, task_id: str, request_id: str) -> VersionRecord:
        version = self._require_version(version_id, request_id)
        version.state = next_state(version.state, "worker_started", request_id)
        task = self._tasks.get(task_id)
        if task is not None:
            task.state = "started"
            self._tasks.save(task)
        self._versions.save(version)
        return version

    def parse_ok(self, version_id: str, request_id: str) -> VersionRecord:
        return self._advance(version_id, "parse_ok", request_id)

    def parse_error(self, version_id: str, code: str, request_id: str) -> VersionRecord:
        version = self._advance(version_id, "parse_error", request_id)
        version.current = False
        version.error_code = code
        self._versions.save(version)
        return version

    def apply_chunks(
        self, version_id: str, texts: list[str], message_id: str, request_id: str
    ) -> tuple[ChunkRecord, ...]:
        version = self._require_version(version_id, request_id)
        existing = self._chunks.list_for_version(version.id)
        task = self._tasks.get(message_id)
        if task is not None and existing:
            return existing
        if existing:
            return existing
        records = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            chunk = ChunkRecord(
                id=new_id("chunk"),
                version_id=version.id,
                text=text,
                text_hash=digest,
                published=False,
            )
            self._chunks.add(chunk)
            records.append(chunk)
        self._tasks.save(
            TaskRecord(
                id=message_id,
                entity_id=version.id,
                entity_type="chunk",
                attempt=1,
                state="applied",
            )
        )
        self._advance(version_id, "chunk_ok", request_id)
        return tuple(records)

    def embedding_ok(self, version_id: str, request_id: str) -> VersionRecord:
        return self._advance(version_id, "embedding_ok", request_id)

    def embedding_error(self, version_id: str, request_id: str) -> VersionRecord:
        version = self._advance(version_id, "embedding_error", request_id)
        version.current = False
        self._versions.save(version)
        return version

    def publish(self, version_id: str, request_id: str) -> VersionRecord:
        version = self._require_version(version_id, request_id)
        version.state = next_state(version.state, "validation_ok", request_id)
        for other in self._versions.list_for_document(version.document_id):
            if other.id != version.id and other.current:
                other.current = False
                self._versions.save(other)
        version.current = True
        for chunk in self._chunks.list_for_version(version.id):
            chunk.published = True
        self._versions.save(version)
        return version

    def retry(self, version_id: str, request_id: str, actor_id: str) -> VersionRecord:
        version = self._advance(version_id, "retry", request_id)
        version.current = False
        self._versions.save(version)
        self._audit(actor_id, "doc.retry", version.id, "ok", request_id)
        return version

    def request_delete(self, document_id: str, request_id: str, actor_id: str) -> DocumentRecord:
        document = self._documents.get(document_id)
        if document is None:
            from pivot.documents.errors import DocumentError

            raise DocumentError("RESOURCE_NOT_FOUND", "资源不存在", request_id)
        now = self._now()
        document.deleted_at = now
        self._documents.save(document)
        for version in self._versions.list_for_document(document_id):
            if version.state == "ready":
                version.state = next_state(version.state, "delete_requested", request_id)
            version.current = False
            self._versions.save(version)
            for chunk in self._chunks.list_for_version(version.id):
                chunk.published = False
        self._audit(actor_id, "doc.delete_requested", document_id, "ok", request_id)
        return document

    def cleanup_ok(self, version_id: str, request_id: str) -> VersionRecord:
        version = self._require_version(version_id, request_id)
        if self._objects.exists(version.storage_key):
            self._objects.delete(version.storage_key)
        version.state = next_state(version.state, "cleanup_ok", request_id)
        version.current = False
        self._versions.save(version)
        self._audit("system", "doc.cleanup_ok", version.id, "ok", request_id)
        return version

    def cleanup_error(self, version_id: str, request_id: str) -> VersionRecord:
        version = self._advance(version_id, "cleanup_error", request_id)
        task = TaskRecord(
            id=new_id("task"),
            entity_id=version.id,
            entity_type="cleanup",
            attempt=1,
            state="delete_failed",
            retryable=True,
            error_code="RESOURCE_LIMIT",
        )
        self._tasks.save(task)
        return version

    def retry_cleanup(self, version_id: str, request_id: str) -> VersionRecord:
        return self._advance(version_id, "retry_cleanup", request_id)

    def list_library(
        self,
        *,
        viewer_role: str,
        space: str | None = None,
        tags: tuple[str, ...] = (),
    ) -> tuple[dict[str, object], ...]:
        items: list[dict[str, object]] = []
        for document in self._documents.list_active():
            if document.deleted_at is not None:
                continue
            if viewer_role != "admin" and document.space != "shared":
                continue
            if space is not None and document.space != space:
                continue
            if tags and not set(tags).issubset(document.tags):
                continue
            current = next(
                (
                    version
                    for version in self._versions.list_for_document(document.id)
                    if version.current and version.state == "ready"
                ),
                None,
            )
            created = document.created_at or self._now()
            items.append(
                {
                    "document_id": document.id,
                    "title": document.title,
                    "space": document.space,
                    "tags": list(document.tags),
                    "classification": document.classification,
                    "created_at": created.isoformat(),
                    "current_version": None
                    if current is None
                    else {
                        "version_id": current.id,
                        "version_label": current.id,
                        "state": current.state,
                    },
                }
            )
        return tuple(items)

    def visible_in_library(self, document_id: str) -> bool:
        document = self._documents.get(document_id)
        if document is None or document.deleted_at is not None:
            return False
        return any(
            is_searchable(version.state, version.current, False)
            for version in self._versions.list_for_document(document_id)
        )

    def searchable_version_ids(self) -> tuple[str, ...]:
        ids = []
        for document in self._documents.list_active():
            deleted = document.deleted_at is not None
            for version in self._versions.list_for_document(document.id):
                if is_searchable(version.state, version.current, deleted):
                    ids.append(version.id)
        return tuple(ids)

    def scan_orphans(
        self, object_keys: tuple[str, ...], vector_version_ids: tuple[str, ...]
    ) -> dict[str, tuple[str, ...]]:
        version_ids = {
            version.id
            for document in self._documents.list_active()
            for version in self._versions.list_for_document(document.id)
        }
        known_keys = {
            version.storage_key
            for document in self._documents.list_active()
            for version in self._versions.list_for_document(document.id)
        }
        orphan_objects = tuple(key for key in object_keys if key not in known_keys)
        orphan_vectors = tuple(vid for vid in vector_version_ids if vid not in version_ids)
        return {"objects": orphan_objects, "vectors": orphan_vectors}

    def _advance(self, version_id: str, event: str, request_id: str) -> VersionRecord:
        version = self._require_version(version_id, request_id)
        version.state = next_state(version.state, event, request_id)
        self._versions.save(version)
        return version

    def _require_version(self, version_id: str, request_id: str) -> VersionRecord:
        version = self._versions.get(version_id)
        if version is None:
            from pivot.documents.errors import DocumentError

            raise DocumentError("RESOURCE_NOT_FOUND", "资源不存在", request_id)
        return version

    def _now(self) -> datetime:
        return self._clock() if callable(self._clock) else self._clock

    def _audit(
        self, actor: str, action: str, target: str, result: str, request_id: str
    ) -> None:
        self._audits.emit(
            AuditDraft(
                actor=actor,
                action=action,
                target=target,
                result=result,
                request_id=request_id,
            )
        )
