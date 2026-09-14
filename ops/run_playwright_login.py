#!/usr/bin/env python3
"""Opt-in Playwright login and ten product pages through Next rewrite + composition root.

Does not start Compose. Starts local uvicorn/Next only when this script is run.
Does not mark GATE-P0 verified.
Requires: pip install -e ./api[http,playwright] && playwright install chromium
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "api" / "src"


def main() -> int:
    env = os.environ.copy()
    env["PIVOT_REQUIRE_PLAYWRIGHT"] = "1"
    pythonpath = os.pathsep.join([str(API_SRC), env.get("PYTHONPATH", "")]).strip(os.pathsep)
    env["PYTHONPATH"] = pythonpath
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/integration/pipeline/test_FR_AUTH_001_browser_login.py",
        "tests/integration/pipeline/test_NFR_UX_browser_ten_pages.py",
    ]
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
