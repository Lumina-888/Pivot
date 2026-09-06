"""Public download URLs that never embed object-store endpoints (FR-EXPORT-001)."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from urllib.parse import urlparse

from pivot.exports.models import ExportRecord

_INTERNAL_MARKERS = (
    "minio",
    "s3.amazonaws",
    "s3.",
    "127.0.0.1",
    "localhost",
    "10.",
    "192.168.",
    ":9000",
    "internal",
)


class PublicDownloadSigner:
    def __init__(self, public_base: str, secret: str) -> None:
        self._base = public_base.rstrip("/")
        self._secret = secret.encode("utf-8")
        self._reject_internal_base()

    def sign(self, record: ExportRecord, *, now: datetime, expires_seconds: int) -> str:
        expiry = int(now.timestamp()) + expires_seconds
        digest = hmac.new(
            self._secret,
            f"{record.id}:{expiry}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:32]
        url = f"{self._base}/d/{record.id}?e={expiry}&s={digest}"
        if contains_internal_storage_host(url):
            raise ValueError("download signer produced an internal storage URL")
        return url

    def _reject_internal_base(self) -> None:
        if contains_internal_storage_host(self._base):
            raise ValueError("download public_base must not be an object-store endpoint")


def contains_internal_storage_host(url: str) -> bool:
    lowered = url.lower()
    host = (urlparse(url).hostname or "").lower()
    if any(marker in lowered for marker in ("minio", "s3.amazonaws", ":9000", "internal")):
        return True
    if host in {"127.0.0.1", "localhost"}:
        return True
    if host.startswith("10.") or host.startswith("192.168.") or host.startswith("172."):
        return True
    return False
