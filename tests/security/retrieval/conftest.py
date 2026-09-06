from __future__ import annotations

import sys
from pathlib import Path

_UNIT = Path(__file__).resolve().parents[2] / "unit" / "retrieval"
if str(_UNIT) not in sys.path:
    sys.path.insert(0, str(_UNIT))

pytest_plugins = ["retrieval_fixtures"]
