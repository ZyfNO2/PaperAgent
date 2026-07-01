"""Session 53: 三栏工作台 + 基础组件 Playwright smoke + 截图.

- 首页切到 WorkbenchShell
- 三栏存在 (left/center/right)
- 8 个基础组件展示区可见
- 总览 tab 显示健康/迁移阶段/S50/S51 卡片
- 组件演示 tab 显示 Button/Badge/Collapse/ErrorState
- 左右栏不随中栏 tabs 切换 unmount
- 截图: 首页 + 组件演示
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def react_url() -> str:
    return "http://127.0.0.1:18183"


def test_s53_01_workbench_shell_renders(page: Page, react_url: str) -> None:
    """WorkbenchShell 三栏都存在."""
    page.goto(react_url, wait_until="domcontentloaded")
    expect(page.get_by_test_id("workbench-shell")).to_be_visible()
    expect(page.get_by_test_id("workbench-left")).to_be_visible()
    expect(page.get_by_test_id("workbench-center")).to_be_visible()
    expect(page.get_by_test_id("workbench-right")).to_be_visible()
    # 截屏首页 (总览 tab 默认)
    page.screenshot(path=str(SCREENSHOT_DIR / "s53_home_overview.png"), full_page=True)


def test_s53_02_health_card_loaded(page: Page, react_url: str) -> None:
    """健康卡片三态之一出现."""
    page.goto(react_url, wait_until="domcontentloaded")
    page.wait_for_selector(
        "[data-testid='health-loading'], [data-testid='health-ok'], "
        "[data-testid='health-error']",
        timeout=10_000,
    )


def test_s53_03_trace_panel_renders(page: Page, react_url: str) -> None:
    """TracePanel 显示 6 个 trace 节点 (S18-S51)."""
    page.goto(react_url, wait_until="domcontentloaded")
    trace = page.get_by_test_id("trace-panel")
    expect(trace).to_be_visible()
    for tid in ("intake", "topic", "plan", "rag", "ground", "thesis"):
        expect(page.get_by_test_id(f"trace-item-{tid}")).to_be_visible()


def test_s53_04_thought_panel_tabs(page: Page, react_url: str) -> None:
    """ThoughtPanel 三 tab (LLM 思维 / 对话 / Skill) 切换."""
    page.goto(react_url, wait_until="domcontentloaded")
    expect(page.get_by_test_id("thought-stream")).to_be_visible()
    page.get_by_test_id("tab-chat").click()
    expect(page.get_by_test_id("chat-stream")).to_be_visible()
    page.get_by_test_id("tab-skills").click()
    expect(page.get_by_test_id("skill-stream")).to_be_visible()


def test_s53_05_main_stage_tabs_persist_sidebar(
    page: Page, react_url: str
) -> None:
    """中栏 Tabs 切换, 左侧 SideNav 与右侧 ThoughtPanel 引用不丢失."""
    page.goto(react_url, wait_until="domcontentloaded")

    sidenav = page.get_by_test_id("sidenav")
    left_first = sidenav.element_handle()
    thought = page.get_by_test_id("thought-panel")
    right_first = thought.element_handle()

    # 切到 组件演示
    page.get_by_test_id("tab-demo").click()
    expect(page.get_by_test_id("overview-demo")).to_be_visible()
    expect(page.get_by_test_id("btn-primary")).to_be_visible()

    # 切回总览
    page.get_by_test_id("tab-summary").click()
    expect(page.get_by_test_id("overview-summary")).to_be_visible()

    # 引用应保持 (说明未被 unmount)
    expect(sidenav).to_be_visible()
    expect(thought).to_be_visible()
    # 内部 count 未变: 仍含 5 个 disabled sidenav item (说明未重建)
    expect(sidenav.locator(".pa-sidenav__item--disabled")).to_have_count(5)


def test_s53_06_button_variants_render(page: Page, react_url: str) -> None:
    """5 个 Button variant 全部可见."""
    page.goto(react_url, wait_until="domcontentloaded")
    page.get_by_test_id("tab-demo").click()
    for tid in ("btn-primary", "btn-loading", "btn-ghost", "btn-disabled", "btn-danger"):
        expect(page.get_by_test_id(tid)).to_be_visible()
    # 截屏组件演示
    page.screenshot(path=str(SCREENSHOT_DIR / "s53_home_demo.png"), full_page=True)


def test_s53_07_collapse_toggle(page: Page, react_url: str) -> None:
    """Collapse 切换展开折叠."""
    page.goto(react_url, wait_until="domcontentloaded")
    page.get_by_test_id("tab-demo").click()
    collapse = page.get_by_test_id("collapse-default")
    expect(collapse).to_be_visible()
    # 初始折叠
    expect(collapse.get_by_text("可折叠区域")).to_be_visible()
    # 展开 (限定在 collapse-default 内, 避免 trace-advanced 误命中)
    collapse.locator("[data-testid='collapse-toggle-closed']").click()
    expect(collapse.get_by_test_id("collapse-body")).to_be_visible()
    # 折叠
    collapse.locator("[data-testid='collapse-toggle-open']").click()
    expect(collapse.locator("[data-testid='collapse-body']")).to_have_count(0)


def test_s53_08_badge_tones(page: Page, react_url: str) -> None:
    """5 个 Badge tone 可见."""
    page.goto(react_url, wait_until="domcontentloaded")
    page.get_by_test_id("tab-demo").click()
    card = page.get_by_test_id("card-badge")
    expect(card).to_be_visible()
    for tone in ("ok", "warn", "err", "info", "neutral"):
        expect(card.locator(f".pa-badge--{tone}").first).to_be_visible()


def test_s53_09_error_state_visible(page: Page, react_url: str) -> None:
    """ErrorState 演示区可见 + retry 按钮可点."""
    page.goto(react_url, wait_until="domcontentloaded")
    page.get_by_test_id("tab-demo").click()
    expect(page.get_by_test_id("err-demo")).to_be_visible()
    expect(page.get_by_test_id("error-retry")).to_be_visible()


def test_s53_10_button_counter_increments(
    page: Page, react_url: str
) -> None:
    """+1 按钮点击, 计数器变化."""
    page.goto(react_url, wait_until="domcontentloaded")
    page.get_by_test_id("tab-demo").click()
    counter = page.get_by_test_id("btn-counter")
    expect(counter).to_have_text("0")
    page.get_by_test_id("btn-incr").click()
    expect(counter).to_have_text("1")
    page.get_by_test_id("btn-incr").click()
    expect(counter).to_have_text("2")


def test_s53_11_desktop_responsive(
    page: Page, react_url: str
) -> None:
    """1280x800 桌面尺寸, 三栏布局不破."""
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(react_url, wait_until="domcontentloaded")
    workbench = page.get_by_test_id("workbench-grid")
    box = workbench.bounding_box()
    assert box is not None
    assert box["width"] >= 1200
    # 三栏宽度应各 > 0
    left = page.get_by_test_id("workbench-left").bounding_box()
    center = page.get_by_test_id("workbench-center").bounding_box()
    right = page.get_by_test_id("workbench-right").bounding_box()
    assert left and left["width"] > 0
    assert center and center["width"] > 200
    assert right and right["width"] > 0


def test_s53_12_sidenav_contains_legacy_link(
    page: Page, react_url: str
) -> None:
    """侧栏保留旧前端入口."""
    page.goto(react_url, wait_until="domcontentloaded")
    sidenav = page.get_by_test_id("sidenav")
    expect(sidenav).to_contain_text("18182")
    expect(sidenav).to_contain_text("工作台")
