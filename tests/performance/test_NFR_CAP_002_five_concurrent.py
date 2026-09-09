"""In-process 5-concurrent retrieval harness. GATE-P0-007 stays unverified."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from pivot.retrieval.fakes import KeywordRetriever
from pivot.retrieval.models import ChunkRecord, RetrievalQuery
from pivot.retrieval.policy import RetrievalPolicy
from pivot.retrieval.service import RetrievalService

_ROOT = Path(__file__).resolve().parents[2]
_OPS = str(_ROOT / "ops")
if _OPS not in sys.path:
    sys.path.insert(0, _OPS)
from fact_backup import synthetic_chunks  # noqa: E402

_PLAN = _ROOT / "tests" / "performance" / "PLAN.md"
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "capacity-backup.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"


def _records() -> tuple[ChunkRecord, ...]:
    return (
        ChunkRecord(
            chunk_id="chk_policy",
            version_id="ver_policy",
            document_id="doc_policy",
            text="late three times written warning. annual leave cannot carry over.",
            title="Attendance Policy",
            space="hr",
            ready=True,
            current=True,
            allowed=True,
            index_generation="gen_cap",
            embedding_model_version="fake-embed",
            retrieval_config_version="cap-injected",
        ),
    )


def _service(records: tuple[ChunkRecord, ...]) -> RetrievalService:
    return RetrievalService(
        corpus=records,
        dense=KeywordRetriever(records, "dense"),
        bm25=KeywordRetriever(records, "bm25"),
        policy=RetrievalPolicy(dense_k=4, bm25_k=4, rrf_k=4, evidence_limit=4),
    )


def test_NFR_CAP_002_five_concurrent_retrieves_complete():
    records = _records()
    query = RetrievalQuery(text="late three times", principal_id="usr_alice")
    n = 5
    barrier = Barrier(n)

    def _one(_: int):
        barrier.wait(timeout=5)
        return _service(records).retrieve(query)

    with ThreadPoolExecutor(max_workers=n) as pool:
        outcomes = list(pool.map(_one, range(n)))
    assert len(outcomes) == n
    assert all(item.status == "ok" for item in outcomes)
    assert all(item.evidence for item in outcomes)
    assert all(item.evidence[0].chunk_id == "chk_policy" for item in outcomes)


def test_NFR_CAP_002_does_not_freeze_latency():
    plan = _PLAN.read_text(encoding="utf-8")
    backup_src = (_ROOT / "ops" / "fact_backup.py").read_text(encoding="utf-8")
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "TBD-P0" in plan
    assert "P95" not in backup_src
    assert "P50" not in backup_src
    assert "不采集" in evidence or "TBD-P0" in evidence


def test_NFR_CAP_004_chunk_count_is_injected():
    chunks = synthetic_chunks(count=8, text="late three times")
    assert len(chunks) == 8
    assert all(item.ready and item.current and item.allowed for item in chunks)
    source = (_ROOT / "ops" / "fact_backup.py").read_text(encoding="utf-8")
    assert "100000" not in source
    assert "100_000" not in source


def test_GATE_P0_007_not_verified_by_five_concurrent_harness():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    plan = _PLAN.read_text(encoding="utf-8")
    limits = _LIMITS.read_text(encoding="utf-8")
    assert "GATE-P0-007" in evidence
    assert "unverified" in evidence.lower()
    assert "unverified" in plan.lower()
    line = next(item for item in limits.splitlines() if "GATE-P0-007" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")
