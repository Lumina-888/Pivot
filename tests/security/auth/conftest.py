from __future__ import annotations

import sys
from pathlib import Path

_UNIT_AUTH = Path(__file__).resolve().parents[2] / "unit" / "auth"
if str(_UNIT_AUTH) not in sys.path:
    sys.path.insert(0, str(_UNIT_AUTH))

pytest_plugins = ["auth_fixtures"]
