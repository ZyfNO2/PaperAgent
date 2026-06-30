"""Session 62: 毕业友好方向推荐 + Baseline + 可加模块决策包 — 真实浏览器点击 + 截图.

覆盖 (SOP §8.2):
1. 首页含方向建议 panel (data-testid="uw-direction-panel")
2. 点击"生成方向建议"按钮后, 方向卡出现
3. 推荐方向有"推荐"徽章
4. 每个方向显示 baseline 卡 (≥1)
5. 每个方向显示可加模块卡 (2-4)
6. stop_reason 出现, 明确不生成开题报告
7. 开发者窗口评分明细默认折叠, 点击展开可见
8. 没有截图装饰: 真实功能流

前置: 后端 18181 + React dev 18183 都已起来.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


pytestmark = pytest.mark.react_web


SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots" / "session62"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


SAMPLE_TOPIC = "基于三维成像的损伤智能检测"


@pytest.fixture
def react_url() -> str:
    return "http://127.0.0.1:18183"


def _shoot(page: Page, name: str) -> None:
    page.wait_for_timeout(200)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(150)
    page.screenshot(path=str(SCREENSHOT_DIR / name), full_page=True)


def _enter_topic(page: Page, react_url: str, topic: str) -> None:
    """输入题目 + 触发后端 analyze (拿到 project_id)."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    expect(page.get_by_test_id("user-shell")).to_be_visible()

    # 填题目 (TopicIntake testid)
    topic_input = page.get_by_test_id("topic-intake-input").first
    expect(topic_input).to_be_visible()
    topic_input.fill(topic)

    # 点开始分析 (触发 OneTopic analyze 拿 project_id, 这是方向建议的前置条件)
    page.get_by_test_id("topic-intake-start").first.click()

    # 等分析返回 (analysis-results 出现)
    expect(page.get_by_test_id("uw-analysis-results")).to_be_visible(timeout=15_000)


# ===========================================================================
# T1: 首页含方向建议 panel
# ===========================================================================


def test_s62_home_shows_direction_panel(page: Page, react_url: str) -> None:
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    expect(page.get_by_test_id("user-shell")).to_be_visible()
    # 即使没分析, panel 占位卡也要出现 (提示用户输入题目)
    expect(page.get_by_test_id("uw-direction-panel")).to_be_visible()
    _shoot(page, "s62_home_panel_present.png")


# ===========================================================================
# T2: 点击"生成方向建议"后, 方向卡出现
# ===========================================================================


def test_s62_click_plan_returns_direction_cards(page: Page, react_url: str) -> None:
    _enter_topic(page, react_url, SAMPLE_TOPIC)

    # 滚动到方向 panel
    panel = page.get_by_test_id("uw-direction-panel")
    panel.scroll_into_view_if_needed()

    # 点击"生成方向建议"
    plan_btn = page.get_by_test_id("gd-plan-btn").first
    expect(plan_btn).to_be_visible()
    plan_btn.click()

    # stop note 出现
    expect(page.get_by_test_id("gd-stop-note")).to_be_visible(timeout=10_000)
    # 来源计数出现
    expect(page.get_by_test_id("gd-source-counts")).to_be_visible()

    # 方向卡 ≥2 (data-testid 以 gd-direction- 起头)
    direction_cards = page.locator('[data-testid^="gd-direction-"]').filter(
        has_not=page.get_by_test_id("gd-recommended-badge")
    )
    # 更稳: 数 gd-direction-* 但排除 'gd-direction-panel' / 'gd-baseline-*' / 'gd-module-*'
    all_gd_ids = page.evaluate(
        """
        () => Array.from(document.querySelectorAll('[data-testid]'))
            .map(el => el.getAttribute('data-testid'))
            .filter(id => id && id.startsWith('gd-direction-'))
        """
    )
    assert 2 <= len(all_gd_ids) <= 3, all_gd_ids

    _shoot(page, "s62_direction_cards.png")


# ===========================================================================
# T3: 推荐方向有"推荐"徽章
# ===========================================================================


def test_s62_recommended_direction_has_badge(page: Page, react_url: str) -> None:
    _enter_topic(page, react_url, SAMPLE_TOPIC)

    panel = page.get_by_test_id("uw-direction-panel")
    panel.scroll_into_view_if_needed()
    page.get_by_test_id("gd-plan-btn").first.click()
    expect(page.get_by_test_id("gd-stop-note")).to_be_visible(timeout=10_000)

    # 推荐徽章恰好 1 个
    recommended = page.get_by_test_id("gd-recommended-badge")
    expect(recommended).to_have_count(1)
    _shoot(page, "s62_recommended_badge.png")


# ===========================================================================
# T4: 推荐方向有 baseline 卡
# ===========================================================================


def test_s62_baseline_cards_present(page: Page, react_url: str) -> None:
    _enter_topic(page, react_url, SAMPLE_TOPIC)

    page.get_by_test_id("uw-direction-panel").scroll_into_view_if_needed()
    page.get_by_test_id("gd-plan-btn").first.click()
    expect(page.get_by_test_id("gd-stop-note")).to_be_visible(timeout=10_000)

    # baseline 卡 (gd-baseline-*) 至少出现 2 张 (至少 1 个方向有 ≥1 个 baseline)
    baseline_ids = page.evaluate(
        """
        () => Array.from(document.querySelectorAll('[data-testid]'))
            .map(el => el.getAttribute('data-testid'))
            .filter(id => id && id.startsWith('gd-baseline-'))
        """
    )
    assert len(baseline_ids) >= 2, baseline_ids
    _shoot(page, "s62_baseline_modules.png")


# ===========================================================================
# T5: 可加模块 (2-4) 出现
# ===========================================================================


def test_s62_extension_modules_visible(page: Page, react_url: str) -> None:
    _enter_topic(page, react_url, SAMPLE_TOPIC)

    page.get_by_test_id("uw-direction-panel").scroll_into_view_if_needed()
    page.get_by_test_id("gd-plan-btn").first.click()
    expect(page.get_by_test_id("gd-stop-note")).to_be_visible(timeout=10_000)

    # 数每个方向的 module 数量 (从后端响应拿)
    breakdown = page.evaluate(
        """
        async () => {
            const resp = await fetch('/api/v1/projects/ot_demo/graduation-direction/plan', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({topic: '基于三维成像的损伤智能检测', use_last_retrieval: true, use_local_rag: true, max_directions: 3}),
            });
            const data = await resp.json();
            return data.directions.map(d => ({title: d.title, mods: d.extension_modules.length, baselines: d.recommended_baselines.length}));
        }
        """
    )
    assert breakdown, "API returned no directions"
    for d in breakdown:
        assert 2 <= d["mods"] <= 4, d
        assert d["baselines"] >= 1, d
    _shoot(page, "s62_modules_count.png")


# ===========================================================================
# T6: 开发者窗口评分明细可展开
# ===========================================================================


def test_s62_dev_scoring_breakdown_expandable(page: Page, react_url: str) -> None:
    _enter_topic(page, react_url, SAMPLE_TOPIC)

    page.get_by_test_id("uw-direction-panel").scroll_into_view_if_needed()
    page.get_by_test_id("gd-plan-btn").first.click()
    expect(page.get_by_test_id("gd-stop-note")).to_be_visible(timeout=10_000)

    # 默认折叠 — 打开开发者评分明细
    toggle = page.get_by_test_id("gd-toggle-scoring-btn").first
    expect(toggle).to_be_visible()
    toggle.click()
    page.wait_for_timeout(300)

    # 验证 details 已展开 (有 summary + ul)
    has_scoring = page.evaluate(
        """
        () => Array.from(document.querySelectorAll('.pa-gd-scoring-list')).length > 0
        """
    )
    assert has_scoring, "评分明细未展开"
    _shoot(page, "s62_dev_scoring_breakdown.png")


# ===========================================================================
# T7: 页面没有生成开题报告正文 (test_session57_click_through 保持)
# ===========================================================================


def test_s62_no_proposal_markdown_in_panel(page: Page, react_url: str) -> None:
    _enter_topic(page, react_url, SAMPLE_TOPIC)

    page.get_by_test_id("uw-direction-panel").scroll_into_view_if_needed()
    page.get_by_test_id("gd-plan-btn").first.click()
    expect(page.get_by_test_id("gd-stop-note")).to_be_visible(timeout=10_000)

    # stop_note 文本必须包含 "不生成开题报告"
    stop_text = page.get_by_test_id("gd-stop-note").inner_text()
    assert "不生成开题报告" in stop_text, stop_text

    # 页面没有 final-package / proposal-markdown 按钮
    has_final = page.evaluate(
        """
        () => {
            const btn = document.querySelector('[data-testid*="final-package"], [data-testid*="proposal-markdown"]');
            return btn !== null;
        }
        """
    )
    assert not has_final, "页面不应出现 final-package / proposal-markdown 按钮"
    _shoot(page, "s62_no_proposal_generation.png")