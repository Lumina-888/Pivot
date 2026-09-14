"""Opt-in Playwright coverage for SPEC's ten product pages. Not GATE-P0-005 verified."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_EVIDENCE = _ROOT / "evidence" / "wave3-m11" / "playwright-ten-pages.md"
_LIMITS = _ROOT / "evidence" / "wave2-m11" / "limits.md"
_RUNNER = _ROOT / "ops" / "run_playwright_login.py"
_GROUPED = _ROOT / "ops" / "run_grouped_tests.py"


def test_NFR_OBS_playwright_ten_pages_runner_is_opt_in():
    text = _RUNNER.read_text(encoding="utf-8")
    assert "PIVOT_REQUIRE_PLAYWRIGHT" in text
    assert "test_NFR_UX_browser_ten_pages.py" in text
    assert "GATE" in text
    grouped = _GROUPED.read_text(encoding="utf-8")
    assert "PIVOT_REQUIRE_PLAYWRIGHT" not in grouped
    assert "uvicorn" in grouped.lower()
    assert "does not start" in grouped.lower() or "不启动" in grouped


def test_GATE_P0_005_not_verified_by_playwright_ten_pages():
    evidence = _EVIDENCE.read_text(encoding="utf-8")
    assert "GATE-P0-005" in evidence
    assert "unverified" in evidence.lower()
    assert "十页" in evidence or "ten page" in evidence.lower()
    assert "playwright" in evidence.lower()
    limits = _LIMITS.read_text(encoding="utf-8")
    line = next(item for item in limits.splitlines() if "GATE-P0-005" in item)
    assert "unverified" in line.lower()
    assert "verified" not in line.lower().replace("unverified", "")


def _user_nav(page):
    return page.get_by_role("navigation", name="主导航")


def _admin_nav(page):
    return page.get_by_role("navigation", name="管理后台导航")


def _open_admin(page):
    page.get_by_role("link", name="管理后台").focus()
    page.keyboard.press("Enter")


def test_NFR_UX_browser_ten_pages_are_reachable(browser_stack, browser_page):
    page = browser_page
    page.goto(f"{browser_stack.web_origin}/login")
    page.get_by_text("企业文档智能问答系统 · 登录").wait_for()
    browser_stack.login(page)
    page.get_by_role("heading", name="问枢 · 企业知识的轴心").wait_for()

    _user_nav(page).get_by_role("link", name="知识库").click()
    page.get_by_role("heading", name="知识库").wait_for()

    page.get_by_role("link", name=browser_stack.document_title).click()
    page.get_by_role("heading", name=browser_stack.document_title).wait_for()
    page.get_by_text("文档详情").wait_for()

    _user_nav(page).get_by_role("link", name="对话").click()
    page.get_by_role("link", name="新建对话").wait_for()
    page.get_by_text("全局知识库").wait_for()

    _user_nav(page).get_by_role("link", name="首页").click()
    page.get_by_placeholder("搜索制度、手册、合同…").fill("年假")
    page.get_by_role("button", name="搜索").click()
    page.get_by_role("heading", name="全局搜索").wait_for()
    page.get_by_text("当前问题：年假").wait_for()

    _open_admin(page)
    page.get_by_role("heading", name="后台概览").wait_for()

    _admin_nav(page).get_by_role("link", name="文档管理").click()
    page.get_by_role("heading", name="文档管理").wait_for()

    _admin_nav(page).get_by_role("link", name="用户管理").click()
    page.get_by_role("heading", name="用户管理").wait_for()

    _admin_nav(page).get_by_role("link", name="审计日志").click()
    page.get_by_role("heading", name="审计日志").wait_for()


def test_FR_SEARCH_001_browser_library_search_and_document(browser_stack, browser_page):
    page = browser_page
    browser_stack.login(page)
    page.get_by_role("heading", name="问枢 · 企业知识的轴心").wait_for()
    _user_nav(page).get_by_role("link", name="知识库").click()
    page.get_by_role("heading", name="知识库").wait_for()
    page.get_by_role("link", name=browser_stack.document_title).click()
    page.get_by_role("heading", name=browser_stack.document_title).wait_for()
    page.get_by_text("文档详情").wait_for()
    _user_nav(page).get_by_role("link", name="首页").click()
    page.get_by_placeholder("搜索制度、手册、合同…").fill("年假")
    page.get_by_role("button", name="搜索").click()
    page.get_by_role("heading", name="全局搜索").wait_for()
    page.get_by_text("当前问题：年假").wait_for()
    assert "q=" in page.url


def test_FR_QA_001_browser_chat_keeps_question_and_document_scope(browser_stack, browser_page):
    page = browser_page
    browser_stack.login(page)
    page.get_by_role("heading", name="问枢 · 企业知识的轴心").wait_for()
    page.get_by_placeholder("搜索制度、手册、合同…").fill("年假能否跨年累计？")
    page.get_by_role("button", name="搜索").click()
    page.get_by_role("heading", name="全局搜索").wait_for()
    page.get_by_text("当前问题：年假能否跨年累计？").wait_for()
    page.get_by_role("link", name="直接问 AI").click()
    page.get_by_text("年假能否跨年累计？").wait_for()
    page.get_by_text("全局知识库").wait_for()
    _user_nav(page).get_by_role("link", name="知识库").click()
    page.get_by_role("link", name=browser_stack.document_title).click()
    page.get_by_role("link", name="仅针对本文提问").click()
    page.get_by_text("单文档 scope").wait_for()
    assert "scope=document" in page.url
    assert browser_stack.document_id in page.url


def test_FR_RBAC_001_browser_regular_user_admin_is_forbidden(browser_stack, browser_page):
    page = browser_page
    browser_stack.login(page, browser_stack.user_username, browser_stack.user_password)
    page.get_by_role("heading", name="问枢 · 企业知识的轴心").wait_for()
    _open_admin(page)
    _admin_nav(page).get_by_role("link", name="用户管理").click()
    page.get_by_text("无权限访问管理后台").wait_for()
    _admin_nav(page).get_by_role("link", name="审计日志").click()
    page.get_by_text("无权限访问管理后台").wait_for()
    assert page.get_by_role("heading", name="用户管理").count() == 0


def test_FR_DOC_006_browser_admin_docs_users_and_audit(browser_stack, browser_page):
    page = browser_page
    browser_stack.login(page)
    page.get_by_role("heading", name="问枢 · 企业知识的轴心").wait_for()
    _open_admin(page)
    _admin_nav(page).get_by_role("link", name="文档管理").click()
    page.get_by_role("heading", name="文档管理").wait_for()
    page.get_by_text(browser_stack.document_title).wait_for()
    _admin_nav(page).get_by_role("link", name="用户管理").click()
    page.get_by_role("heading", name="用户管理").wait_for()
    page.get_by_role("cell", name=browser_stack.username, exact=True).first.wait_for()
    page.get_by_role("cell", name=browser_stack.user_username, exact=True).wait_for()
    _admin_nav(page).get_by_role("link", name="审计日志").click()
    page.get_by_role("heading", name="审计日志").wait_for()
    page.get_by_text("只读查询").wait_for()
    page.get_by_text("Prompt/口令/思考链").wait_for()
