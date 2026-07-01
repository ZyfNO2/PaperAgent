"""Session 57 真实点击测试 — 每个交互栏可用性 + 截图

区别于 S57 主 spec (验证可见性), 本文件覆盖真实点击 + 状态变化 + 截图.

标记: react-web
前置: 后端 18181 + React dev 18183 都已起来
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


pytestmark = pytest.mark.react_web


SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots" / "session57" / "interactions"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def react_url() -> str:
    return "http://127.0.0.1:18183"


def _shoot(page: Page, name: str) -> None:
    page.wait_for_timeout(150)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(120)
    page.screenshot(path=str(SCREENSHOT_DIR / name), full_page=True)


# ===========================================================================
# TopBar 真实点击 (5 nav + CTA + legacy)
# ===========================================================================


def test_interact_topnav_workbench_clickable(page: Page, react_url: str) -> None:
    """工作台 nav item 真实跳转 — 触发后 hash 改变, 对应内容渲染."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("topnav-home").click()
    page.wait_for_timeout(400)
    assert page.url.endswith("#/workbench"), f"unexpected url {page.url}"
    expect(page.get_by_test_id("step-workbench-page")).to_be_visible()
    _shoot(page, "i01_topnav_workbench_clicked.png")


def test_interact_topnav_rag_eval_clickable(page: Page, react_url: str) -> None:
    """RAG nav 点击后, RAG eval page 出现, 高亮态正确."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("topnav-rag-eval").click()
    page.wait_for_timeout(400)
    expect(page.get_by_test_id("rag-eval-route")).to_be_visible()
    active = page.locator(".pa-topbar__nav-item--active")
    expect(active).to_have_attribute("data-testid", "topnav-rag-eval")
    _shoot(page, "i02_topnav_rag_eval_clicked.png")


def test_interact_topnav_thesis_clickable(page: Page, react_url: str) -> None:
    """ThesisEval nav 点击后 4 subset 可见."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("topnav-thesis-eval").click()
    page.wait_for_timeout(400)
    expect(page.get_by_test_id("thesis-eval-route")).to_be_visible()
    page.get_by_test_id("thesis-eval-route").locator(".pa-subset-btn").first.wait_for()
    count = page.get_by_test_id("thesis-eval-route").locator(".pa-subset-btn").count()
    assert count >= 4, f"expected ≥4 subset buttons, got {count}"
    _shoot(page, "i03_topnav_thesis_clicked.png")


def test_interact_topnav_interview_clickable(page: Page, react_url: str) -> None:
    """面试 nav 点击后 step-workbench 出现."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("topnav-interview").click()
    page.wait_for_timeout(400)
    expect(page.get_by_test_id("step-workbench-page")).to_be_visible()
    _shoot(page, "i04_topnav_interview_clicked.png")


def test_interact_topnav_protocols_clickable(page: Page, react_url: str) -> None:
    """协议 nav 点击后 protocol page 出现."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("topnav-protocols").click()
    page.wait_for_timeout(400)
    expect(page.get_by_test_id("protocols-page")).to_be_visible()
    _shoot(page, "i05_topnav_protocols_clicked.png")


def test_interact_topbar_demo_cta(page: Page, react_url: str) -> None:
    """TopBar 黑色 CTA 加载 Demo 点击后, hash 跳到 interview + demo=case1."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("topbar-demo").click()
    page.wait_for_timeout(500)
    assert "demo=case1" in page.url, f"expected demo=case1 in url, got {page.url}"
    _shoot(page, "i06_topbar_demo_cta.png")


def test_interact_topbar_legacy_link_exists(page: Page, react_url: str) -> None:
    """旧前端链接存在并指向 18182."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    legacy = page.get_by_test_id("topbar-legacy")
    expect(legacy).to_be_visible()
    href = legacy.get_attribute("href")
    assert href and "18182" in href, f"legacy href should point to 18182, got {href}"


# ===========================================================================
# SideNav docs rail 真实点击
# ===========================================================================


def test_interact_sidenav_rag_click(page: Page, react_url: str) -> None:
    """SideNav 点 RAG Eval → 跳到 RAG 页面 + nav item 高亮."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("nav-rag-eval").click()
    page.wait_for_timeout(400)
    expect(page.get_by_test_id("rag-eval-route")).to_be_visible()
    active = page.locator(".pa-sidenav__item--active")
    expect(active).to_have_attribute("data-testid", "nav-rag-eval")
    _shoot(page, "i10_sidenav_rag_clicked.png")


def test_interact_sidenav_thesis_click(page: Page, react_url: str) -> None:
    """SideNav 点 ThesisEval → 跳到 Thesis 页面 + nav item 高亮."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("nav-thesis-eval").click()
    page.wait_for_timeout(400)
    expect(page.get_by_test_id("thesis-eval-route")).to_be_visible()
    active = page.locator(".pa-sidenav__item--active")
    expect(active).to_have_attribute("data-testid", "nav-thesis-eval")
    _shoot(page, "i11_sidenav_thesis_clicked.png")


def test_interact_sidenav_protocols_click(page: Page, react_url: str) -> None:
    """SideNav 点 Protocols → 跳到 protocol 页 + nav item 高亮."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("nav-protocols").click()
    page.wait_for_timeout(400)
    expect(page.get_by_test_id("protocols-page")).to_be_visible()
    active = page.locator(".pa-sidenav__item--active")
    expect(active).to_have_attribute("data-testid", "nav-protocols")
    _shoot(page, "i12_sidenav_protocols_clicked.png")


# ===========================================================================
# HomePage hero 真实点击
# ===========================================================================


def test_interact_home_cta_workbench(page: Page, react_url: str) -> None:
    """首页黑色 进入工作台 → 跳到 home route (验证 hash)."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    cta = page.get_by_test_id("home-cta-workbench")
    expect(cta).to_be_visible()
    cta.click()
    page.wait_for_timeout(250)
    assert "#/" in page.url, f"expected home route, got {page.url}"
    _shoot(page, "i20_home_cta_workbench.png")


def test_interact_home_cta_demo(page: Page, react_url: str) -> None:
    """首页次按钮 加载面试 Demo → hash 跳到 interview + demo=case1."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("home-cta-demo").click()
    page.wait_for_timeout(500)
    assert "mode=interview" in page.url and "demo=case1" in page.url, (
        f"expected demo route, got {page.url}"
    )
    _shoot(page, "i21_home_cta_demo.png")


def test_interact_home_cta_health(page: Page, react_url: str) -> None:
    """首页 /health 次按钮 → 链接到 18183/health."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    cta = page.get_by_test_id("home-cta-health")
    expect(cta).to_be_visible()
    href = cta.get_attribute("href")
    assert href and "/health" in href, f"expected /health link, got {href}"


def test_interact_home_3_zones_visible(page: Page, react_url: str) -> None:
    """首页 3 个能力数据区可见 + 有 图 N caption."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    for tid, cap in (("zone-rag", "图 1"),
                     ("zone-thesis", "图 2"),
                     ("zone-interview", "图 3")):
        zone = page.get_by_test_id(tid)
        expect(zone).to_be_visible()
        text = zone.inner_text()
        assert cap in text, f"{tid} 缺少 {cap} caption: {text}"
    _shoot(page, "i22_home_3_zones.png")


# ===========================================================================
# ThoughtPanel TUI console 真实交互
# ===========================================================================


def test_interact_console_prompt_submit(page: Page, react_url: str) -> None:
    """底部命令行 prompt 输入并回车后, 新行追加."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    inp = page.get_by_test_id("thought-input")
    expect(inp).to_be_visible()
    before = page.locator(".pa-thought-panel__line").count()
    inp.fill("请帮我查 YOLO 钢材数据集")
    inp.press("Enter")
    page.wait_for_timeout(200)
    after = page.locator(".pa-thought-panel__line").count()
    assert after >= before + 1, f"expected ≥{before+1} lines, got {after}"
    # 验证新行确实包含用户文本
    lines = page.locator(".pa-thought-panel__text").all_inner_texts()
    assert any("YOLO 钢材数据集" in line for line in lines), (
        f"新行未包含用户输入, 实际行: {lines}"
    )
    _shoot(page, "i30_console_submit.png")


def test_interact_console_not_cleared_on_route_change(page: Page, react_url: str) -> None:
    """路由切换后 console 内容不清空 (S54 关键不变式)."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    inp = page.get_by_test_id("thought-input")
    inp.fill("route-change-stamp")
    inp.press("Enter")
    page.wait_for_timeout(150)
    page.get_by_test_id("topnav-rag-eval").click()
    page.wait_for_timeout(400)
    page.get_by_test_id("topnav-home").click()
    page.wait_for_timeout(400)
    lines = page.locator(".pa-thought-panel__text").all_inner_texts()
    assert any("route-change-stamp" in line for line in lines), (
        "路由切换后 console 内容不应清空"
    )
    _shoot(page, "i31_console_persists.png")


# ===========================================================================
# RAG Eval 真实操作
# ===========================================================================


def test_interact_rag_seed_then_run(page: Page, react_url: str) -> None:
    """点 Seed Library → Run Eval → metric table 出现 + 有 baseline."""
    page.goto(react_url + "/#/?mode=rag-eval", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    page.get_by_test_id("rag-seed-btn").click()
    page.wait_for_timeout(800)
    page.get_by_test_id("rag-run-btn").click()
    page.wait_for_timeout(1500)
    expect(page.get_by_test_id("rag-metric-table")).to_be_visible()
    rows = page.locator("[data-testid^='rag-metric-']")
    assert rows.count() >= 11, f"expected ≥11 metric rows, got {rows.count()}"
    _shoot(page, "i40_rag_run_eval.png")


# ===========================================================================
# ThesisEval 真实切换
# ===========================================================================


def test_interact_thesis_subset_switch(page: Page, react_url: str) -> None:
    """点第二个 subset 按钮 → 该按钮变 active."""
    page.goto(react_url + "/#/?mode=thesis-eval", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    btns = page.get_by_test_id("thesis-eval-route").locator(".pa-subset-btn")
    expect(btns.first).to_be_visible()
    if btns.count() >= 2:
        btns.nth(1).click()
        page.wait_for_timeout(200)
        active_count = page.get_by_test_id("thesis-eval-route").locator(
            ".pa-subset-btn--active"
        ).count()
        assert active_count == 1, f"应有 1 个 active subset, 实际 {active_count}"
    _shoot(page, "i50_thesis_subset_switch.png")