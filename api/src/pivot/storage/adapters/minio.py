"""MinIO-backed ObjectStore. Endpoint, bucket and credentials are injected."""

from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from typing import Protocol

from pivot.storage.config import ObjectStoreConfig
from pivot.storage.protocols import ObjectStore

__all__ = ["MinioObjectStore", "ObjectStore", "connect_minio_client"]


class MinioClient(Protocol):
    def bucket_exists(self, bucket: str) -> bool: ...
    def make_bucket(self, bucket: str) -> None: ...
    def put_object(self, bucket, object_name, data, length, content_type=None): ...
    def get_object(self, bucket, object_name): ...
    def remove_object(self, bucket, object_name) -> None: ...
    def stat_object(self, bucket, object_name): ...
    def list_objects(self, bucket, prefix="", recursive=True): ...
    def presigned_get_object(self, bucket, object_name, expires=None) -> str: ...


def _split_endpoint(endpoint: str) -> tuple[str, bool | None]:
    raw = endpoint.strip()
    if raw.startswith("https://"):
        return raw[len("https://") :].rstrip("/"), True
    if raw.startswith("http://"):
        return raw[len("http://") :].rstrip("/"), False
    return raw.rstrip("/"), None


def connect_minio_client(
    *,
    endpoint: str,
    access_key: str,
    secret_key: str,
    secure: bool = False,
):
    host, scheme_secure = _split_endpoint(endpoint)
    if not host:
        raise RuntimeError("PIVOT_MINIO_ENDPOINT is required when PIVOT_OBJECT_STORE=minio")
    use_secure = scheme_secure if scheme_secure is not None else secure
    try:
        from minio import Minio
    except ImportError as exc:
        raise RuntimeError("minio extra is not installed; pip install -e ./api[minio]") from exc
    return Minio(host, access_key=access_key, secret_key=secret_key, secure=use_secure)


class MinioObjectStore:
    """ObjectStore that talks to an injected MinIO-compatible client."""

    def __init__(
        self,
        client: MinioClient,
        *,
        bucket: str,
        ensure_bucket: bool = False,
    ) -> None:
        if not bucket.strip():
            raise ValueError("bucket is required")
        self._client = client
        self._bucket = bucket
        if ensure_bucket and not client.bucket_exists(bucket):
            client.make_bucket(bucket)

    @classmethod
    def connect(
        cls,
        config: ObjectStoreConfig,
        *,
        access_key: str,
        secret_key: str,
        secure: bool = False,
        ensure_bucket: bool = False,
    ) -> "MinioObjectStore":
        client = connect_minio_client(
            endpoint=config.endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        return cls(client, bucket=config.bucket, ensure_bucket=ensure_bucket)

    def healthy(self) -> bool:
        try:
            return bool(self._client.bucket_exists(self._bucket))
        except Exception:
            return False

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        self._require_key(key)
        payload = data if isinstance(data, (bytes, bytearray)) else bytes(data)
        self._client.put_object(
            self._bucket,
            key,
            BytesIO(payload),
            len(payload),
            content_type=content_type,
        )

    def get(self, key: str) -> bytes | None:
        self._require_key(key)
        if not self.exists(key):
            return None
        response = self._client.get_object(self._bucket, key)
        try:
            return response.read()
        finally:
            close = getattr(response, "close", None)
            if close is not None:
                close()
            release = getattr(response, "release_conn", None)
            if release is not None:
                release()

    def exists(self, key: str) -> bool:
        self._require_key(key)
        try:
            self._client.stat_object(self._bucket, key)
            return True
        except Exception as exc:
            if _is_missing(exc):
                return False
            raise

    def delete(self, key: str) -> None:
        self._require_key(key)
        self._client.remove_object(self._bucket, key)

    def keys(self) -> tuple[str, ...]:
        names: list[str] = []
        for item in self._client.list_objects(self._bucket, recursive=True):
            name = getattr(item, "object_name", None)
            if isinstance(name, str) and name:
                names.append(name)
        return tuple(names)

    def presign(self, key: str, *, expires_seconds: int) -> str:
        self._require_key(key)
        if expires_seconds <= 0:
            raise ValueError("expires_seconds must be positive")
        return self._client.presigned_get_object(
            self._bucket,
            key,
            expires=timedelta(seconds=expires_seconds),
        )

    def _require_key(self, key: str) -> None:
        if not key or not str(key).strip():
            raise ValueError("object key must be non-empty")


def _is_missing(exc: BaseException) -> bool:
    if isinstance(exc, KeyError):
        return True
    text = str(exc)
    name = type(exc).__name__
    return name in {"S3Error", "NoSuchKey"} or "NoSuchKey" in text or "Not Found" in text
