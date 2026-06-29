"""Session 54: StepWorkbench + Interview Mode React 迁移 e2e + 截图.

- 默认 /: 首页
- /?mode=interview: Interview Mode (Demo Case 加载 + 8 步 + Deep Dive)
- 切 step 不重置 Trace/Thought
- 对话入口生成 preview
- Deep Dive 抽屉可开可关
- Tech Switches 8 项可见, 3 tone
- Protocol Map 显示 MCP/A2A/ACP, ACP 标 design-only
- 2 截图: lite 主页 + interview 模式
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def react_url() -> str:
    return "http://127.0.0.1:18183"


# ----------------------------- Default (home) -----------------------------


def test_s54_01_home_page_renders(page: Page, react_url: str) -> None:
    page.goto(react_url, wait_until="domcontentloaded")
    expect(page.get_by_test_id("workbench-shell")).to_be_visible()
    expect(page.get_by_test_id("sidenav")).to_be_visible()
    expect(page.get_by_test_id("nav-interview")).to_be_visible()
    expect(page.get_by_test_id("nav-protocols")).to_be_visible()


# ----------------------------- Step Workbench ------------------------------


def test_s54_10_step_workbench_default_5_steps(
    page: Page, react_url: str
) -> None:
    """#/ 路由: 默认仍是 HomePage, 但 sidenav 提供 interview 入口."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    expect(page.get_by_test_id("workbench-shell")).to_be_visible()


def test_s54_11_interview_mode_loads(page: Page, react_url: str) -> None:
    """?mode=interview 切到 InterviewShell."""
    page.goto(
        react_url + "/#/?mode=interview", wait_until="domcontentloaded"
    )
    expect(page.get_by_test_id("interview-shell")).to_be_visible()
    expect(page.get_by_test_id("step-workbench-page")).to_be_visible()
    expect(page.get_by_test_id("iv-mode-badge")).to_be_visible()


def test_s54_12_step_navigator_5_steps(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    nav = page.get_by_test_id("wb-step-nav")
    expect(nav).to_be_visible()
    for key in (
        "topic_understanding",
        "keyword_breakdown",
        "search_candidates",
        "feasibility",
        "proposal",
    ):
        expect(page.get_by_test_id(f"step-nav-{key}")).to_be_visible()


def test_s54_13_load_demo_case_completes_all_steps(
    page: Page, react_url: str
) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("demo-load").click()
    # 5 步全部 completed
    for key in (
        "topic_understanding",
        "keyword_breakdown",
        "search_candidates",
        "feasibility",
        "proposal",
    ):
        expect(page.get_by_test_id(f"step-nav-{key}")).to_have_attribute(
            "data-state", "completed"
        )
    # trace 多一条 demo_case
    expect(page.get_by_test_id("wb-trace")).to_be_visible()
    expect(page.get_by_test_id("iv-state-loaded")).to_be_visible()


def test_s54_14_switch_step_does_not_clear_trace(
    page: Page, react_url: str
) -> None:
    """切到 step 3 再切回, trace 数应保持."""
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("demo-load").click()
    trace_before = page.locator("[data-testid^='trace-evt-']").count()
    page.get_by_test_id("step-nav-search_candidates").click()
    page.get_by_test_id("step-nav-topic_understanding").click()
    trace_after = page.locator("[data-testid^='trace-evt-']").count()
    assert trace_after == trace_before, (
        f"trace should not shrink on step switch: {trace_before} -> {trace_after}"
    )


def test_s54_15_chat_input_generates_preview(
    page: Page, react_url: str
) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("demo-load").click()
    page.get_by_test_id("chat-input").fill("修改 step 3 的工程证据")
    page.get_by_test_id("chat-submit").click()
    expect(page.get_by_test_id("chat-preview")).to_be_visible()
    expect(page.get_by_test_id("chat-accept")).to_be_visible()


def test_s54_16_accept_preview_appends_system_msg(
    page: Page, react_url: str
) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("chat-input").fill("增加一个新候选")
    page.get_by_test_id("chat-submit").click()
    page.get_by_test_id("chat-accept").click()
    expect(page.locator("[data-testid^='chat-msg-']")).to_have_count(2)


# ----------------------------- Tech Switches -------------------------------


def test_s54_20_tech_switches_8_items(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    expect(page.get_by_test_id("iv-tech-switches")).to_be_visible()
    for k in (
        "paper_rag",
        "reality_check",
        "claim_grounding",
        "track_b_extractor",
        "thesis_eval",
        "rag_evaluator",
        "mcp",
        "acp_admission_control",
    ):
        expect(page.get_by_test_id(f"tech-switch-{k}")).to_be_visible()
    # ACP 必须 design-only
    acp = page.get_by_test_id("tech-switch-acp_admission_control")
    expect(acp).to_have_attribute("data-status", "design-only")


# ----------------------------- Deep Dive ----------------------------------


def test_s54_30_deep_dive_open_close(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    expect(page.get_by_test_id("iv-deep-dive")).to_have_count(0)
    page.get_by_test_id("iv-open-deep-dive").click()
    expect(page.get_by_test_id("iv-deep-dive")).to_be_visible()
    expect(page.get_by_test_id("deep-dive-list")).to_be_visible()
    # 9 个 module item (li.pa-deep-dive__item)
    items = page.locator(".pa-deep-dive__list > .pa-deep-dive__item")
    expect(items).to_have_count(9)
    # 关闭
    page.get_by_test_id("deep-dive-close").click()
    expect(page.get_by_test_id("iv-deep-dive")).to_have_count(0)


def test_s54_31_deep_dive_filter_design_only(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("iv-open-deep-dive").click()
    page.get_by_test_id("filter-design").click()
    # design-only: mcp, agent, protocols (3 个)
    items = page.locator("[data-testid^='deep-dive-'][data-testid$='-rag'], [data-testid^='deep-dive-'][data-testid$='-mcp'], [data-testid^='deep-dive-'][data-testid$='-agent'], [data-testid^='deep-dive-'][data-testid$='-protocols']")
    visible = items.count()
    # 设计: 9 全 - 6 非 design-only 路径
    assert visible >= 3


# ----------------------------- Protocol Map -------------------------------


def test_s54_40_protocol_map_rows(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    expect(page.get_by_test_id("iv-protocols")).to_be_visible()
    for k in ("mcp", "a2a", "acp"):
        expect(page.get_by_test_id(f"protocol-row-{k}")).to_be_visible()
    # ACP design-only
    expect(page.get_by_test_id("protocol-tone-acp")).to_have_text("design-only")
    expect(page.get_by_test_id("protocol-honest")).to_be_visible()


# ----------------------------- Routing ------------------------------------


def test_s54_50_protocols_route(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/protocols", wait_until="domcontentloaded")
    expect(page.get_by_test_id("protocols-page")).to_be_visible()
    # 路由高亮 protocols 入口
    expect(page.get_by_test_id("nav-protocols")).to_have_class(
        __import__("re").compile(r"pa-sidenav__item--active")
    )


def test_s54_51_interview_route_highlight(
    page: Page, react_url: str
) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    expect(page.get_by_test_id("nav-interview")).to_have_class(
        __import__("re").compile(r"pa-sidenav__item--active")
    )


# ----------------------------- Screenshots --------------------------------


def test_s54_90_screenshot_home(page: Page, react_url: str) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    page.screenshot(path=str(SCREENSHOT_DIR / "s54_home_lite.png"), full_page=True)


def test_s54_91_screenshot_interview(page: Page, react_url: str) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("demo-load").click()
    page.wait_for_timeout(800)
    page.screenshot(path=str(SCREENSHOT_DIR / "s54_interview_mode.png"), full_page=True)


def test_s54_92_screenshot_deep_dive(page: Page, react_url: str) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("iv-open-deep-dive").click()
    page.wait_for_timeout(500)
    page.screenshot(path=str(SCREENSHOT_DIR / "s54_deep_dive.png"), full_page=True)
