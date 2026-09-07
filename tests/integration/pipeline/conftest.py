"""M11 pipeline tests: put api/src and worker/src on path. Do not insert unit fakes.py dirs."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
for extra in (_ROOT / "api" / "src", _ROOT / "worker" / "src", Path(__file__).resolve().parent):
    path = str(extra)
    if path not in sys.path:
        sys.path.insert(0, path)
