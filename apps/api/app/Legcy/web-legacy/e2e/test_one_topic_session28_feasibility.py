"""Session 28: Feasibility Card e2e tests (SOP §6).

覆盖 S28-PW-1~7:
1. S28-PW-1: 可行性卡显示 7 维
2. S28-PW-2: 硬性否决显示
3. S28-PW-3: GO/CONDITIONAL/PIVOT/PARK/STOP 可见
4. S28-PW-4: PIVOT 路线可展开
5. S28-PW-5: 点击路线不会直接改题，需确认
6. S28-PW-6: 每条结论有证据或缺口
7. S28-PW-7: S25-S27 不回退
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
    page.click("button.tab[data-tab='step-deck']")
    page.wait_for_selector("#page-step-deck:not([hidden])", timeout=15000)
    page.wait_for_function("window.StepDeckUI && window.StepDeckUI.isReady()", timeout=10000)


def _start_mock_and_wait_keyword(page):
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
    page.wait_for_function(
        "window.StepDeckUI && window.StepDeckUI.ui.runState.isStreaming === false",
        timeout=10000,
    )


def _approve_keyword(page):
    approve_btn = page.locator("[data-gate-action='approve'][data-step-key='keyword_review']").first
    expect(approve_btn).to_be_visible()
    approve_btn.click()
    page.wait_for_function(
        """() => {
            const rs = window.StepDeckUI.ui.runState;
            return rs.hasApprovedGate2 === true;
        }""",
        timeout=5000,
    )


def _fire_extended_mock(page):
    page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const events = window.StepDeckUI.startExtendedMockStream(rs);
        if (events) events.forEach(evt => window.StepDeck.applyEvent(rs, evt));
        window.StepDeckUI.renderAll();
    }""")


def _approve_query_plan(page):
    approve_btn = page.locator("[data-gate-action='approve'][data-step-key='query_plan']").first
    expect(approve_btn).to_be_visible(timeout=5000)
    approve_btn.click()
    page.wait_for_function(
        """() => {
            const rs = window.StepDeckUI.ui.runState;
            const s = rs.steps.query_plan;
            return s && (s.status === 'approved' || s.status === 'completed');
        }""",
        timeout=5000,
    )


def _fire_candidates_mock(page):
    page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const events = window.StepDeckUI.startCandidatesMockStream(rs);
        if (events) events.forEach(evt => window.StepDeck.applyEvent(rs, evt));
        window.StepDeckUI.renderAll();
    }""")


def _setup_full_candidates(page):
    _goto_step_deck(page)
    _start_mock_and_wait_keyword(page)
    _approve_keyword(page)
    _fire_extended_mock(page)
    _approve_query_plan(page)
    _fire_candidates_mock(page)


# ---------- Mock assessment data ---------- #

MOCK_ASSESSMENT = {
    "dimensions": [
        {"dimension": "EvidenceSupport", "score": 60, "level": "medium", "evidence_refs": ["ev_1", "ev_2"], "reason": "2 EvidenceRefs", "suggestion": "Need more", "missing_evidence": ["1 more EvidenceRef"]},
        {"dimension": "DataAvailability", "score": 80, "level": "low", "evidence_refs": ["ev_1"], "reason": "Dataset available", "suggestion": "Verify access", "missing_evidence": []},
        {"dimension": "BaselineReadiness", "score": 0, "level": "high", "evidence_refs": [], "reason": "No baseline", "suggestion": "Find baseline", "missing_evidence": ["Baseline paper"]},
        {"dimension": "ExperimentalClarity", "score": 0, "level": "high", "evidence_refs": [], "reason": "No experiment plan", "suggestion": "Design experiments", "missing_evidence": ["Experiment design"]},
        {"dimension": "ScopeControl", "score": 30, "level": "medium", "evidence_refs": [], "reason": "Scope unclear", "suggestion": "Narrow scope", "missing_evidence": []},
        {"dimension": "ResourceFit", "score": 20, "level": "medium", "evidence_refs": [], "reason": "Resources uncertain", "suggestion": "Verify URLs", "missing_evidence": []},
        {"dimension": "NoveltyDifferentiation", "score": 50, "level": "medium", "evidence_refs": ["ev_2"], "reason": "Some differentiation", "suggestion": "More comparison", "missing_evidence": []},
    ],
    "overall_score": 34,
    "verdict": "PIVOT",
    "hard_vetoes": [
        {"rule": "no_baseline", "description": "无 baseline/repo/可比较方法不得 GO", "triggered": True, "blocked_verdicts": ["GO"]},
        {"rule": "no_experiment_plan", "description": "只有文字方案无实验不得 GO", "triggered": True, "blocked_verdicts": ["GO"]},
    ],
    "pivot_routes": [
        {"route_type": "conservative", "new_topic": "Steel Defect — 简化版", "changed_keywords": ["简化任务", "单一数据集"], "required_evidence": ["简化后的 baseline"], "expected_workload": "3-4 个月", "risk_delta": "大幅降低", "recommended_for": "时间紧迫"},
        {"route_type": "balanced", "new_topic": "Steel Defect — 替换数据集版", "changed_keywords": ["公开数据集", "标准指标"], "required_evidence": ["新数据集 URL", "baseline 代码"], "expected_workload": "4-5 个月", "risk_delta": "中等降低", "recommended_for": "方法有创新"},
        {"route_type": "aggressive", "new_topic": "Steel Defect — 创新版", "changed_keywords": ["补充实验", "增加 baseline"], "required_evidence": ["实验设计", "多个 baseline"], "expected_workload": "5-6 个月", "risk_delta": "略高", "recommended_for": "有充足时间"},
    ],
    "summary": "Verdict: PIVOT, Score: 34/100 — 需要收缩或换方向",
    "bound_evidence": ["ev_1", "ev_2"],
    "missing_evidence": ["1 more EvidenceRef", "Baseline paper", "Experiment design"],
}


# ---------- S28-PW-1: 可行性卡显示 7 维 ---------- #


def test_pw_01_seven_dimensions_visible(page):
    """S28-PW-1: 可行性卡渲染 7 个维度."""
    _goto_step_deck(page)
    result = page.evaluate("""(assessment) => {
        const fc = window.FeasibilityCard;
        const html = fc.renderAssessment(assessment);
        const dimCount = (html.match(/class="feasibility-dim"/g) || []).length;
        const dimNames = ['EvidenceSupport', 'DataAvailability', 'BaselineReadiness',
            'ExperimentalClarity', 'ScopeControl', 'ResourceFit', 'NoveltyDifferentiation'];
        const allPresent = dimNames.every(n => html.includes(n));
        return { dimCount, allPresent };
    }""", MOCK_ASSESSMENT)
    assert result["dimCount"] == 7, "Should render 7 dimensions"
    assert result["allPresent"], "All 7 dimension names should be present"


# ---------- S28-PW-2: 硬性否决显示 ---------- #


def test_pw_02_hard_veto_displayed(page):
    """S28-PW-2: 触发的硬性否决项可见."""
    _goto_step_deck(page)
    result = page.evaluate("""(assessment) => {
        const fc = window.FeasibilityCard;
        const html = fc.renderAssessment(assessment);
        return {
            hasVetoSection: html.includes('hard-veto'),
            hasNoBaseline: html.includes('no_baseline') || html.includes('无 baseline'),
            hasNoExperiment: html.includes('no_experiment_plan') || html.includes('无实验'),
            hasBlockIcon: html.includes('🚫'),
        };
    }""", MOCK_ASSESSMENT)
    assert result["hasVetoSection"], "Should have hard veto section"
    assert result["hasBlockIcon"], "Should show block icon"


# ---------- S28-PW-3: 裁决标签可见 ---------- #


def test_pw_03_verdict_badge_visible(page):
    """S28-PW-3: 裁决标签（PIVOT）可见."""
    _goto_step_deck(page)
    result = page.evaluate("""(assessment) => {
        const fc = window.FeasibilityCard;
        const html = fc.renderAssessment(assessment);
        return {
            hasPivot: html.includes('PIVOT'),
            hasVerdictBadge: html.includes('verdict-badge'),
            hasScore: html.includes('34/100'),
        };
    }""", MOCK_ASSESSMENT)
    assert result["hasPivot"], "Should show PIVOT verdict"
    assert result["hasVerdictBadge"], "Should have verdict badge"
    assert result["hasScore"], "Should show score"


# ---------- S28-PW-4: PIVOT 路线可展开 ---------- #


def test_pw_04_pivot_routes_expandable(page):
    """S28-PW-4: 三条 PIVOT 路线可见且可展开."""
    _goto_step_deck(page)
    result = page.evaluate("""(assessment) => {
        const fc = window.FeasibilityCard;
        const html = fc.renderAssessment(assessment);
        return {
            hasConservative: html.includes('conservative'),
            hasBalanced: html.includes('balanced'),
            hasAggressive: html.includes('aggressive'),
            routeCount: (html.match(/pivot-route/g) || []).length,
            hasSelectBtn: html.includes('select_pivot'),
        };
    }""", MOCK_ASSESSMENT)
    assert result["hasConservative"], "Should have conservative route"
    assert result["hasBalanced"], "Should have balanced route"
    assert result["hasAggressive"], "Should have aggressive route"
    assert result["routeCount"] == 3, "Should have 3 pivot routes"
    assert result["hasSelectBtn"], "Each route should have select button"


# ---------- S28-PW-5: 点击路线需确认 ---------- #


def test_pw_05_pivot_needs_confirmation(page):
    """S28-PW-5: 选择路线按钮有确认标记（不直接改题）."""
    _goto_step_deck(page)
    result = page.evaluate("""(assessment) => {
        const fc = window.FeasibilityCard;
        const html = fc.renderAssessment(assessment);
        return {
            hasConfirmText: html.includes('需确认') || html.includes('confirm'),
            btnHasAction: html.includes('data-action="select_pivot"'),
            btnHasIndex: html.includes('data-route-index'),
        };
    }""", MOCK_ASSESSMENT)
    assert result["hasConfirmText"], "Select button should indicate confirmation needed"
    assert result["btnHasAction"], "Button should have data-action"
    assert result["btnHasIndex"], "Button should have route index"


# ---------- S28-PW-6: 每条结论有证据或缺口 ---------- #


def test_pw_06_evidence_or_missing(page):
    """S28-PW-6: 每个维度有 evidence 或 missing_evidence 信息."""
    _goto_step_deck(page)
    result = page.evaluate("""(assessment) => {
        const fc = window.FeasibilityCard;
        const html = fc.renderAssessment(assessment);
        return {
            hasEvidenceSection: html.includes('dim-evidence') || html.includes('📎'),
            hasMissingSection: html.includes('dim-missing') || html.includes('缺少'),
            hasSuggestion: html.includes('dim-suggestion') || html.includes('💡'),
            hasMissingOverall: html.includes('feasibility-missing'),
        };
    }""", MOCK_ASSESSMENT)
    assert result["hasEvidenceSection"], "Should show evidence references"
    assert result["hasMissingSection"], "Should show missing evidence"
    assert result["hasSuggestion"], "Should show suggestions"
    assert result["hasMissingOverall"], "Should have overall missing section"


# ---------- S28-PW-7: S25-S27 不回退 ---------- #


def test_pw_07_s25_s27_no_regression(page):
    """S28-PW-7: S25 双栏 + S26 晋升 + S27 StreamClient 不回退."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const wb = window.WorkspaceBoard;
        const ep = window.EvidencePromotion;
        const sc = window.StreamClient;
        const fc = window.FeasibilityCard;

        // S25: workspace works
        const candStep = rs.steps.candidates;
        const card = rs.cards[candStep.blocks[0]];
        const selId = wb.addToSelected(card);

        // S26: promotion gate
        const selected = wb.getSelectedResources();
        const gateResult = ep.checkPromotionGate(card, selected, {});

        return {
            s25_addOk: !!selId,
            s26_gateResult: gateResult.status,
            s27_scReady: sc && sc.isReady(),
            s28_fcReady: fc && fc.isReady(),
        };
    }""")
    assert result["s25_addOk"], "S25 addToSelected should still work"
    assert result["s26_gateResult"] in ("blocked", "eligible"), "S26 gate should respond"
    assert result["s27_scReady"], "S27 StreamClient should be ready"
    assert result["s28_fcReady"], "S28 FeasibilityCard should be ready"
