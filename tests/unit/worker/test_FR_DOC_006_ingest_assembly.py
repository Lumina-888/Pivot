from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pivot.parsing.fakes import ScriptedMinerUHttpClient
from pivot.parsing.mineru import MinerUCloudParser
from pivot_worker.assembly import IngestAssemblySettings, assemble_ingest_runtime

_ASSEMBLY_SRC = (
    Path(__file__).resolve().parents[3] / "worker" / "src" / "pivot_worker" / "assembly.py"
)
_MAIN = Path(__file__).resolve().parents[3] / "worker" / "src" / "pivot_worker" / "__main__.py"


def _settings(**overrides: object) -> IngestAssemblySettings:
    values: dict[str, object] = {
        "storage": "postgres",
        "database_url": "sqlite+pysqlite:///:memory:",
        "object_store": "minio",
        "minio_endpoint": "objects.test:443",
        "minio_bucket": "pivot-docs",
        "minio_access_key": "pivotminio",
        "minio_secret_key": "pivot_dev_only",
    }
    values.update(overrides)
    return IngestAssemblySettings(**values)


def test_FR_DOC_006_worker_ingest_rejects_memory_storage():
    with pytest.raises(RuntimeError, match="PIVOT_STORAGE=postgres"):
        assemble_ingest_runtime(_settings(storage="memory"))


def test_FR_DOC_006_worker_ingest_rejects_memory_object_store():
    with pytest.raises(RuntimeError, match="PIVOT_OBJECT_STORE=minio"):
        assemble_ingest_runtime(_settings(object_store="memory"))


def test_FR_DOC_006_worker_ingest_requires_database_url():
    with pytest.raises(RuntimeError, match="PIVOT_DATABASE_URL"):
        assemble_ingest_runtime(_settings(database_url=None))
    with pytest.raises(RuntimeError, match="PIVOT_DATABASE_URL"):
        IngestAssemblySettings.from_env(
            {
                "PIVOT_STORAGE": "postgres",
                "PIVOT_OBJECT_STORE": "minio",
                "PIVOT_MINIO_ENDPOINT": "objects.test:443",
                "PIVOT_MINIO_BUCKET": "pivot-docs",
                "PIVOT_MINIO_ACCESS_KEY": "pivotminio",
                "PIVOT_MINIO_SECRET_KEY": "pivot_dev_only",
            }
        )


def test_FR_DOC_006_worker_ingest_requires_minio_endpoint():
    with pytest.raises(RuntimeError, match="PIVOT_MINIO_ENDPOINT"):
        assemble_ingest_runtime(_settings(minio_endpoint=None))
    with pytest.raises(RuntimeError, match="PIVOT_MINIO_ENDPOINT"):
        IngestAssemblySettings.from_env(
            {
                "PIVOT_STORAGE": "postgres",
                "PIVOT_DATABASE_URL": "sqlite+pysqlite:///:memory:",
                "PIVOT_OBJECT_STORE": "minio",
                "PIVOT_MINIO_BUCKET": "pivot-docs",
                "PIVOT_MINIO_ACCESS_KEY": "pivotminio",
                "PIVOT_MINIO_SECRET_KEY": "pivot_dev_only",
            }
        )


def test_FR_DOC_006_worker_qdrant_publish_requires_endpoint():
    with pytest.raises(RuntimeError, match="PIVOT_QDRANT_ENDPOINT"):
        assemble_ingest_runtime(_settings(vector_store="qdrant"))
    with pytest.raises(RuntimeError, match="PIVOT_QDRANT_ENDPOINT"):
        IngestAssemblySettings.from_env(
            {
                "PIVOT_STORAGE": "postgres",
                "PIVOT_DATABASE_URL": "sqlite+pysqlite:///:memory:",
                "PIVOT_OBJECT_STORE": "minio",
                "PIVOT_MINIO_ENDPOINT": "objects.test:443",
                "PIVOT_MINIO_BUCKET": "pivot-docs",
                "PIVOT_MINIO_ACCESS_KEY": "pivotminio",
                "PIVOT_MINIO_SECRET_KEY": "pivot_dev_only",
                "PIVOT_VECTOR_STORE": "qdrant",
            }
        )


def test_FR_DOC_006_worker_qdrant_publish_requires_collection():
    with pytest.raises(RuntimeError, match="PIVOT_QDRANT_COLLECTION"):
        assemble_ingest_runtime(
            _settings(vector_store="qdrant", qdrant_endpoint="vectors.test:443")
        )


def test_FR_DOC_006_worker_qdrant_publish_requires_vector_size():
    with pytest.raises(RuntimeError, match="PIVOT_QDRANT_VECTOR_SIZE"):
        assemble_ingest_runtime(
            _settings(
                vector_store="qdrant",
                qdrant_endpoint="vectors.test:443",
                qdrant_collection="pivot-chunks",
            )
        )


def test_FR_DOC_006_worker_qdrant_publish_rejects_unsupported_store():
    with pytest.raises(RuntimeError, match="unsupported PIVOT_VECTOR_STORE"):
        assemble_ingest_runtime(_settings(vector_store="pinecone"))


def test_FR_DOC_006_worker_http_embedding_requires_qdrant():
    with pytest.raises(RuntimeError, match="PIVOT_VECTOR_STORE=qdrant"):
        _settings(
            embedding="http",
            embedding_endpoint="https://embed.test/v1/embeddings",
            embedding_model="injected-embed-model",
            embedding_api_key="secret-embed-key",
        )
    with pytest.raises(RuntimeError, match="PIVOT_VECTOR_STORE=qdrant"):
        IngestAssemblySettings.from_env(
            {
                "PIVOT_STORAGE": "postgres",
                "PIVOT_DATABASE_URL": "sqlite+pysqlite:///:memory:",
                "PIVOT_OBJECT_STORE": "minio",
                "PIVOT_MINIO_ENDPOINT": "objects.test:443",
                "PIVOT_MINIO_BUCKET": "pivot-docs",
                "PIVOT_MINIO_ACCESS_KEY": "pivotminio",
                "PIVOT_MINIO_SECRET_KEY": "pivot_dev_only",
                "PIVOT_EMBEDDING": "http",
                "PIVOT_EMBEDDING_ENDPOINT": "https://embed.test/v1/embeddings",
                "PIVOT_EMBEDDING_MODEL": "injected-embed-model",
                "PIVOT_EMBEDDING_API_KEY": "secret-embed-key",
            }
        )


def test_FR_DOC_006_worker_http_embedding_requires_endpoint():
    with pytest.raises(RuntimeError, match="PIVOT_EMBEDDING_ENDPOINT"):
        _settings(
            vector_store="qdrant",
            qdrant_endpoint="vectors.test:443",
            qdrant_collection="pivot-chunks",
            qdrant_vector_size=4,
            embedding="http",
        )
    with pytest.raises(RuntimeError, match="PIVOT_EMBEDDING_ENDPOINT"):
        IngestAssemblySettings.from_env(
            {
                "PIVOT_STORAGE": "postgres",
                "PIVOT_DATABASE_URL": "sqlite+pysqlite:///:memory:",
                "PIVOT_OBJECT_STORE": "minio",
                "PIVOT_MINIO_ENDPOINT": "objects.test:443",
                "PIVOT_MINIO_BUCKET": "pivot-docs",
                "PIVOT_MINIO_ACCESS_KEY": "pivotminio",
                "PIVOT_MINIO_SECRET_KEY": "pivot_dev_only",
                "PIVOT_VECTOR_STORE": "qdrant",
                "PIVOT_QDRANT_ENDPOINT": "vectors.test:443",
                "PIVOT_QDRANT_COLLECTION": "pivot-chunks",
                "PIVOT_QDRANT_VECTOR_SIZE": "4",
                "PIVOT_EMBEDDING": "http",
            }
        )


def test_FR_DOC_006_worker_http_embedding_rejects_unsupported():
    with pytest.raises(RuntimeError, match="unsupported PIVOT_EMBEDDING"):
        _settings(embedding="openai")


def test_FR_DOC_006_worker_mineru_requires_endpoint():
    with pytest.raises(RuntimeError, match="PIVOT_PARSER_ENDPOINT"):
        _settings(parser="mineru")
    with pytest.raises(RuntimeError, match="PIVOT_PARSER_ENDPOINT"):
        IngestAssemblySettings.from_env(
            {
                "PIVOT_STORAGE": "postgres",
                "PIVOT_DATABASE_URL": "sqlite+pysqlite:///:memory:",
                "PIVOT_OBJECT_STORE": "minio",
                "PIVOT_MINIO_ENDPOINT": "objects.test:443",
                "PIVOT_MINIO_BUCKET": "pivot-docs",
                "PIVOT_MINIO_ACCESS_KEY": "pivotminio",
                "PIVOT_MINIO_SECRET_KEY": "pivot_dev_only",
                "PIVOT_PARSER": "mineru",
            }
        )


def test_FR_DOC_006_worker_mineru_rejects_unsupported():
    with pytest.raises(RuntimeError, match="unsupported PIVOT_PARSER"):
        _settings(parser="pymupdf")


class _HealthyMinio:
    def bucket_exists(self, bucket: str) -> bool:
        del bucket
        return True

    def make_bucket(self, bucket: str) -> None:
        return None

    def put_object(self, bucket, object_name, data, length, content_type=None):
        return None

    def get_object(self, bucket, object_name):
        del bucket, object_name
        return SimpleNamespace(
            read=lambda *args: b"",
            close=lambda: None,
            release_conn=lambda: None,
        )

    def remove_object(self, bucket, object_name) -> None:
        return None

    def stat_object(self, bucket, object_name):
        return SimpleNamespace(size=0)

    def list_objects(self, bucket, prefix="", recursive=True):
        return []

    def presigned_get_object(self, bucket, object_name, expires=None) -> str:
        return f"https://objects.test/{bucket}/{object_name}"


def test_FR_DOC_006_worker_mineru_wires_parser():
    assembly = assemble_ingest_runtime(
        _settings(
            create_schema=True,
            minio_ensure_bucket=True,
            object_store_client=_HealthyMinio(),
            parser="mineru",
            parser_endpoint="https://parser.test/api/v4",
            parser_token="secret-mineru-token",
            parser_http_client=ScriptedMinerUHttpClient(),
        )
    )
    assert assembly.parsers is not None
    parser = assembly.parsers._parsers["pdf"]
    assert isinstance(parser, MinerUCloudParser)


def test_FR_DOC_006_worker_ingest_source_has_no_hardcoded_endpoints():
    text = _ASSEMBLY_SRC.read_text(encoding="utf-8").lower()
    assert "localhost" not in text
    assert "127.0.0.1" not in text
    assert "minio:9000" not in text
    assert "qdrant:6333" not in text
    assert "postgresql://" not in text
    assert "redis://" not in text
    assert "siliconflow" not in text
    assert "bge-m3" not in text
    assert "openai.com" not in text
    assert "cosine" not in text
    assert "1024" not in text
    assert "mineru.net" not in text


def test_NFR_OBS_worker_process_assembles_ingest_runner():
    text = _MAIN.read_text(encoding="utf-8")
    assert "assemble_ingest_runtime" in text
    assert "start_celery_worker" in text
    assert "_unassembled_runner" not in text
