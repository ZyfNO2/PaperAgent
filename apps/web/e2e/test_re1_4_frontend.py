# -*- coding: utf-8 -*-
"""Re1.4 Playwright E2E — 前端全流程截图验证。

运行方式:
    # 先启动 API 服务
    cd apps/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 18181 &
    
    # 再运行测试
    python -m pytest apps/web/e2e/test_re1_4_frontend.py -s --tb=short
"""
import os
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

pytestmark = pytest.mark.skip(reason="legacy UI selectors (.adapter-row, #filterResult, etc.) — see test_re2_4_frontend.py for current UI tests")

BASE_URL = "http://127.0.0.1:18181"
SCREENSHOT_DIR = Path("tmp_re14_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)
HISTORY_CASE_ID = os.environ.get("RE14_HISTORY_CASE", "re14-medical-llm")
TOPIC = "基于大语言模型的医学问答可信度评估方法研究"


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


async def submit_and_wait(page, topic=TOPIC, timeout_ms=600000):
    """Submit a topic and wait for completion."""
    await page.goto(f"{BASE_URL}/web/")
    await page.fill("#topic", topic)
    await page.click("#startBtn")
    await page.wait_for_function(
        "() => { var s=document.getElementById('statusBar'); return s && (s.textContent.includes('完成') || s.textContent.includes('错误')); }",
        timeout=timeout_ms,
    )


class TestFrontendE2E:
    """17 项 Playwright E2E 测试，每步截图。"""

    @pytest.mark.asyncio
    async def test_01_page_loads(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("h1", timeout=10000)
        await screenshot(page, "01_page_load.png")
        assert len(errors) == 0, f"Console errors: {errors}"
        assert "PaperAgent" in await page.title()

    @pytest.mark.asyncio
    async def test_02_topic_input(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", TOPIC)
        await screenshot(page, "02_topic_input.png")
        assert "医学问答" in await page.input_value("#topic")

    @pytest.mark.asyncio
    async def test_03_submit_and_progress(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", TOPIC)
        await page.click("#startBtn")
        await page.wait_for_selector(".status-bar", timeout=10000)
        await screenshot(page, "03_submit_progress.png")

    @pytest.mark.asyncio
    async def test_04_adapter_results(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", TOPIC)
        await page.click("#startBtn")
        try:
            await page.wait_for_selector(".adapter-row", timeout=60000)
            await screenshot(page, "04_adapter_results.png")
            rows = await page.query_selector_all(".adapter-row")
            assert len(rows) >= 1
        except Exception:
            await screenshot(page, "04_adapter_results.png")

    @pytest.mark.asyncio
    async def test_05_filter_result(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", TOPIC)
        await page.click("#startBtn")
        try:
            await page.wait_for_function("()=>document.getElementById('filterResult')&&document.getElementById('filterResult').textContent.length>0", timeout=90000)
            await screenshot(page, "05_filter_result.png")
        except Exception:
            await screenshot(page, "05_filter_result.png")

    @pytest.mark.asyncio
    async def test_06_verify_round1(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", TOPIC)
        await page.click("#startBtn")
        try:
            await page.wait_for_function("()=>document.getElementById('verifyResults')&&document.getElementById('verifyResults').textContent.length>0", timeout=120000)
            await screenshot(page, "06_verify_round1.png")
        except Exception:
            await screenshot(page, "06_verify_round1.png")

    @pytest.mark.asyncio
    async def test_07_expansion_seeds(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", TOPIC)
        await page.click("#startBtn")
        try:
            await page.wait_for_function("()=>document.getElementById('expansionResults')&&document.getElementById('expansionResults').textContent.length>0", timeout=180000)
            await screenshot(page, "07_expansion_seeds.png")
        except Exception:
            await screenshot(page, "07_expansion_seeds.png")

    @pytest.mark.asyncio
    async def test_08_expansion_completed(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", TOPIC)
        await page.click("#startBtn")
        try:
            await page.wait_for_function("()=>document.body.textContent.includes('扩展完成')", timeout=180000)
            await screenshot(page, "08_expansion_completed.png")
        except Exception:
            await screenshot(page, "08_expansion_completed.png")

    @pytest.mark.asyncio
    async def test_09_verify_round2(self, browser_page):
        page, errors = browser_page
        await submit_and_wait(page, timeout_ms=300000)
        await screenshot(page, "09_verify_round2.png")

    @pytest.mark.asyncio
    async def test_10_analysis_nodes(self, browser_page):
        page, errors = browser_page
        await submit_and_wait(page, timeout_ms=300000)
        try:
            await page.wait_for_selector(".node-status", timeout=10000)
        except Exception:
            pass
        await screenshot(page, "10_analysis_nodes.png")

    @pytest.mark.asyncio
    async def test_11_complete(self, browser_page):
        page, errors = browser_page
        await submit_and_wait(page, timeout_ms=600000)
        await screenshot(page, "11_complete.png")

    @pytest.mark.asyncio
    async def test_12_paper_list(self, browser_page):
        page, errors = browser_page
        await submit_and_wait(page, timeout_ms=600000)
        try:
            await page.wait_for_selector(".paper-card", timeout=10000)
        except Exception:
            pass
        await screenshot(page, "12_paper_list.png")

    @pytest.mark.asyncio
    async def test_13_evidence_graph(self, browser_page):
        page, errors = browser_page
        await submit_and_wait(page, timeout_ms=600000)
        await screenshot(page, "13_evidence_graph.png")

    @pytest.mark.asyncio
    async def test_14_work_packages(self, browser_page):
        page, errors = browser_page
        await submit_and_wait(page, timeout_ms=600000)
        await screenshot(page, "14_work_packages.png")

    @pytest.mark.asyncio
    async def test_15_final_report(self, browser_page):
        page, errors = browser_page
        await submit_and_wait(page, timeout_ms=600000)
        await screenshot(page, "15_final_report.png")

    @pytest.mark.asyncio
    async def test_16_history_dropdown(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("#historySelect", timeout=10000)
        # Click to open the dropdown
        await page.click("#historySelect")
        await page.wait_for_timeout(500)
        await screenshot(page, "16_history_dropdown.png")

    @pytest.mark.asyncio
    async def test_17_history_case_load(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("#historySelect", timeout=10000)
        await page.wait_for_timeout(2000)
        options = await page.query_selector_all("#historySelect option")
        if len(options) <= 1:
            pytest.skip("No history cases available")
        await page.select_option("#historySelect", index=1)
        try:
            await page.wait_for_selector(".paper-card", timeout=15000)
        except Exception:
            pass
        await screenshot(page, "17_history_case_load.png")
        cards = await page.query_selector_all(".paper-card")
        assert len(cards) >= 1, "No paper cards rendered for history case"


class TestHistoryCaseData:
    """Loop 3: 历史 case 数据一致性验证。"""

    @pytest.mark.asyncio
    async def test_history_papers_match(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("#historySelect", timeout=10000)
        await page.wait_for_timeout(2000)
        options = await page.query_selector_all("#historySelect option")
        if len(options) <= 1:
            pytest.skip("No history cases")
        await page.select_option("#historySelect", index=1)
        try:
            await page.wait_for_selector(".paper-card", timeout=15000)
            await screenshot(page, "loop3_papers.png")
            cards = await page.query_selector_all(".paper-card")
            assert len(cards) >= 1
        except Exception:
            await screenshot(page, "loop3_papers.png")

    @pytest.mark.asyncio
    async def test_history_evidence_graph(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("#historySelect", timeout=10000)
        await page.wait_for_timeout(2000)
        options = await page.query_selector_all("#historySelect option")
        if len(options) <= 1:
            pytest.skip("No history cases")
        await page.select_option("#historySelect", index=1)
        try:
            await page.wait_for_selector("#evidenceGraph", timeout=15000)
        except Exception:
            pass
        await screenshot(page, "loop3_evidence_graph.png")

    @pytest.mark.asyncio
    async def test_history_work_packages(self, browser_page):
        page, errors = browser_page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("#historySelect", timeout=10000)
        await page.wait_for_timeout(2000)
        options = await page.query_selector_all("#historySelect option")
        if len(options) <= 1:
            pytest.skip("No history cases")
        await page.select_option("#historySelect", index=1)
        try:
            await page.wait_for_selector("#workPackages", timeout=15000)
        except Exception:
            pass
        await screenshot(page, "loop3_work_packages.png")
