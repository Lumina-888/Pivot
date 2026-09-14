"""Opt-in Playwright login through Next rewrite. Not GATE-P0-005 verified."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "playwright-login.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_RUNNER = _ROOT / "ops" / "run_playwright_login.py"
_GROUPED = _ROOT / "ops" / "run_grouped_tests.py"


def test_NFR_OBS_playwright_login_runner_is_opt_in():
    text = _RUNNER.read_text(encoding="utf-8")
    assert "PIVOT_REQUIRE_PLAYWRIGHT" in text
    assert "GATE" in text
    grouped = _GROUPED.read_text(encoding="utf-8")
    assert "PIVOT_REQUIRE_PLAYWRIGHT" not in grouped
    assert "uvicorn" in grouped.lower()
    assert "does not start" in grouped.lower() or "不启动" in grouped


def test_GATE_P0_005_not_verified_by_playwright_login():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-005" in evidence
    assert "unverified" in evidence.lower()
    assert "playwright" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-005" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")


def test_FR_AUTH_001_browser_login_reaches_home(browser_stack, browser_page):
    page = browser_page
    page.goto(f"{browser_stack.web_origin}/login")
    page.locator("#username").fill(browser_stack.username)
    page.locator("#password").fill(browser_stack.password)
    page.locator("button[type=submit]").click()
    page.get_by_role("heading", name="问枢 · 企业知识的轴心").wait_for()
    assert "/login" not in page.url
    assert page.get_by_role("button", name="退出登录").is_visible()


def test_FR_AUTH_002_browser_invalid_credentials_are_generic(browser_stack, browser_page):
    page = browser_page
    page.goto(f"{browser_stack.web_origin}/login")
    page.locator("#username").fill(browser_stack.username)
    page.locator("#password").fill("wrong-password")
    page.locator("button[type=submit]").click()
    page.get_by_text("账号或密码错误").wait_for()
    assert page.get_by_text("账号或密码错误").is_visible()
    assert page.url.endswith("/login")
    assert page.locator("#username").is_visible()
