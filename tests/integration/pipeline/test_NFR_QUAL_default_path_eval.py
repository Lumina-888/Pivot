"""NFR-QUAL: lock the measured Golden Set results of the default path.

The numbers asserted here are the ones recorded in
evidence/golden-set-eval/default-path-eval.md. Any change, improvement
or regression, must update the report and this test together.

The 2026-10-23 re-measurement follows the FR-RAG-009 dense-leg fix:
the original locks were measured with the dense leg silently down
(BM25 only). Controlled-embedding numbers only; production embedding
behavior is measured by the live runs of line three D.
"""

from __future__ import annotations

import pytest
from default_path_eval import evaluate_default_path
from golden_set import load_dataset, load_enterprise_dataset
from pivot.retrieval.policy import RetrievalPolicy

_POLICY = RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=60, evidence_limit=5)
_CONTENT_STRATA = (
    "fact",
    "parameter",
    "multi_span",
    "distractor",
    "document_scope",
    "parse_failure",
    "prompt_injection",
    "version_conflict",
)


def test_NFR_QUAL_synthetic_set_measured_on_default_path():
    pytest.importorskip("llama_index.core")
    report = evaluate_default_path(load_dataset(), policy=_POLICY)
    assert report["case_count"] == 120
    assert report["passed_count"] == 94
    assert report["labeled_hit_rate"] == 1.0
    assert report["forbidden_leaks"] == 2
    # Refusal strata fail exactly like the enterprise set: with the
    # dense leg live, nearest neighbours come back instead of empty.
    assert report["strata"]["no_answer"]["passed"] == 0
    assert report["strata"]["unauthorized"]["passed"] == 0
    assert report["strata"]["document_scope"]["passed"] == 10
    assert report["gate"] == "unverified"


def test_NFR_QUAL_enterprise_set_measured_limits_on_default_path():
    pytest.importorskip("llama_index.core")
    report = evaluate_default_path(load_enterprise_dataset(), policy=_POLICY)
    assert report["case_count"] == 120
    # Bow dense similarity is lexical overlap; on realistically
    # rewritten text it injects near-miss chunks into the fusion and
    # evicts labeled ones. These are the measured controlled-harness
    # limits, not production (bge-m3) behavior.
    assert report["labeled_hit_rate"] == 76 / 108
    expected_passed = {
        "fact": 7,
        "parameter": 6,
        "multi_span": 12,
        "distractor": 4,
        "document_scope": 12,
        "parse_failure": 12,
        "prompt_injection": 12,
        "version_conflict": 2,
    }
    for stratum in _CONTENT_STRATA:
        assert report["strata"][stratum]["passed"] == expected_passed[stratum], stratum
    # Refusal strata remain the recorded limitation of the retrieval
    # layer: no relevance floor exists yet (ADR-014 gate values stay
    # TBD-P0 until line-three D calibration).
    assert report["strata"]["no_answer"]["passed"] == 0
    assert report["strata"]["unauthorized"]["passed"] == 0
    assert report["passed_count"] == 67
    assert report["forbidden_leaks"] == 8
    assert report["gate"] == "unverified"
