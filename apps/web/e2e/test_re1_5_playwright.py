# -*- coding: utf-8 -*-
"""Re1.5 Playwright E2E — 前端全流程截图验证。

运行方式:
    # 先启动 API 服务
    cd G:\PaperAgent
    set FAST_JSON_PRIMARY=deepseek
    python -m uvicorn apps.api.app.main:app --host 0.0.0.0 --port 18182 --log-level warning

    # 再运行测试
    python -m pytest apps/web/e2e/test_re1_5_playwright.py -s --tb=short
"""
import os
import asyncio
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:18182"
SCREENSHOT_DIR = Path("tmp_re15_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

# Use a topic that's already been run in Phase 1 for history loading
HISTORY_CASE_ID = os.environ.get("RE15_HISTORY_CASE", "ENG-THESIS-074")
TOPIC = "基于深度学习的混凝土桥梁裂缝检测研究"


async def screenshot(page, name):
    """Take a full-page screenshot."""
    await page.screenshot(path=str(SCREENSHOT_DIR / name), full_page=True)


@pytest.fixture
async def browser_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN")
        page = await context.new_page()
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: errors.append(str(err)))
        yield page, errors
        await browser.close()


async def submit_and_wait(page, topic=TOPIC, timeout_ms=300000):
    """Submit a topic and wait for completion."""
    await page.goto(f"{BASE_URL}/web/")
    await page.fill("#topic", topic)
    await page.click("#startBtn")
    await page.wait_for_function(
        "() => { var s=document.getElementById('statusBar'); return s && (s.textContent.includes('完成') || s.textContent.includes('错误')); }",
        timeout=timeout_ms,
    )


class TestRe15Playwright:
    """10 Playwright tests for Re1.5 — page load, submit, wait, panels, history."""

    @pytest.mark.asyncio
    async def test_01_page_load(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("#topic", timeout=10000)
        await screenshot(page, "01_page_load.png")
        assert len(errors) == 0, f"Console errors: {errors}"

    @pytest.mark.asyncio
    async def test_02_topic_input(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", TOPIC)
        await screenshot(page, "02_topic_input.png")
        assert await page.input_value("#topic") == TOPIC

    @pytest.mark.asyncio
    async def test_03_submit(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", TOPIC)
        await page.click("#startBtn")
        # Wait for status bar to show something
        await page.wait_for_selector("#statusBar", timeout=10000)
        await screenshot(page, "03_submit.png")

    @pytest.mark.asyncio
    async def test_04_wait_complete(self, browser_page):
        page, errors = browser_page
        await submit_and_wait(page, TOPIC, timeout_ms=300000)
        await screenshot(page, "04_wait_complete.png")
        status = await page.text_content("#statusBar")
        assert "完成" in status or "错误" in status, f"Unexpected status: {status}"

    @pytest.mark.asyncio
    async def test_05_paper_list(self, browser_page):
        page, errors = browser_page
        await submit_and_wait(page, TOPIC, timeout_ms=300000)
        await screenshot(page, "05_paper_list.png")
        # Check paper cards exist
        cards = await page.query_selector_all(".paper-card")
        assert len(cards) > 0, "No paper cards found"

    @pytest.mark.asyncio
    async def test_06_evidence_graph(self, browser_page):
        page, errors = browser_page
        await submit_and_wait(page, TOPIC, timeout_ms=300000)
        await screenshot(page, "06_evidence_graph.png")
        eg = await page.query_selector("#evidenceGraph")
        assert eg is not None, "Evidence graph panel not found"

    @pytest.mark.asyncio
    async def test_07_work_packages(self, browser_page):
        page, errors = browser_page
        await submit_and_wait(page, TOPIC, timeout_ms=300000)
        await screenshot(page, "07_work_packages.png")
        wp = await page.query_selector("#workPackages")
        assert wp is not None, "Work packages panel not found"

    @pytest.mark.asyncio
    async def test_08_final_report(self, browser_page):
        page, errors = browser_page
        await submit_and_wait(page, TOPIC, timeout_ms=300000)
        await screenshot(page, "08_final_report.png")
        fr = await page.query_selector("#finalReport")
        assert fr is not None, "Final report panel not found"

    @pytest.mark.asyncio
    async def test_09_history_dropdown(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("#historySelect", timeout=10000)
        await page.click("#historySelect")
        await page.wait_for_timeout(500)
        await screenshot(page, "09_history_dropdown.png")
        # Check dropdown has options
        options = await page.query_selector_all("#historySelect option")
        assert len(options) > 0, "No history options found"

    @pytest.mark.asyncio
    async def test_10_history_load(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("#historySelect", timeout=10000)
        await page.click("#historySelect")
        await page.wait_for_timeout(500)
        # Select first available case
        options = await page.query_selector_all("#historySelect option")
        if len(options) > 1:
            val = await options[1].get_attribute("value")
            if val:
                await page.select_option("#historySelect", val)
                await page.wait_for_timeout(2000)
                await screenshot(page, "10_history_load.png")
                # Verify panels rendered
                cards = await page.query_selector_all(".paper-card")
                assert len(cards) > 0, "No paper cards after history load"
        else:
            await screenshot(page, "10_history_no_cases.png")
            pytest.skip("No history cases available")
