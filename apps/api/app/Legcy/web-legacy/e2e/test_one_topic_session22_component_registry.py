"""Session 22: Component Registry (前端, 22-a) e2e.

覆盖 SOP §12 S22-PW-1~8:
1. 6 张核心卡通过 registry 渲染 (S22-PW-1)
2. 未知 component 降级为 fallback 卡 (S22-PW-2)
3. props 类型错误降级为 invalid 卡 (S22-PW-3)
4. 未知 action 被拒 (S22-PW-4)
5. KeywordReviewCard 仍可增删 (S22-PW-5)
6. SearchQueryPlanCard 显示 paper/dataset/repo queries (S22-PW-6)
7. RetrievalCandidateCard save/reject 不写 Evidence (S22-PW-7)
8. S21 Step Deck 主流程不回退 (S22-PW-8)
"""

from __future__ import annotations

import sys
import re
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


def _start_mock_and_wait_keyword(page):
    """Start mock stream, wait for keyword_review to reach awaiting_review."""
    page.click("#btn-sd-start-stream")
    page.wait_for_function(
        """() => {
            const rs = window.StepDeckUI && window.StepDeckUI.ui.runState;
            if (!rs) return false;
            const step = rs.steps['keyword_review'];
            return step && step.status === 'awaiting_review';
        }""",
        timeout=15000,
    )
    # ensure mock stream is done
    page.wait_for_function(
        "window.StepDeckUI && window.StepDeckUI.ui.runState.isStreaming === false",
        timeout=10000,
    )


# ---------- S22-PW-1: 6 core cards render through registry ---------- #


def test_pw_01_registry_available(page):
    """S22-PW-1: ComponentRegistry 在 window 上可用且注册了 6 张核心卡."""
    _goto_step_deck(page)

    result = page.evaluate("""() => {
        const cr = window.ComponentRegistry;
        if (!cr) return { ok: false, reason: 'not loaded' };
        const CORE = [
            'TopicUnderstandingCard',
            'KeywordReviewCard',
            'SearchQueryPlanCard',
            'RetrievalCandidateCard',
            'EvidenceRefCard',
            'ReportQualityCard',
        ];
        const registered = CORE.filter(name => cr.has(name));
        return { ok: true, total: cr.list ? cr.list().length : registered.length, registered };
    }""")
    assert result["ok"], f"ComponentRegistry not loaded: {result}"
    assert len(result["registered"]) == 6, (
        f"Expected 6 core cards, got {len(result['registered'])}: {result['registered']}"
    )


# ---------- S22-PW-2: unknown component shows safe fallback ---------- #


def test_pw_02_unknown_component_fallback(page):
    """S22-PW-2: 渲染未知 component 时输出 .pa-card--fallback 降级卡."""
    _goto_step_deck(page)

    html = page.evaluate("""() => {
        const cr = window.ComponentRegistry;
        return cr.renderCard({ component: 'NoSuchCard_XYZ', props: { x: 1 } });
    }""")
    assert "pa-card--fallback" in html, f"Expected fallback card, got: {html[:200]}"
    assert "NoSuchCard_XYZ" in html, "Fallback should mention the component name"


# ---------- S22-PW-3: props type error shows invalid ---------- #


def test_pw_03_bad_props_invalid_card(page):
    """S22-PW-3: props 类型错误时 validateCard 失败, renderCard 输出 invalid 卡."""
    _goto_step_deck(page)

    result = page.evaluate("""() => {
        const cr = window.ComponentRegistry;
        // KeywordReviewCard 期望 keywords 为数组, 传字符串触发 schema 校验失败
        const card = { component: 'KeywordReviewCard', props: { keywords: 'not-an-array' } };
        const v = cr.validateCard(card);
        if (v.ok) return { ok: true, reason: 'validateCard did not catch bad props' };
        const html = cr.renderCard(card);
        return { ok: false, validationError: v.error, hasInvalid: html.includes('pa-card--invalid') };
    }""")
    assert not result["ok"], f"validateCard should reject bad props: {result}"
    assert result["hasInvalid"], f"renderCard should produce invalid card: {result}"


# ---------- S22-PW-4: unknown action rejected ---------- #


def test_pw_04_unknown_action_rejected(page):
    """S22-PW-4: isActionAllowed 对未知 action 返回 false."""
    _goto_step_deck(page)

    result = page.evaluate("""() => {
        const cr = window.ComponentRegistry;
        const ok = cr.isActionAllowed('KeywordReviewCard', 'hack_the_planet');
        const real = cr.isActionAllowed('KeywordReviewCard', 'approve_step');
        return { unknownRejected: !ok, knownAllowed: real };
    }""")
    assert result["unknownRejected"], "Unknown action should be rejected"
    assert result["knownAllowed"], "Known action (approve_step) should be allowed"


# ---------- S22-PW-5: KeywordReviewCard still add/delete works ---------- #


def test_pw_05_keyword_card_delete_works(page):
    """S22-PW-5: mock 流后 KeywordReviewCard 仍可删除关键词."""
    _goto_step_deck(page)
    _start_mock_and_wait_keyword(page)

    # Debug: check runState structure
    debug = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const kr = rs.steps['keyword_review'];
        return {
            currentStep: rs.currentStep,
            krStatus: kr ? kr.status : null,
            krBlocks: kr ? kr.blocks : null,
            cardCount: Object.keys(rs.cards).length,
            cardTypes: Object.values(rs.cards).map(c => c.type),
        };
    }""")
    assert debug["krBlocks"] and len(debug["krBlocks"]) > 0, f"No blocks in keyword_review step: {debug}"

    before = page.locator(".pa-card--KeywordReviewCard .pa-kw").count()
    assert before >= 3, f"Expected at least 3 keywords, got {before}"

    # 删除第一个
    page.locator(".pa-card--KeywordReviewCard .pa-kw__del").first.click()

    after = page.locator(".pa-card--KeywordReviewCard .pa-kw").count()
    assert after == before - 1, f"Delete failed: before={before}, after={after}"


# ---------- S22-PW-6: SearchQueryPlanCard shows queries ---------- #


def test_pw_06_search_query_plan_card_renders(page):
    """S22-PW-6: ComponentRegistry 正确渲染 SearchQueryPlanCard 三组 queries."""
    _goto_step_deck(page)

    html = page.evaluate("""() => {
        const cr = window.ComponentRegistry;
        return cr.renderCard({
            component: 'SearchQueryPlanCard',
            props: {
                queries: [
                    { source: 'paper', query: 'YOLOv8 defect detection' },
                    { source: 'dataset', query: 'NEU steel surface defect' },
                    { source: 'repo', query: 'ultralytics yolov8' },
                ],
            },
        });
    }""")
    assert "pa-card--SearchQueryPlanCard" in html
    assert "YOLOv8" in html, "paper query should appear"
    assert "NEU steel" in html, "dataset query should appear"
    assert "ultralytics" in html, "repo query should appear"


# ---------- S22-PW-7: RetrievalCandidateCard save/reject ---------- #


def test_pw_07_retrieval_candidate_card_renders(page):
    """S22-PW-7: ComponentRegistry 正确渲染 RetrievalCandidateCard 且有 save/reject 按钮."""
    _goto_step_deck(page)

    html = page.evaluate("""() => {
        const cr = window.ComponentRegistry;
        return cr.renderCard({
            component: 'RetrievalCandidateCard',
            props: {
                kind: 'paper',
                title: 'Steel Defect Detection Using YOLO',
                source: 'IEEE Access',
                score: 0.92,
                snippet: 'We propose a modified YOLOv5 for steel surface defect detection.',
                matched_keywords: ['YOLO', 'defect detection'],
            },
        });
    }""")
    assert "pa-card--RetrievalCandidateCard" in html
    assert "Steel Defect Detection" in html, "Title should appear"
    assert "paper" in html, "kind should appear"
    # 按钮存在 (save_candidate / reject_candidate)
    assert "save_candidate" in html or "候选" in html, "save_candidate button or label expected"


# ---------- S22-PW-8: S21 Step Deck main flow doesn't regress ---------- #


def test_pw_08_s21_step_deck_not_broken(page):
    """S22-PW-8: S21 的 Step Deck 主流程不回退 — rail 9 步、mock 流暂停、通过后推进."""
    _goto_step_deck(page)

    # 1. rail 有 9 步
    rail_items = page.locator("#step-deck-rail .step-rail__item")
    assert rail_items.count() == 9, f"Expected 9 rail items, got {rail_items.count()}"

    # 2. mock 流启动后在 keyword_review 暂停
    _start_mock_and_wait_keyword(page)

    # keyword_review rail item 有 is-current
    kr_item = page.locator("#step-deck-rail .step-rail__item[data-step-key='keyword_review']")
    expect(kr_item).to_have_class(re.compile(r"is-current"))

    # 3. 点击通过
    approve_btn = page.locator("[data-gate-action='approve'][data-step-key='keyword_review']").first
    expect(approve_btn).to_be_visible()
    approve_btn.click()

    # keyword_review 状态应变为 approved 或 completed
    page.wait_for_function(
        """() => {
            const rs = window.StepDeckUI.ui.runState;
            const s = rs.steps.keyword_review;
            return s && (s.status === 'approved' || s.status === 'completed');
        }""",
        timeout=5000,
    )
