"""Export authorization, generation and expiry (FR-EXPORT-001~003)."""

from __future__ import annotations

from datetime import timedelta

from pivot.audit.ports import Actor
from pivot.exports.content import (
    build_conversation_payload,
    build_document_payload,
    sanitize_filename,
)
from pivot.exports.errors import export_expired, not_found
from pivot.exports.machine import apply, is_downloadable
from pivot.exports.models import (
    EXPORT_FORMATS,
    EXPORTABLE_RUN_STATES,
    SOURCE_TYPES,
    ExportRecord,
    created_dto,
    status_dto,
)
from pivot.exports.ports import (
    AccessControlPort,
    AnswerStore,
    AuditRecorder,
    Clock,
    DownloadSigner,
    ExportRepository,
    ObjectStorePort,
)
from pivot.exports.render import render
from pivot.exports.signer import contains_internal_storage_host
from pivot.shared.ids import new_id


class ExportService:
    def __init__(
        self,
        *,
        access: AccessControlPort,
        answers: AnswerStore,
        exports: ExportRepository,
        objects: ObjectStorePort,
        audits: AuditRecorder,
        clock: Clock,
        signer: DownloadSigner,
        ttl_seconds: int,
        download_ttl_seconds: int,
    ) -> None:
        # ttl_seconds / download_ttl_seconds are injected; retention remains TBD-P0.
        self._access = access
        self._answers = answers
        self._exports = exports
        self._objects = objects
        self._audits = audits
        self._clock = clock
        self._signer = signer
        self._ttl_seconds = ttl_seconds
        self._download_ttl_seconds = download_ttl_seconds

    def create(
        self,
        actor: Actor,
        *,
        source_type: str,
        source_id: str,
        fmt: str,
        request_id: str,
    ) -> dict[str, str]:
        if source_type not in SOURCE_TYPES or fmt not in EXPORT_FORMATS:
            raise not_found(request_id)
        self._authorize_source(actor, source_type, source_id, request_id)
        now = self._clock.now()
        record = ExportRecord(
            id=new_id("export"),
            owner_id=actor.user_id,
            source_type=source_type,
            source_id=source_id,
            format=fmt,
            state="requested",
            expires_at=now + timedelta(seconds=self._ttl_seconds),
            created_at=now,
            filename=sanitize_filename(source_id, fmt),
        )
        self._exports.add(record)
        self._audits.record(
            actor=actor.user_id,
            action="export.create",
            target=record.id,
            result="ok",
            request_id=request_id,
            metadata={"source_type": source_type, "source_id": source_id, "format": fmt},
        )
        self._process(actor, record, request_id)
        return created_dto(record)

    def get(self, actor: Actor, export_id: str, request_id: str) -> dict[str, str | None]:
        record = self._load_authorized(actor, export_id, request_id)
        self._expire_if_due(actor, record, request_id)
        download_url = None
        if is_downloadable(record.state):
            download_url = self._public_url(record)
        return status_dto(record, download_url)

    def download(self, actor: Actor, export_id: str, request_id: str) -> tuple[bytes, str, str]:
        record = self._load_authorized(actor, export_id, request_id)
        self._expire_if_due(actor, record, request_id)
        if record.state == "expired":
            raise export_expired(request_id)
        if not is_downloadable(record.state) or not record.storage_key:
            raise not_found(request_id)
        payload = self._objects.get(record.storage_key)
        self._audits.record(
            actor=actor.user_id,
            action="export.download",
            target=record.id,
            result="ok",
            request_id=request_id,
            metadata={"filename": record.filename},
            run_id=record.run_id,
        )
        return payload, record.filename, record.content_type or "application/octet-stream"

    def _authorize_source(
        self, actor: Actor, source_type: str, source_id: str, request_id: str
    ) -> None:
        if source_type == "conversation":
            self._access.authorize_conversation(actor, source_id, request_id)
        else:
            self._access.authorize_document(actor, source_id, request_id)

    def _load_authorized(self, actor: Actor, export_id: str, request_id: str) -> ExportRecord:
        record = self._exports.get(export_id)
        if record is None:
            raise not_found(request_id)
        self._access.authorize_export(actor, export_id, request_id)
        return record

    def _process(self, actor: Actor, record: ExportRecord, request_id: str) -> None:
        record.state = apply(record.state, "queue", request_id)
        record.state = apply(record.state, "generate", request_id)
        self._exports.save(record)
        try:
            payload = self._load_payload(record)
            body, filename, content_type = render(payload, record.format)
            record.filename = filename
            record.content_type = content_type
            record.run_id = payload.get("run_id")
            key = f"exports/{record.id}/{filename}"
            self._objects.put(key, body, content_type=content_type)
            record.storage_key = key
            record.state = apply(record.state, "succeed", request_id)
            self._exports.save(record)
        except Exception:
            record.state = apply(record.state, "fail", request_id)
            record.error_code = "EXPORT_FAILED"
            self._exports.save(record)
            self._audits.record(
                actor=actor.user_id,
                action="export.failed",
                target=record.id,
                result="failed",
                request_id=request_id,
                metadata={"source_id": record.source_id},
            )

    def _load_payload(self, record: ExportRecord) -> dict:
        if record.source_type == "conversation":
            answer = self._answers.get_exportable_answer(record.source_id)
            if answer is None or answer.state not in EXPORTABLE_RUN_STATES:
                raise ValueError("no persisted final answer")
            payload = build_conversation_payload(answer)
            record.filename = sanitize_filename(answer.title, record.format)
            return payload
        document = self._answers.get_document_export(record.source_id)
        if document is None:
            raise ValueError("no exportable document view")
        record.filename = sanitize_filename(document.title, record.format)
        return build_document_payload(document)

    def _expire_if_due(self, actor: Actor, record: ExportRecord, request_id: str) -> None:
        if record.state == "expired":
            return
        if record.state == "ready" and self._clock.now() >= record.expires_at:
            record.state = apply(record.state, "expire", request_id)
            self._exports.save(record)
            self._audits.record(
                actor=actor.user_id,
                action="export.expired",
                target=record.id,
                result="expired",
                request_id=request_id,
            )

    def _public_url(self, record: ExportRecord) -> str:
        url = self._signer.sign(
            record,
            now=self._clock.now(),
            expires_seconds=self._download_ttl_seconds,
        )
        if contains_internal_storage_host(url):
            raise RuntimeError("refusing to expose object-store endpoint")
        return url
