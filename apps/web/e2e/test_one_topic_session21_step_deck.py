"""Session 21: Step Deck UI (前端, 21-a) e2e.

覆盖 SOP §12 S21-PW-1/2/8/10 + 21-d 安全渲染降级:
1. Step Deck 页面可打开 (S21-PW-1)
2. 默认只显示一个主步骤卡 (S21-PW-2)
3. 左右 / 上下按钮可用 (S21-PW-8)
4. 证据抽屉可折叠
5. 渲染协议: paperagent-card / pa-card 白名单 (S21-PW-9)
6. 非法 render block 降级 (不执行 script)
7. S17 baseline 入口不回退 (S21-PW-10)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))


# ---------- helpers ---------- #


def _goto_step_deck(page):
    """点击 '📑 步骤流 (BETA)' tab, 等 page-step-deck 出现."""

    page.click("button.tab[data-tab='step-deck']")
    page.wait_for_selector("#page-step-deck:not([hidden])", timeout=15000)
    page.wait_for_function("window.StepDeckUI && window.StepDeckUI.isReady()", timeout=10000)


# ---------- S21-PW-1: Step Deck 页面可打开 ---------- #


def test_pw_01_step_deck_opens(page):
    """S21-PW-1: 切换到 Step Deck tab, 容器渲染, rail/card/drawer 都在."""

    _goto_step_deck(page)

    # 三个容器都存在且可见
    expect(page.locator("#step-deck-rail")).to_be_visible()
    expect(page.locator("#step-deck-card-wrap")).to_be_visible()
    expect(page.locator("#step-deck-drawer")).to_be_visible()

    # rail 至少渲染 9 步 (SOP §5.2)
    rail_items = page.locator("#step-deck-rail .step-rail__item")
    assert rail_items.count() == 9, f"期望 9 步, 实际 {rail_items.count()}"


# ---------- S21-PW-2: 默认只显示一个主步骤卡 ---------- #


def test_pw_02_default_one_step_visible(page):
    """S21-PW-2: 默认 input 步骤卡可见; 其他步骤在 rail 标记但不在主区."""

    _goto_step_deck(page)

    # 主卡当前显示 input
    card = page.locator("#step-deck-card-wrap")
    expect(card.locator(".step-deck__title")).to_contain_text("输入题目")

    # input 步骤只有一个 step-deck__body[data-step-key="input"]
    bodies = page.locator(".step-deck__body")
    assert bodies.count() == 1
    expect(bodies.first).to_have_attribute("data-step-key", "input")

    # 主卡只展示 input 内容 (不展示其他 step 的 body)
    assert page.locator("#step-deck-card-wrap .step-deck__body").count() == 1
    # rail 上 9 步均存在, 但当前 active 只有 input
    assert page.locator("#step-deck-rail .step-rail__item.is-current").count() == 1
    expect(page.locator("#step-deck-rail .step-rail__item.is-current")).to_have_attribute(
        "data-step-key", "input"
    )


# ---------- S21-PW-8: 上一步 / 下一步可用 ---------- #


def test_pw_03_prev_next_buttons_work(page):
    """S21-PW-8: 切到 input, 点下一步到 topic_understanding; 再上一步回 input."""

    _goto_step_deck(page)

    # 默认 input, 下一步可用, 上一步禁用
    expect(page.locator("#sd-btn-next")).to_be_enabled()
    expect(page.locator("#sd-btn-prev")).to_be_disabled()

    # 点下一步
    page.click("#sd-btn-next")
    page.wait_for_selector(".step-deck__body[data-step-key='topic_understanding']", state="attached", timeout=5000)

    # 上一步应可用
    expect(page.locator("#sd-btn-prev")).to_be_enabled()

    # 上一步
    page.click("#sd-btn-prev")
    page.wait_for_selector(".step-deck__body[data-step-key='input']", state="attached", timeout=5000)


# ---------- 抽屉可折叠 ---------- #


def test_pw_04_drawer_collapsible(page):
    """右上角 📂 抽屉 按钮可隐藏/显示 drawer."""

    _goto_step_deck(page)
    drawer = page.locator("#step-deck-drawer")
    expect(drawer).to_be_visible()

    page.click("#btn-sd-toggle-drawer")
    # 抽屉 should hide via class
    expect(drawer).to_have_class(__import__("re").compile(r"is-collapsed"))

    # 再点一次恢复
    page.click("#btn-sd-toggle-drawer")
    expect(drawer).not_to_have_class(__import__("re").compile(r"is-collapsed"))


# ---------- 渲染协议: paperagent-card / pa-card ---------- #


def test_pw_05_render_protocol_parses_paperagent_card(page):
    """RenderProtocol.parse 应能解析合法 paperagent-card."""

    rp = page.evaluate("""() => {
        const RP = window.RenderProtocol;
        if (!RP) return { ok: false, reason: 'no RP' };
        const text = '前缀正文\\n```paperagent-card\\n{ "component": "KeywordReviewCard", "props": { "keywords": [{"kind":"method","text":"YOLO"}] } }\\n```\\n后缀';
        const parsed = RP.parse(text);
        return { ok: true, blocks: parsed.blocks.length, hasValid: parsed.blocks.some(b => b.ok) };
    }""")
    assert rp["ok"], "RenderProtocol 未加载"
    assert rp["blocks"] >= 1
    assert rp["hasValid"], "应识别合法 paperagent-card"


def test_pw_06_render_protocol_parses_pa_card(page):
    """RenderProtocol.parse 应能解析 <pa-card> 标签."""

    result = page.evaluate("""() => {
        const RP = window.RenderProtocol;
        const text = '<pa-card type="TopicUnderstandingCard" id="t1">{"props":{"topic":"YOLO"}} </pa-card>';
        const parsed = RP.parse(text);
        return parsed.blocks.length;
    }""")
    assert result >= 1


def test_pw_07_render_protocol_rejects_unknown_component(page):
    """非法 component 应被降级 (返回 ok=false 但不抛异常)."""

    result = page.evaluate("""() => {
        const RP = window.RenderProtocol;
        const text = '```paperagent-card\\n{ "component": "ScriptExec", "props": {} }\\n```';
        const parsed = RP.parse(text);
        return parsed.blocks.map(b => ({ ok: b.ok, reason: b.reason }));
    }""")
    assert len(result) >= 1
    assert any(not b["ok"] for b in result), "非法 component 应被拒"
    assert any("白名单" in (b.get("reason") or "") for b in result)


def test_pw_08_render_protocol_blocks_script_tag(page):
    """S21-PW-9: 包含 <script> 的块应被拒."""

    result = page.evaluate("""() => {
        const RP = window.RenderProtocol;
        const text = '```paperagent-card\\n<scr' + 'ipt>alert(1)</scr' + 'ipt>\\n```';
        const parsed = RP.parse(text);
        return parsed.blocks.map(b => ({ ok: b.ok, reason: b.reason }));
    }""")
    assert len(result) >= 1
    assert any(not b["ok"] for b in result)


def test_pw_09_render_protocol_blocks_onclick(page):
    """onclick= 字符串应被拒."""

    result = page.evaluate("""() => {
        const RP = window.RenderProtocol;
        const text = '```paperagent-card\\n{ "component": "KeywordReviewCard", "props": { "onclick": "alert(1)" } }\\n```';
        const parsed = RP.parse(text);
        return parsed.blocks.map(b => ({ ok: b.ok, reason: b.reason }));
    }""")
    assert len(result) >= 1
    assert any(not b["ok"] for b in result)


# ---------- Mock 流式 + 关键词 Gate 暂停 ---------- #


def test_pw_10_mock_stream_pauses_at_keyword_review(page):
    """21-b + SOP §9: 点击开始流式后, 应在 keyword_review 自动暂停."""

    _goto_step_deck(page)
    page.click("#btn-sd-start-stream")

    # 等到 keyword_review 步骤并状态变为 awaiting_review
    page.wait_for_function(
        """() => {
            const rs = window.StepDeckUI && window.StepDeckUI.ui.runState;
            if (!rs) return false;
            const step = rs.steps['keyword_review'];
            return step && step.status === 'awaiting_review';
        }""",
        timeout=15000,
    )

    # 等 mock 流结束 (isStreaming=false)
    page.wait_for_function(
        "window.StepDeckUI && window.StepDeckUI.ui.runState.isStreaming === false",
        timeout=10000,
    )

    # 验证: 步骤栏 keyword_review 标记 awaiting_review
    rail_item = page.locator("#step-deck-rail .step-rail__item[data-step-key='keyword_review']")
    expect(rail_item).to_have_class(__import__("re").compile(r"awaiting_review"))

    # 主卡显示 KeywordReviewCard
    expect(page.locator(".pa-card--KeywordReviewCard")).to_be_visible()
    # 至少 5 个关键词
    kws = page.locator(".pa-card--KeywordReviewCard .pa-kw")
    assert kws.count() >= 5

    # 通过按钮可见
    expect(page.locator("button[data-gate-action='approve'][data-step-key='keyword_review']").first).to_be_visible()


def test_pw_11_keyword_approve_advances(page):
    """21-c 雏形: 关键词 Gate 通过后, 应自动推进到 query_plan."""

    _goto_step_deck(page)
    page.click("#btn-sd-start-stream")
    page.wait_for_function(
        """() => {
            const rs = window.StepDeckUI && window.StepDeckUI.ui.runState;
            const step = rs && rs.steps['keyword_review'];
            return step && step.status === 'awaiting_review';
        }""",
        timeout=15000,
    )

    # 点击通过
    page.click("button[data-gate-action='approve'][data-step-key='keyword_review']")
    page.wait_for_timeout(300)

    # 当前步骤推进到 query_plan
    rs = page.evaluate("window.StepDeckUI.ui.runState.currentStep")
    assert rs == "query_plan", f"通过后应推进到 query_plan, 实际 {rs}"


def test_pw_12_keyword_delete_one(page):
    """21-c 雏形: 关键词卡可删除一个, DOM 数量减少."""

    _goto_step_deck(page)
    page.click("#btn-sd-start-stream")
    page.wait_for_function(
        """() => {
            const rs = window.StepDeckUI && window.StepDeckUI.ui.runState;
            const step = rs && rs.steps['keyword_review'];
            return step && step.status === 'awaiting_review';
        }""",
        timeout=15000,
    )

    before = page.locator(".pa-card--KeywordReviewCard .pa-kw").count()
    # 删第一个
    page.locator(".pa-card--KeywordReviewCard .pa-kw__del").first.click()
    page.wait_for_timeout(150)
    after = page.locator(".pa-card--KeywordReviewCard .pa-kw").count()
    assert after == before - 1, f"删除后应少 1, before={before}, after={after}"


# ---------- S21-PW-10: 经典页入口未回退 ---------- #


def test_pw_13_classic_page_unchanged(page):
    """S21-PW-10: 切回 '一题分析' tab, 经典 6 块依然可用."""

    page.click("button.tab[data-tab='analyze']")
    page.wait_for_selector("#page-analyze:not([hidden])", timeout=5000)
    # 经典 result-grid 默认 hidden; input-card 可见
    expect(page.locator("#input-card")).to_be_visible()
    # Step Deck 容器已隐藏
    expect(page.locator("#page-step-deck")).to_be_hidden()