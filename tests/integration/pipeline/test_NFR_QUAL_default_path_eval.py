"""NFR-QUAL: lock the measured Golden Set results of the default path.

The numbers asserted here are the ones recorded in
evidence/golden-set-eval/default-path-eval.md. Any change, improvement
or regression, must update the report and this test together.
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


def test_NFR_QUAL_synthetic_set_fully_passes_on_default_path():
    pytest.importorskip("llama_index.core")
    report = evaluate_default_path(load_dataset(), policy=_POLICY)
    assert report["case_count"] == 120
    assert report["passed_count"] == 120
    assert report["labeled_hit_rate"] == 1.0
    assert report["forbidden_leaks"] == 0
    assert report["gate"] == "unverified"


def test_NFR_QUAL_enterprise_set_measured_limits_on_default_path():
    pytest.importorskip("llama_index.core")
    report = evaluate_default_path(load_enterprise_dataset(), policy=_POLICY)
    assert report["case_count"] == 120
    assert report["labeled_hit_rate"] == 1.0
    # Content strata: every case passes, no forbidden chunk anywhere.
    for stratum in _CONTENT_STRATA:
        assert report["strata"][stratum]["passed"] == 12, stratum
    # Refusal strata are the recorded limitation of the retrieval layer:
    # no relevance floor exists (thresholds stay TBD-P0), so on realistic
    # text the retriever returns nearest neighbours instead of empty.
    assert report["strata"]["no_answer"]["passed"] == 0
    assert report["strata"]["unauthorized"]["passed"] == 0
    assert report["passed_count"] == 96
    assert report["forbidden_leaks"] == 10
    assert report["gate"] == "unverified"
