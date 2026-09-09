"""Export ObjectStorePort over an injected byte store.

Public download URLs stay on PublicDownloadSigner. MinIO presign is not a
public download API (FR-EXPORT-001).
"""

from __future__ import annotations


class ExportObjectAdapter:
    def __init__(self, store) -> None:
        self._store = store

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        self._store.put(key, data, content_type=content_type)

    def get(self, key: str) -> bytes:
        payload = self._store.get(key)
        if payload is None:
            raise KeyError(key)
        return payload

    def exists(self, key: str) -> bool:
        return bool(self._store.exists(key))

    def presign(self, key: str, *, expires_seconds: int) -> str:
        raise RuntimeError("export public download must use PublicDownloadSigner")
