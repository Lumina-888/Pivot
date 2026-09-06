from __future__ import annotations

from datetime import UTC, datetime

from pivot.retrieval.models import ChunkRecord

TRACE = {
    "index_generation": "gen_1",
    "embedding_model_version": "embed-v1",
    "retrieval_config_version": "retr-v1",
}


def chunk(**overrides) -> ChunkRecord:
    base = dict(
        chunk_id="chk_a",
        version_id="ver_a",
        document_id="doc_a",
        text="迟到三次以上记为旷工",
        title="考勤制度",
        space="hr",
        tags=("policy",),
        kind="pdf",
        ready=True,
        current=True,
        allowed=True,
        expired=False,
        deleted=False,
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        version_label="v1",
        **TRACE,
    )
    base.update(overrides)
    return ChunkRecord(**base)


def corpus() -> tuple[ChunkRecord, ...]:
    return (
        chunk(),
        chunk(
            chunk_id="chk_b",
            version_id="ver_b",
            document_id="doc_b",
            text="差旅报销需提供发票",
            title="报销制度",
            space="finance",
        ),
        chunk(
            chunk_id="chk_not_ready",
            version_id="ver_nr",
            document_id="doc_nr",
            text="迟到三次以上记为旷工 草稿",
            title="草稿",
            ready=False,
            current=False,
        ),
        chunk(
            chunk_id="chk_expired",
            version_id="ver_old",
            document_id="doc_old",
            text="迟到三次以上记为旷工 旧版",
            title="旧考勤",
            expired=True,
            current=False,
        ),
        chunk(
            chunk_id="chk_forbidden",
            version_id="ver_sec",
            document_id="doc_secret",
            text="迟到三次以上记为旷工 机密",
            title="机密",
            allowed=False,
        ),
        chunk(
            chunk_id="chk_a2",
            version_id="ver_a2",
            document_id="doc_a",
            text="迟到三次记书面警告",
            title="考勤制度",
            version_label="v2",
            current=True,
        ),
    )
