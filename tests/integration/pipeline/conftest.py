"""M11 pipeline tests: put api/src and worker/src on path. Do not insert unit fakes.py dirs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
for extra in (_ROOT / "api" / "src", _ROOT / "worker" / "src", Path(__file__).resolve().parent):
    path = str(extra)
    if path not in sys.path:
        sys.path.insert(0, path)


def _require_playwright() -> None:
    if os.environ.get("PIVOT_REQUIRE_PLAYWRIGHT") == "1":
        return
    pytest.skip("set PIVOT_REQUIRE_PLAYWRIGHT=1 to run browser login")


@pytest.fixture(scope="session")
def browser_stack():
    _require_playwright()
    from browser_login_support import start_browser_stack

    stack = start_browser_stack()
    try:
        yield stack
    finally:
        stack.close()


@pytest.fixture
def browser_page(browser_stack):
    page = browser_stack.new_page()
    try:
        yield page
    finally:
        page.close()
