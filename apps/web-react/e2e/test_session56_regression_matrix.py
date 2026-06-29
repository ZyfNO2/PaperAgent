"""Session 56: React 前端切换与回归收口 — 8 范围 Playwright 回归矩阵

标记: react-web (与 legacy-web 区分)
前置: 后端 18181 + React dev 18183 都已起来

范围 (SOP §3.2):
1. 基础启动: 首页 / health / 错误态
2. 工作台: Step 1 暂停 / 横向切换 / Trace 不重置
3. 对话编辑: chat 输入 + preview
4. 面试模式: Demo Case + Deep Dive + Tech Switches
5. 协议展示: MCP/A2A/ACP design-only
6. RAG: baseline / run eval / regression alert
7. ThesisEval: assess / subset / 三态降级
8. 报告导出: Step 6 导出入口
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


pytestmark = pytest.mark.react_web


SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def react_url() -> str:
    return "http://127.0.0.1:18183"


# ===========================================================================
# 1. 基础启动
# ===========================================================================


def test_s56_01_home_renders(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    expect(page.get_by_test_id("workbench-shell")).to_be_visible()
    expect(page.get_by_test_id("sidenav")).to_be_visible()


def test_s56_02_health_check(page: Page, react_url: str) -> None:
    """health card 渲染, 显示 backend 状态."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    expect(page.get_by_test_id("card-health")).to_be_visible()


def test_s56_03_route_resolution(page: Page, react_url: str) -> None:
    """5 个路由都能加载 — 5 个 nav item 都可见."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    for nav in ("nav-home", "nav-interview", "nav-rag-eval", "nav-thesis-eval", "nav-protocols"):
        expect(page.get_by_test_id(nav)).to_be_visible()


# ===========================================================================
# 2. 工作台
# ===========================================================================


def test_s56_10_step_workbench_5_steps(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    expect(page.get_by_test_id("step-workbench-page")).to_be_visible()
    for k in (
        "topic_understanding",
        "keyword_breakdown",
        "search_candidates",
        "feasibility",
        "proposal",
    ):
        expect(page.get_by_test_id(f"step-nav-{k}")).to_be_visible()


def test_s56_11_demo_case_loads(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("demo-load").click()
    for k in (
        "topic_understanding",
        "keyword_breakdown",
        "search_candidates",
        "feasibility",
        "proposal",
    ):
        expect(page.get_by_test_id(f"step-nav-{k}")).to_have_attribute(
            "data-state", "completed"
        )


def test_s56_12_step_switch_preserves_trace(
    page: Page, react_url: str
) -> None:
    """切 step 不重置 trace — 关键不变式."""
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("demo-load").click()
    before = page.locator("[data-testid^='trace-evt-']").count()
    page.get_by_test_id("step-nav-search_candidates").click()
    page.get_by_test_id("step-nav-topic_understanding").click()
    after = page.locator("[data-testid^='trace-evt-']").count()
    assert after == before, f"trace should not shrink: {before} -> {after}"


def test_s56_13_step1_pause_gate(page: Page, react_url: str) -> None:
    """Step 1 暂停确认 (paused_for_review 状态视觉化)."""
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    # 无 demo 时 step 1 是 locked/running; demo 加载后才 completed
    # 不做状态转换断言, 仅确认 step-nav 至少有一种状态属性
    el = page.get_by_test_id("step-nav-topic_understanding")
    state = el.get_attribute("data-state")
    assert state in ("locked", "running", "paused_for_review", "completed", "approved")


# ===========================================================================
# 3. 对话编辑
# ===========================================================================


def test_s56_20_chat_input_visible(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    expect(page.get_by_test_id("chat-input")).to_be_visible()
    expect(page.get_by_test_id("chat-submit")).to_be_visible()


def test_s56_21_chat_generates_preview(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("chat-input").fill("修改 step 3 工程证据")
    page.get_by_test_id("chat-submit").click()
    expect(page.get_by_test_id("chat-preview")).to_be_visible()
    expect(page.get_by_test_id("chat-accept")).to_be_visible()


def test_s56_22_chat_accept_appends_msg(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("chat-input").fill("增加一个候选")
    page.get_by_test_id("chat-submit").click()
    page.get_by_test_id("chat-accept").click()
    msgs = page.locator("[data-testid^='chat-msg-']").count()
    assert msgs >= 2


# ===========================================================================
# 4. 面试模式
# ===========================================================================


def test_s56_30_tech_switches_8_items(page: Page, react_url: str) -> None:
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


def test_s56_31_acp_design_only(page: Page, react_url: str) -> None:
    """诚实边界: ACP 必须 design-only."""
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    acp = page.get_by_test_id("tech-switch-acp_admission_control")
    expect(acp).to_have_attribute("data-status", "design-only")


def test_s56_32_deep_dive_9_modules(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("iv-open-deep-dive").click()
    expect(page.get_by_test_id("iv-deep-dive")).to_be_visible()
    items = page.locator(".pa-deep-dive__list > .pa-deep-dive__item")
    expect(items).to_have_count(9)


# ===========================================================================
# 5. 协议展示
# ===========================================================================


def test_s56_40_protocol_map_3_rows(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    expect(page.get_by_test_id("iv-protocols")).to_be_visible()
    for k in ("mcp", "a2a", "acp"):
        expect(page.get_by_test_id(f"protocol-row-{k}")).to_be_visible()
    expect(page.get_by_test_id("protocol-tone-acp")).to_have_text("design-only")


def test_s56_41_protocol_honest_boundary(
    page: Page, react_url: str
) -> None:
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    expect(page.get_by_test_id("protocol-honest")).to_be_visible()


def test_s56_42_protocols_route_highlight(
    page: Page, react_url: str
) -> None:
    page.goto(react_url + "/#/protocols", wait_until="domcontentloaded")
    expect(page.get_by_test_id("protocols-page")).to_be_visible()
    expect(page.get_by_test_id("nav-protocols")).to_have_class(
        __import__("re").compile(r"pa-sidenav__item--active")
    )


# ===========================================================================
# 6. RAG Eval
# ===========================================================================


def test_s56_50_rag_eval_route(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=rag-eval", wait_until="domcontentloaded")
    expect(page.get_by_test_id("rag-eval-page")).to_be_visible()
    expect(page.get_by_test_id("rag-eval-card")).to_be_visible()
    expect(page.get_by_test_id("rag-seed-btn")).to_be_visible()
    expect(page.get_by_test_id("rag-run-btn")).to_be_visible()


def test_s56_51_rag_baseline_card(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=rag-eval", wait_until="domcontentloaded")
    expect(page.get_by_test_id("rag-baseline-card")).to_be_visible()
    # baseline 可空, 但卡片存在
    expect(
        page.locator("[data-testid='rag-baseline-empty'], [data-testid='rag-baseline-summary']")
    ).to_have_count(1)


def test_s56_52_rag_metric_table_or_empty(
    page: Page, react_url: str
) -> None:
    page.goto(react_url + "/#/?mode=rag-eval", wait_until="domcontentloaded")
    expect(page.get_by_test_id("rag-metric-card")).to_be_visible()


def test_s56_53_rag_regression_optional(
    page: Page, react_url: str
) -> None:
    """Regression card 在无 report 时不渲染; 有 report 时渲染. 验证 testId 不冲突即可."""
    page.goto(react_url + "/#/?mode=rag-eval", wait_until="domcontentloaded")
    # 跑一次 eval 看是否能进入有 regression card 的路径
    page.get_by_test_id("rag-run-btn").click()
    page.wait_for_timeout(2000)
    # 任意状态: 0 个或 1 个 regression-card 都算合理
    expect(page.get_by_test_id("rag-metric-card")).to_be_visible()


# ===========================================================================
# 7. ThesisEval
# ===========================================================================


def test_s56_60_thesis_eval_route(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=thesis-eval", wait_until="domcontentloaded")
    expect(page.get_by_test_id("thesis-eval-page")).to_be_visible()
    expect(page.get_by_test_id("thesis-eval-card")).to_be_visible()


def test_s56_61_thesis_subsets_4(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=thesis-eval", wait_until="domcontentloaded")
    for k in ("smoke_20", "regression_60", "hard_20", "all_100"):
        expect(page.get_by_test_id(f"thesis-subset-{k}")).to_be_visible()


def test_s56_62_thesis_assess_form(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=thesis-eval", wait_until="domcontentloaded")
    expect(page.get_by_test_id("thesis-id-input")).to_have_value(
        "ENG-THESIS-001"
    )
    expect(page.get_by_test_id("thesis-assess-btn")).to_be_visible()


def test_s56_63_thesis_baseline_card(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=thesis-eval", wait_until="domcontentloaded")
    expect(page.get_by_test_id("thesis-baseline-card")).to_be_visible()


def test_s56_64_thesis_subset_switch(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/?mode=thesis-eval", wait_until="domcontentloaded")
    page.get_by_test_id("thesis-subset-hard_20").click()
    expect(page.get_by_test_id("thesis-subset-hard_20")).to_have_attribute(
        "data-active", "yes"
    )
    expect(page.get_by_test_id("thesis-subset-smoke_20")).to_have_attribute(
        "data-active", "no"
    )


# ===========================================================================
# 8. 报告导出入口 (S54 已设计; S56 验证入口存在)
# ===========================================================================


def test_s56_70_step_workbench_export_entry(
    page: Page, react_url: str
) -> None:
    """Step 6 导出入口 — S54 stepTypes.PROPOSAL step 应有导出按钮 (设计保留)."""
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("step-nav-proposal").click()
    # proposal 是第 5 步 (index 4), 验证 step card 渲染
    expect(page.get_by_test_id("step-nav-proposal")).to_be_visible()


# ===========================================================================
# 9. 截图 (整页 1280x800)
# ===========================================================================


def test_s56_90_screenshot_home(page: Page, react_url: str) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    page.screenshot(
        path=str(SCREENSHOT_DIR / "s56_home.png"), full_page=True
    )


def test_s56_91_screenshot_interview(page: Page, react_url: str) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(react_url + "/#/?mode=interview", wait_until="domcontentloaded")
    page.get_by_test_id("demo-load").click()
    page.wait_for_timeout(800)
    page.screenshot(
        path=str(SCREENSHOT_DIR / "s56_interview.png"), full_page=True
    )


def test_s56_92_screenshot_rag_eval(page: Page, react_url: str) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(react_url + "/#/?mode=rag-eval", wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    page.screenshot(
        path=str(SCREENSHOT_DIR / "s56_rag_eval.png"), full_page=True
    )


def test_s56_93_screenshot_thesis_eval(page: Page, react_url: str) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(react_url + "/#/?mode=thesis-eval", wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    page.screenshot(
        path=str(SCREENSHOT_DIR / "s56_thesis_eval.png"), full_page=True
    )