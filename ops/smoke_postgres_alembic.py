#!/usr/bin/env python3
"""Opt-in Alembic smoke against local Compose Postgres.

Does not start Compose, FastAPI, or Celery, and does not mark GATE-P0 verified.
Requires a reachable postgres on 127.0.0.1:5432 and `pip install -e ./api[postgres]`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    env = os.environ.copy()
    env["PIVOT_REQUIRE_COMPOSE"] = "1"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/integration/pipeline/test_M03_postgres_compose.py",
    ]
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
