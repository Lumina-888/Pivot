from __future__ import annotations

from pathlib import Path

import pytest
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


def test_FR_DOC_006_worker_ingest_source_has_no_hardcoded_endpoints():
    text = _ASSEMBLY_SRC.read_text(encoding="utf-8").lower()
    assert "localhost" not in text
    assert "127.0.0.1" not in text
    assert "minio:9000" not in text
    assert "qdrant:6333" not in text
    assert "postgresql://" not in text
    assert "redis://" not in text
    assert "siliconflow" not in text
    assert "cosine" not in text
    assert "1024" not in text


def test_NFR_OBS_worker_process_assembles_ingest_runner():
    text = _MAIN.read_text(encoding="utf-8")
    assert "assemble_ingest_runtime" in text
    assert "start_celery_worker" in text
    assert "_unassembled_runner" not in text
