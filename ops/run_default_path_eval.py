#!/usr/bin/env python3
"""Golden Set evaluation of the default LlamaIndex retrieval path.

Default dataset is the synthetic v0.2 set; --enterprise loads the human
v0.3 desensitized set. Prints the JSON report. Exit code is 1 when any
case fails its expectation. Does not mark GATE-P0 verified and does not
freeze NFR-QUAL thresholds: policy sizes and the harness embedder are
test values.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "tests" / "integration" / "pipeline"
API_SRC = ROOT / "api" / "src"


def main() -> int:
    sys.path[:0] = [str(PIPELINE), str(API_SRC)]
    try:
        from default_path_eval import evaluate_default_path
        from golden_set import load_dataset, load_enterprise_dataset
        from pivot.retrieval.policy import RetrievalPolicy
    except ImportError as exc:
        print(f"missing dependency: {exc}", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--enterprise",
        action="store_true",
        help="evaluate the human v0.3 desensitized set instead of synthetic v0.2",
    )
    args = parser.parse_args()

    dataset = load_enterprise_dataset() if args.enterprise else load_dataset()
    # Test-only sizes. Do not copy into SPEC or freeze TBD-P0.
    policy = RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=60, evidence_limit=5)
    report = evaluate_default_path(dataset, policy=policy)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        "GATE-P0-002 unverified: controlled harness embedder, test policy values",
        file=sys.stderr,
    )
    return 0 if report["passed_count"] == report["case_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
