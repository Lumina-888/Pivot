#!/usr/bin/env python3
"""Dual-path retrieval comparison entry (LlamaIndex integration L2).

Runs the synthetic Golden Set v0.2 through the native Golden Set wiring and
the LlamaIndex path, prints the comparison report as JSON, and exits 0 only
when the labeled expectations hold on both paths.
Does not mark GATE-P0 verified. Does not freeze NFR-QUAL thresholds.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "tests" / "integration" / "pipeline"
API_SRC = ROOT / "api" / "src"


def main() -> int:
    sys.path[:0] = [str(PIPELINE), str(API_SRC)]
    try:
        import llama_index.core  # noqa: F401
    except ImportError:
        print(
            "llama-index extra is not installed; pip install -e ./api[llama-index]",
            file=sys.stderr,
        )
        return 2
    from backend_compare import compare
    from golden_set import load_dataset
    from pivot.retrieval.policy import RetrievalPolicy

    # Test-only sizes. Do not copy into SPEC or freeze TBD-P0.
    policy = RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=60, evidence_limit=5)
    report = compare(load_dataset(), policy=policy)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        "GATE-P0-002 unverified: synthetic set, harness embedders on both paths",
        file=sys.stderr,
    )
    return 0 if not report["native_failed"] and not report["llama_failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
