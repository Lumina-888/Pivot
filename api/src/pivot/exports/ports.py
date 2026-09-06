"""Ports consumed by export. M01/M05 implementations are injected, never imported."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pivot.audit.ports import Actor
from pivot.exports.models import (
    DocumentExportView,
    ExportRecord,
    PersistedAnswer,
)

__all__ = [
    "Actor",
    "AccessControlPort",
    "AnswerStore",
    "Clock",
    "DownloadSigner",
    "ExportRepository",
    "ObjectStorePort",
]


class Clock(Protocol):
    def now(self) -> datetime: ...


class AccessControlPort(Protocol):
    """Re-run M01 authorization; guessing IDs must not leak existence."""

    def authorize_conversation(
        self, actor: Actor, conversation_id: str, request_id: str
    ) -> None: ...

    def authorize_document(self, actor: Actor, document_id: str, request_id: str) -> None: ...

    def authorize_export(self, actor: Actor, export_id: str, request_id: str) -> None: ...


class AnswerStore(Protocol):
    """Read already-persisted M05 answers. Must never re-run QA."""

    def get_exportable_answer(self, conversation_id: str) -> PersistedAnswer | None: ...

    def get_document_export(self, document_id: str) -> DocumentExportView | None: ...


class ExportRepository(Protocol):
    def add(self, record: ExportRecord) -> None: ...

    def get(self, export_id: str) -> ExportRecord | None: ...

    def save(self, record: ExportRecord) -> None: ...


class ObjectStorePort(Protocol):
    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def presign(self, key: str, *, expires_seconds: int) -> str: ...


class DownloadSigner(Protocol):
    """Public short-lived URL factory. Must not embed object-store endpoints."""

    def sign(self, record: ExportRecord, *, now: datetime, expires_seconds: int) -> str: ...


class AuditRecorder(Protocol):
    def record(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        result: str,
        request_id: str,
        metadata: dict | None = None,
        run_id: str | None = None,
    ) -> None: ...
