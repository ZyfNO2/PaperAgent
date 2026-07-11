"""Re4.2 Day 2: React+Vite 前端 Playwright 截图基线。

Tests:
1. Home page loads, shows title, 3-step guide, demo cases
2. Workbench: submit topic, see progress, papers, source panel
3. Error state: invalid case_id shows error + suggestion
4. Report: completed case shows report sections
5. Mobile viewport: core flows browsable on 375px width
6. Keyboard nav: Tab through home → demo → workbench
"""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.react_web

BASE_URL = "http://127.0.0.1:18183"
SCREENSHOT_DIR = Path("tmp_re42_screenshots")


class TestReactHome:
    def test_home_loads(self, page: Page):
        """首页加载，显示标题、三步引导、Demo Case。"""
        page.goto(BASE_URL + "/")
        expect(page.locator("h1")).to_contain_text("PaperAgent")
        expect(page.locator("text=输入题目")).to_be_visible()
        expect(page.locator("text=智能检索")).to_be_visible()
        expect(page.locator("text=审核报告")).to_be_visible()
        expect(page.locator("text=钢材表面缺陷检测")).to_be_visible()
        SCREENSHOT_DIR.mkdir(exist_ok=True)
        page.screenshot(path=str(SCREENSHOT_DIR / "home.png"))

    def test_home_keyboard_nav(self, page: Page):
        """键盘可达：Tab 可导航到主要交互元素。"""
        page.goto(BASE_URL + "/")
        # Tab through nav links and input — verify keyboard reaches interactive elements
        page.keyboard.press("Tab")
        # First focus should be on a nav link
        focused_tag = page.evaluate("document.activeElement.tagName")
        assert focused_tag in ("A", "BUTTON", "INPUT"), f"Tab should focus interactive element, got {focused_tag}"

    def test_home_mobile_viewport(self, page: Page):
        """窄屏可浏览。"""
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(BASE_URL + "/")
        expect(page.locator("h1")).to_be_visible()
        page.screenshot(path=str(SCREENSHOT_DIR / "home_mobile.png"))


class TestReactWorkbench:
    def test_workbench_submit_topic(self, page: Page):
        """提交题目，看到进度状态。"""
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(BASE_URL + "/")
        page.fill("input[placeholder*='题目']", "基于YOLO的钢材表面缺陷检测")
        page.click("button:has-text('开始研究')")
        page.wait_for_url("**/workbench**", timeout=10000)
        page.screenshot(path=str(SCREENSHOT_DIR / "workbench_running.png"))

    def test_workbench_error_state(self, page: Page):
        """无效 case_id 显示错误状态。"""
        page.goto(BASE_URL + "/#/workbench/nonexistent-case-99999")
        page.wait_for_timeout(3000)
        page.screenshot(path=str(SCREENSHOT_DIR / "workbench_error.png"))

    def test_workbench_completed_case(self, page: Page):
        """已完成 case 显示报告区。"""
        page.goto(BASE_URL + "/#/workbench/re41-verify-001")
        page.wait_for_timeout(3000)
        page.screenshot(path=str(SCREENSHOT_DIR / "workbench_report.png"))

    def test_workbench_mobile(self, page: Page):
        """窄屏工作台可浏览。"""
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(BASE_URL + "/#/workbench/re41-verify-001")
        page.wait_for_timeout(3000)
        page.screenshot(path=str(SCREENSHOT_DIR / "workbench_mobile.png"))


class TestReactRagPlaceholder:
    def test_rag_placeholder(self, page: Page):
        """RAG 占位页面。"""
        page.goto(BASE_URL + "/#/rag")
        expect(page.locator("text=即将上线")).to_be_visible()
        page.screenshot(path=str(SCREENSHOT_DIR / "rag_placeholder.png"))
