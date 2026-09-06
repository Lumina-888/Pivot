from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3] / "api" / "src"
_EXPORT_FAKES = Path(__file__).resolve().parents[2] / "unit" / "exports"
for path in (str(_SRC), str(_EXPORT_FAKES)):
    if path not in sys.path:
        sys.path.insert(0, path)

from fakes import build_harness  # noqa: E402


@pytest.fixture
def harness():
    return build_harness()
