#!/usr/bin/env python3
"""Golden Set evaluation entry. Default = synthetic Fake labels.

--enterprise loads the empty human schema and reports awaiting_annotation.
Does not mark GATE-P0 verified. Does not freeze NFR-QUAL thresholds.
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
    from golden_set import evaluate, load_dataset, load_enterprise_dataset
    from pivot.retrieval.policy import RetrievalPolicy

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--enterprise",
        action="store_true",
        help="load v0.3-enterprise (empty until annotated); not a GATE pass",
    )
    args = parser.parse_args()

    if args.enterprise:
        dataset = load_enterprise_dataset()
        report = evaluate(dataset)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("GATE-P0-002 unverified: enterprise set awaiting_annotation", file=sys.stderr)
        return 2

    # Default CI fixture remains retrieval/v0.2-synthetic.json via load_dataset().
    # Test-only sizes. Do not copy into SPEC or freeze TBD-P0.
    policy = RetrievalPolicy(dense_k=8, bm25_k=8, rrf_k=60, evidence_limit=5)
    report = evaluate(load_dataset(), policy=policy)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("GATE-P0-002 unverified: synthetic Fake KeywordRetriever", file=sys.stderr)
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
