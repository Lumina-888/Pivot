"""Document ingest domain service (FR-DOC-001~008). Parsing execution belongs to M07."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime

from pivot.documents.errors import (
    DocumentError,
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
    FileContent,
    ObjectStore,
    PreparedIngest,
    ResourceLimits,
    TaskRecord,
    TaskStore,
    VersionRecord,
    VersionStore,
)
from pivot.documents.signatures import (
    KIND_MEDIA_TYPE,
    download_filename,
    normalize_filename,
    sniff_kind,
    validate_upload,
)
from pivot.domain.document_state import TERMINAL_FAILURE, is_searchable, next_state
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
        delete_hook=None,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._chunks = chunks
        self._tasks = tasks
        self._objects = objects
        self._audits = audits
        self._limits = limits or ResourceLimits()
        self._clock = clock
        # Optional callback fired with the document id after a delete is
        # recorded, so derived indexes can reconcile. It must not raise.
        self._delete_hook = delete_hook

    def count_total(self) -> int:
        """Return total number of documents."""
        return len(self._documents.list_active())

    def _current_version_state(self, document_id: str) -> str | None:
        """State of the document's current version, if any.

        D8-11: DocumentRecord has no ``status`` field at all; the state
        lives on VersionRecord.state (the current version). Reading
        ``doc.status`` raised AttributeError, but only once a document
        existed -- the empty-library sum() never touched the attribute,
        which is why CI stayed green while real libraries 500'd.
        """
        versions = self._versions.list_for_document(document_id)
        for version in versions:
            if version.current:
                return version.state
        return None

    def count_indexed(self) -> int:
        """Return number of indexed documents."""
        count = 0
        for doc in self._documents.list_active():
            if doc.deleted_at is not None:
                continue
            state = self._current_version_state(doc.id)
            if state is not None and is_searchable(state, True, False):
                count += 1
        return count

    def count_pending(self) -> int:
        """Return number of pending documents."""
        pending = {
            "uploaded",
            "queued",
            "parsing",
            "chunking",
            "embedding",
            "indexed",
            "pending_approval",
        }
        count = 0
        for doc in self._documents.list_active():
            if doc.deleted_at is not None:
                continue
            if self._current_version_state(doc.id) in pending:
                count += 1
        return count

    def count_failed(self) -> int:
        """Return number of failed documents."""
        count = 0
        for doc in self._documents.list_active():
            if doc.deleted_at is not None:
                continue
            if self._current_version_state(doc.id) in TERMINAL_FAILURE:
                count += 1
        return count

    def list_tasks(self) -> tuple[TaskRecord, ...]:
        """Return all persisted ingest tasks, newest first."""
        return self._tasks.list_all()

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
        external_llm_allowed: bool = False,
        target_library_id: str | None = None,
        viewer_role: str | None = None,
        visible_libraries: frozenset[str] | None = None,
        visible_folder_ids: frozenset[str] | None = None,
        exception_document_ids: frozenset[str] | None = None,
        pending_target_matches: Callable[[str], bool] | None = None,
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
            # Content dedup (2026-11-03 local-real-deps defect 4):
            # a sha hit must never silently drop a requested target
            # library, never bypass publish approval, and never hand
            # back an id the uploader cannot read. The S3 repeat
            # rule ("same document returns the existing version, no
            # second request") is kept exactly where it is safe:
            #   * targeted upload, old version still pending_approval
            #     for the SAME target (pending_target_matches, when
            #     the caller can say) -> return it; a pending version
            #     with NO pending request at all (orphan) also
            #     returns, because there is no conflicting target
            #     and the HTTP layer creates the missing request
            #     for the requested target (heal path);
            #   * targeted upload, old version already decided
            #     (uploaded/ready/...) -> fork a fresh pending_approval
            #     document, routed by the caller through ADR-019;
            #   * targeted upload, old version pending but for a
            #     different target (callback says so) -> fork;
            #   * untargeted upload, old document unreadable to the
            #     caller under the same library/folder/exception
            #     channels as _visible_document -> fork. Readability
            #     is computed here from the caller's visible sets,
            #     NOT via AccessControl.authorize_document, whose
            #     catalog is a separate store from this service's
            #     document rows (in the pipeline harness they diverge,
            #     and authorize_document would wrongly deny even an
            #     admin's own upload);
            #   * otherwise (no target and readable, or no viewer
            #     info supplied, i.e. legacy callers) -> return it.
            # The old version is left untouched in every branch;
            # nothing is moved. A legacy caller without the target
            # callback that re-uploads a pending document to a
            # different target still returns the old version — that
            # residual is documented in the PR; production routing
            # always supplies the callback.
            fork = False
            if target_library_id is not None:
                if duplicate.state != "pending_approval":
                    fork = True
                elif pending_target_matches is not None:
                    try:
                        fork = not pending_target_matches(duplicate.document_id)
                    except Exception:
                        fork = True
            elif viewer_role is not None:
                if viewer_role != "admin":
                    old_document = self._documents.get(duplicate.document_id)
                    readable = old_document is not None and self._is_visible(
                        old_document,
                        visible_libraries or frozenset(),
                        visible_folder_ids,
                        exception_document_ids,
                    )
                    fork = not readable
            if not fork:
                self._audit(actor_id, "doc.upload_idempotent", duplicate.id, "ok", request_id)
                return duplicate
            self._audit(actor_id, "doc.upload_fork", duplicate.id, "ok", request_id)
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
            # P1-3 S3: a targeted upload is born pending_approval and
            # never enters the pipeline until approval (or the
            # self-approval fast path) moves it to uploaded. The route
            # validates the target before calling upload, so this
            # service trusts the parameter; idempotent returns below
            # return the existing version untouched, so a repeat upload
            # never flips state and never spawns a second request.
            state="pending_approval" if target_library_id is not None else "uploaded",
            current=False,
            idempotency_key=idempotency_key,
            external_llm_allowed=external_llm_allowed,
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

    def prepare_ingest(
        self, version_id: str, request_id: str, actor_id: str
    ) -> PreparedIngest | None:
        version = self._require_version(version_id, request_id)
        if version.state not in {"uploaded", "queued"}:
            return None
        try:
            if version.state == "uploaded":
                task = self.enqueue(version_id, request_id, actor_id)
            else:
                task = TaskRecord(
                    id=new_id("task"),
                    entity_id=version.id,
                    entity_type="document_version",
                    attempt=1,
                    state="queued",
                )
                self._tasks.save(task)
            version = self.worker_started(version_id, task.id, request_id)
        except DocumentError:
            return None
        document = self._require_document(version.document_id, request_id)
        content = self._objects.get(version.storage_key)
        if not content:
            raise DocumentError("RESOURCE_NOT_FOUND", "资源不存在", request_id)
        kind = sniff_kind(content)
        return PreparedIngest(
            version=version,
            document=document,
            content=content,
            kind=kind,
            task_id=task.id,
        )

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
            self._chunks.add(chunk)
        self._versions.save(version)
        return version

    def retry(self, version_id: str, request_id: str, actor_id: str) -> VersionRecord:
        version = self._advance(version_id, "retry", request_id)
        version.current = False
        self._versions.save(version)
        self._audit(actor_id, "doc.retry", version.id, "ok", request_id)
        return version

    def retry_document(self, document_id: str, request_id: str, actor_id: str) -> VersionRecord:
        self._require_document(document_id, request_id)
        failed = [
            version
            for version in self._versions.list_for_document(document_id)
            if version.state in TERMINAL_FAILURE
        ]
        if not failed:
            raise DocumentError("RESOURCE_FORBIDDEN", "没有可重试的失败版本", request_id)
        return self.retry(failed[-1].id, request_id, actor_id)

    def open_content(
        self,
        document_id: str,
        *,
        viewer_role: str,
        visible_libraries: frozenset[str],
        request_id: str,
        purpose: str,
        actor_id: str,
        visible_folder_ids: frozenset[str] | None = None,
        exception_document_ids: frozenset[str] | None = None,
    ) -> FileContent:
        if purpose not in {"preview", "download"}:
            raise DocumentError("RESOURCE_FORBIDDEN", "非法用途", request_id)
        document = self._visible_document(
            document_id,
            viewer_role,
            visible_libraries,
            request_id,
            visible_folder_ids=visible_folder_ids,
            exception_document_ids=exception_document_ids,
        )
        body = self._object_bytes(document.id, request_id)
        kind = sniff_kind(body)
        extension = f".{kind}" if kind in KIND_MEDIA_TYPE else ".bin"
        payload = FileContent(
            body=body,
            filename=download_filename(document.title, extension),
            media_type=KIND_MEDIA_TYPE.get(kind, "application/octet-stream"),
            disposition="inline" if purpose == "preview" else "attachment",
        )
        self._audit(actor_id, f"doc.{purpose}", document.id, "ok", request_id)
        return payload

    def get_detail(
        self,
        document_id: str,
        *,
        viewer_role: str,
        visible_libraries: frozenset[str],
        request_id: str,
        visible_folder_ids: frozenset[str] | None = None,
        exception_document_ids: frozenset[str] | None = None,
    ) -> dict[str, object]:
        document = self._visible_document(
            document_id,
            viewer_role,
            visible_libraries,
            request_id,
            visible_folder_ids=visible_folder_ids,
            exception_document_ids=exception_document_ids,
        )
        created = document.created_at or self._now()
        return {
            "document_id": document.id,
            "title": document.title,
            "space": document.space,
            "tags": list(document.tags),
            "classification": document.classification,
            "created_by": document.created_by,
            "created_at": created.isoformat(),
            "deleted_at": None if document.deleted_at is None else document.deleted_at.isoformat(),
            "versions": [
                self._version_view(version)
                for version in self._versions.list_for_document(document.id)
            ],
        }

    def list_versions(
        self,
        document_id: str,
        *,
        viewer_role: str,
        visible_libraries: frozenset[str],
        request_id: str,
        visible_folder_ids: frozenset[str] | None = None,
        exception_document_ids: frozenset[str] | None = None,
    ) -> tuple[dict[str, object], ...]:
        detail = self.get_detail(
            document_id,
            viewer_role=viewer_role,
            visible_libraries=visible_libraries,
            request_id=request_id,
            visible_folder_ids=visible_folder_ids,
            exception_document_ids=exception_document_ids,
        )
        return tuple(detail["versions"])  # type: ignore[arg-type]

    def request_delete(self, document_id: str, request_id: str, actor_id: str) -> DocumentRecord:
        document = self._require_document(document_id, request_id)
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
        if self._delete_hook is not None:
            self._delete_hook(document_id)
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
        visible_libraries: frozenset[str],
        space: str | None = None,
        tags: tuple[str, ...] = (),
        visible_folder_ids: frozenset[str] | None = None,
        exception_document_ids: frozenset[str] | None = None,
    ) -> tuple[dict[str, object], ...]:
        items: list[dict[str, object]] = []
        for document in self._documents.list_active():
            if document.deleted_at is not None:
                continue
            # Authorization basis (ADR-016 D2, ADR-017 D1, ADR-018
            # D3), same channels as AccessControl.authorize_document:
            # admin sees everything; otherwise an exception grant
            # opens exactly that document; otherwise the library must
            # be visible and, when a folder set is supplied, a
            # restricted folder must be visible too (None = default
            # folder, i.e. the library itself). When no folder set
            # is supplied (legacy callers), the previous
            # library-only behaviour is kept.
            if viewer_role != "admin" and not self._is_visible(
                document,
                visible_libraries,
                visible_folder_ids,
                exception_document_ids,
            ):
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

    def _is_visible(
        self,
        document: DocumentRecord,
        visible_libraries: frozenset[str],
        visible_folder_ids: frozenset[str] | None,
        exception_document_ids: frozenset[str] | None,
    ) -> bool:
        """Library + folder + exception visibility, mirroring
        AccessControl.authorize_document (ADR-016 D2, ADR-017 D1,
        ADR-018 D3). Exceptions open exactly the granted document,
        even inside an invisible folder; folders never replace
        exceptions. Deleted documents are never visible here (admin
        handling is the caller's branch, see _visible_document).
        """
        if document.deleted_at is not None:
            return False
        if exception_document_ids is not None and document.id in exception_document_ids:
            return True
        if document.library_id not in visible_libraries:
            return False
        if visible_folder_ids is None:
            return True
        if document.folder_id is None:
            return True
        return document.folder_id in visible_folder_ids

    def _visible_document(
        self,
        document_id: str,
        viewer_role: str,
        visible_libraries: frozenset[str],
        request_id: str,
        visible_folder_ids: frozenset[str] | None = None,
        exception_document_ids: frozenset[str] | None = None,
    ) -> DocumentRecord:
        document = self._require_document(document_id, request_id)
        # Super admins keep full access (ADR-016 D3), including deleted
        # documents, as before. Everyone else sees a document only
        # through the library/folder/exception channels in
        # _is_visible. Anything else is RESOURCE_NOT_FOUND: no
        # existence leak.
        if viewer_role != "admin" and not self._is_visible(
            document, visible_libraries, visible_folder_ids, exception_document_ids
        ):
            raise DocumentError("RESOURCE_NOT_FOUND", "资源不存在", request_id)
        return document

    def _object_bytes(self, document_id: str, request_id: str) -> bytes:
        versions = self._versions.list_for_document(document_id)
        preferred = [version for version in versions if version.current]
        ordered = (*preferred, *reversed(versions))
        seen: set[str] = set()
        for version in ordered:
            if version.id in seen:
                continue
            seen.add(version.id)
            payload = self._objects.get(version.storage_key)
            if payload is not None:
                return payload
        raise DocumentError("RESOURCE_NOT_FOUND", "资源不存在", request_id)

    def _require_document(self, document_id: str, request_id: str) -> DocumentRecord:
        document = self._documents.get(document_id)
        if document is None:
            raise DocumentError("RESOURCE_NOT_FOUND", "资源不存在", request_id)
        return document

    def _require_version(self, version_id: str, request_id: str) -> VersionRecord:
        version = self._versions.get(version_id)
        if version is None:
            raise DocumentError("RESOURCE_NOT_FOUND", "资源不存在", request_id)
        return version

    def _version_view(self, version: VersionRecord) -> dict[str, object]:
        return {
            "version_id": version.id,
            "document_id": version.document_id,
            "version_label": version.id,
            "state": version.state,
            "current": version.current,
            "content_sha256": version.content_sha256,
            "external_llm_allowed": version.external_llm_allowed,
        }

    def _now(self) -> datetime:
        return self._clock() if callable(self._clock) else self._clock

    def _audit(self, actor: str, action: str, target: str, result: str, request_id: str) -> None:
        self._audits.emit(
            AuditDraft(
                actor=actor,
                action=action,
                target=target,
                result=result,
                request_id=request_id,
            )
        )
