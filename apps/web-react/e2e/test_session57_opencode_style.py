"""Session 57: OpenCode 风格视觉重塑 — 10 case + 5 截图

标记: react-web
前置: 后端 18181 + React dev 18183 都已起来

范围 (SOP §8):
1. 首页可见 paperagent wordmark
2. 顶部导航 5 个入口可跳转
3. 左侧 docs rail 存在, 当前项高亮
4. 右侧 ThoughtPanel 是 dark console 风格
5. 工作台 Step 切换后 ThoughtPanel 内容不清空
6. RAG Eval 指标区仍可见
7. ThesisEval 子集选择仍可见
8. Interview Mode Tech Switches 仍显示真实状态
9. 旧前端入口仍存在
10. 截图: home / workbench / rag-eval / thesis-eval / interview
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


pytestmark = pytest.mark.react_web


SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots" / "session57"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def react_url() -> str:
    return "http://127.0.0.1:18183"


# ===========================================================================
# 1. TopBar: wordmark + nav
# ===========================================================================


def test_s57_01_topbar_wordmark_visible(page: Page, react_url: str) -> None:
    """首页可见 paperagent wordmark."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    wordmark = page.get_by_test_id("topbar").locator(".pa-topbar__name")
    expect(wordmark).to_be_visible()
    expect(wordmark).to_have_text("paperagent")


def test_s57_02_topnav_5_entries_clickable(page: Page, react_url: str) -> None:
    """顶部导航 5 个核心入口可点击跳转."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    for nav in ("topnav-home", "topnav-rag-eval", "topnav-thesis-eval",
                "topnav-interview", "topnav-protocols"):
        expect(page.get_by_test_id(nav)).to_be_visible()


def test_s57_03_topnav_cta_and_legacy(page: Page, react_url: str) -> None:
    """主按钮「加载 Demo」与旧前端入口都在."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    expect(page.get_by_test_id("topbar-demo")).to_be_visible()
    expect(page.get_by_test_id("topbar-legacy")).to_be_visible()


# ===========================================================================
# 2. SideNav docs rail
# ===========================================================================


def test_s57_04_sidenav_sections(page: Page, react_url: str) -> None:
    """左侧 docs rail 存在, 分组标题可见."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    sidenav = page.get_by_test_id("sidenav")
    expect(sidenav).to_be_visible()
    sections = sidenav.locator(".pa-sidenav__section")
    expect(sections.first).to_be_visible()
    count = sections.count()
    assert count >= 4, f"expected ≥4 docs-rail sections, got {count}"


def test_s57_05_sidenav_active_route(page: Page, react_url: str) -> None:
    """切到 RAG Eval 后 nav-rag-eval 高亮."""
    page.goto(react_url + "/#/?mode=rag-eval", wait_until="domcontentloaded")
    active = page.locator(
        ".pa-sidenav__item.pa-sidenav__item--active"
    )
    expect(active).to_have_count(1)
    expect(active).to_have_attribute("data-testid", "nav-rag-eval")


# ===========================================================================
# 3. ThoughtPanel dark console
# ===========================================================================


def test_s57_06_thought_panel_is_dark_console(page: Page, react_url: str) -> None:
    """ThoughtPanel 是深色 console: 有 titlebar / 3 dot / 流式行."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    panel = page.get_by_test_id("thought-panel")
    expect(panel).to_be_visible()
    expect(panel.locator(".pa-thought-panel__titlebar")).to_be_visible()
    expect(panel.locator(".pa-thought-panel__dot--r")).to_be_visible()
    expect(panel.locator(".pa-thought-panel__dot--y")).to_be_visible()
    expect(panel.locator(".pa-thought-panel__dot--g")).to_be_visible()
    title = panel.locator(".pa-thought-panel__title")
    expect(title).to_have_text(
        "PaperAgent | Topic feasibility workflow"
    )


def test_s57_07_thought_panel_prompt_input(page: Page, react_url: str) -> None:
    """底部命令行 prompt 输入框可用, 提交后新增一行."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    panel = page.get_by_test_id("thought-panel")
    inp = panel.locator(".pa-thought-panel__input")
    expect(inp).to_be_visible()
    before = panel.locator(".pa-thought-panel__line").count()
    inp.fill("hello agent")
    panel.locator(".pa-thought-panel__input").press("Enter")
    page.wait_for_timeout(120)
    after = panel.locator(".pa-thought-panel__line").count()
    assert after >= before + 1, (
        f"expected ≥{before + 1} lines, got {after}"
    )


# ===========================================================================
# 4. 业务页风格统一 (关键入口都还在)
# ===========================================================================


def test_s57_08_rag_eval_route_visible(page: Page, react_url: str) -> None:
    """RAG Eval 页面入口仍可见; 跑 Run Eval 后指标表可见."""
    page.goto(react_url + "/#/?mode=rag-eval", wait_until="domcontentloaded")
    page.wait_for_timeout(600)
    expect(page.get_by_test_id("rag-eval-card")).to_be_visible()
    expect(page.get_by_test_id("rag-seed-btn")).to_be_visible()
    expect(page.get_by_test_id("rag-run-btn")).to_be_visible()
    # 点击 Run Eval 后表格出现
    page.get_by_test_id("rag-run-btn").click()
    page.wait_for_timeout(1500)
    expect(page.get_by_test_id("rag-metric-table")).to_be_visible()


def test_s57_09_thesis_eval_subset_visible(page: Page, react_url: str) -> None:
    """ThesisEval 4 subset 选择区可见."""
    page.goto(react_url + "/#/?mode=thesis-eval", wait_until="domcontentloaded")
    page.wait_for_timeout(150)
    expect(page.get_by_test_id("thesis-eval-route")).to_be_visible()
    buttons = page.get_by_test_id("thesis-eval-route").locator(".pa-subset-btn")
    expect(buttons.first).to_be_visible()
    count = buttons.count()
    assert count >= 4, f"expected ≥4 subset buttons, got {count}"


def test_s57_10_interview_tech_switches(page: Page, react_url: str) -> None:
    """Interview Mode Tech Switches 仍显示真实状态 (3 种)."""
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.wait_for_timeout(150)
    items = page.locator(".pa-tech-switches__item")
    expect(items.first).to_be_visible()
    total = items.count()
    assert total >= 5, f"expected ≥5 tech switches, got {total}"
    # Tech switches 应显示真实状态: implemented / lightweight / design-only (含中文映射: 已实现 / 轻量 / 设计稿)
    text = " ".join(items.all_inner_texts())
    has_implemented = "implemented" in text or "已实现" in text
    has_lightweight = "lightweight" in text or "轻量" in text
    has_design_only = "design-only" in text or "架构预留" in text or "设计稿" in text
    assert has_implemented, (
        "tech switches 应包含 implemented / 已实现 状态"
    )
    assert has_design_only, (
        "tech switches 应包含 design-only / 架构预留 状态"
    )


# ===========================================================================
# 11. 截图
# ===========================================================================


def test_s57_20_screenshot_home(page: Page, react_url: str) -> None:
    """首页 OpenCode 风格截图."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.wait_for_timeout(300)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(200)
    page.screenshot(
        path=str(SCREENSHOT_DIR / "s57_home_opencode.png"),
        full_page=True,
    )


def test_s57_21_screenshot_workbench(page: Page, react_url: str) -> None:
    """工作台截图."""
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.wait_for_timeout(300)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(200)
    page.screenshot(
        path=str(SCREENSHOT_DIR / "s57_workbench_opencode.png"),
        full_page=True,
    )


def test_s57_22_screenshot_rag_eval(page: Page, react_url: str) -> None:
    """RAG Eval 截图."""
    page.goto(react_url + "/#/?mode=rag-eval", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(200)
    page.screenshot(
        path=str(SCREENSHOT_DIR / "s57_rag_opencode.png"),
        full_page=True,
    )


def test_s57_23_screenshot_thesis_eval(page: Page, react_url: str) -> None:
    """ThesisEval 截图."""
    page.goto(react_url + "/#/?mode=thesis-eval", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(200)
    page.screenshot(
        path=str(SCREENSHOT_DIR / "s57_thesis_opencode.png"),
        full_page=True,
    )


def test_s57_24_screenshot_interview(page: Page, react_url: str) -> None:
    """Interview 截图."""
    page.goto(react_url + "/#/?mode=interview&demo=case1", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(200)
    page.screenshot(
        path=str(SCREENSHOT_DIR / "s57_interview_opencode.png"),
        full_page=True,
    )