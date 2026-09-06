"""In-memory ExportTask collection for Wave 1 unit tests. Production uses M03."""

from __future__ import annotations

from pivot.exports.models import ExportRecord


class InMemoryExportRepository:
    def __init__(self) -> None:
        self._items: dict[str, ExportRecord] = {}

    def add(self, record: ExportRecord) -> None:
        if record.id in self._items:
            raise ValueError(f"duplicate export id: {record.id}")
        self._items[record.id] = record

    def get(self, export_id: str) -> ExportRecord | None:
        return self._items.get(export_id)

    def save(self, record: ExportRecord) -> None:
        self._items[record.id] = record

    def list(self) -> tuple[ExportRecord, ...]:
        return tuple(self._items.values())
