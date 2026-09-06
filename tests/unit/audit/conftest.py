from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3] / "api" / "src"
_EXPORT_FAKES = Path(__file__).resolve().parents[1] / "exports"
for path in (str(_SRC), str(_EXPORT_FAKES)):
    if path not in sys.path:
        sys.path.insert(0, path)

from fakes import ADMIN, ALICE, FakeClock  # noqa: E402
from pivot.audit.service import AuditService  # noqa: E402
from pivot.audit.store import AppendOnlyAuditStore  # noqa: E402


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def audit_service(clock):
    return AuditService(AppendOnlyAuditStore(), clock)


@pytest.fixture
def admin():
    return ADMIN


@pytest.fixture
def user():
    return ALICE
