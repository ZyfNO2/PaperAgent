"""Session 25: Workspace Board e2e tests (SOP §9).

覆盖 S25-PW-1~8:
1. S25-PW-1: 双栏工作台可打开
2. S25-PW-2: 右栏显示S24候选
3. S25-PW-3: 点击加入后左栏出现资料
4. S25-PW-4: 左栏移除后右栏候选仍存在
5. S25-PW-5: mark_core 可见
6. S25-PW-6: coverage summary 更新
7. S25-PW-7: 加入左栏不生成EvidenceRef
8. S25-PW-8: S21-S24主流程不回退
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
    """Navigate to step-deck, run mock stream through keyword+query_plan+candidates."""
    _goto_step_deck(page)
    _start_mock_and_wait_keyword(page)
    _approve_keyword(page)
    _fire_extended_mock(page)
    _approve_query_plan(page)
    _fire_candidates_mock(page)


# ---------- S25-PW-1: 双栏工作台可打开 ---------- #


def test_pw_01_workspace_board_visible(page):
    """S25-PW-1: WorkspaceBoard 模块可访问且 renderWorkspace 可执行."""
    _goto_step_deck(page)
    result = page.evaluate("""() => {
        const wb = window.WorkspaceBoard;
        if (!wb || typeof wb.renderWorkspace !== 'function') return { ok: false, reason: 'not loaded' };
        const html = wb.renderWorkspace(null);
        return {
            ok: true,
            hasLeftCol: html.includes('ws-col--selected'),
            hasRightCol: html.includes('ws-col--candidates'),
            hasCoverage: html.includes('ws-coverage'),
        };
    }""")
    assert result["ok"], f"WorkspaceBoard not loaded: {result}"
    assert result["hasLeftCol"], "Should have left column (selected)"
    assert result["hasRightCol"], "Should have right column (candidates)"
    assert result["hasCoverage"], "Should have coverage summary"


# ---------- S25-PW-2: 右栏显示S24候选 ---------- #


def test_pw_02_right_col_shows_candidates(page):
    """S25-PW-2: 右栏显示 S24 候选卡."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const wb = window.WorkspaceBoard;
        const html = wb.renderCandidateColumn(rs);
        const hasCandidate = html.includes('ws-item--candidate');
        const count = (html.match(/ws-item--candidate/g) || []).length;
        return { hasCandidate, count };
    }""")
    assert result["hasCandidate"], "Right column should show candidate items"
    assert result["count"] == 3, f"Expected 3 candidates in right col, got {result['count']}"


# ---------- S25-PW-3: 点击加入后左栏出现资料 ---------- #


def test_pw_03_add_to_left_col(page):
    """S25-PW-3: addToSelected 后左栏出现资料."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const wb = window.WorkspaceBoard;
        // Get first candidate card
        const candStep = rs.steps.candidates;
        const cardId = candStep.blocks[0];
        const card = rs.cards[cardId];
        // Add to selected
        const selId = wb.addToSelected(card);
        // Render left column
        const leftHtml = wb.renderSelectedColumn();
        return {
            selectedId: selId,
            hasItem: leftHtml.includes('ws-item--selected'),
            hasTitle: leftHtml.includes(card.props.title),
        };
    }""")
    assert result["selectedId"], "Should return a selected ID"
    assert result["hasItem"], "Left column should show selected item"
    assert result["hasTitle"], "Left column should show the candidate title"


# ---------- S25-PW-4: 左栏移除后右栏候选仍存在 ---------- #


def test_pw_04_remove_preserves_candidates(page):
    """S25-PW-4: removeFromSelected 后右栏候选仍存在."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const wb = window.WorkspaceBoard;
        const candStep = rs.steps.candidates;
        const cardId = candStep.blocks[0];
        const card = rs.cards[cardId];
        // Add then remove
        wb.addToSelected(card);
        wb.removeFromSelected(cardId);
        const leftHtml = wb.renderSelectedColumn();
        const rightHtml = wb.renderCandidateColumn(rs);
        const leftEmpty = !leftHtml.includes('ws-item--selected');
        const rightStillHas = rightHtml.includes('ws-item--candidate');
        return { leftEmpty, rightStillHas };
    }""")
    assert result["leftEmpty"], "Left column should be empty after remove"
    assert result["rightStillHas"], "Right column candidates should still exist"


# ---------- S25-PW-5: mark_core 可见 ---------- #


def test_pw_05_mark_core_visible(page):
    """S25-PW-5: mark_core 操作后左栏显示⭐核心标签."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const wb = window.WorkspaceBoard;
        const candStep = rs.steps.candidates;
        const cardId = candStep.blocks[0];
        const card = rs.cards[cardId];
        wb.addToSelected(card);
        wb.markCore(cardId, true);
        const leftHtml = wb.renderSelectedColumn();
        return {
            hasCoreTag: leftHtml.includes('核心'),
            hasCoreClass: leftHtml.includes('pa-tag--core'),
        };
    }""")
    assert result["hasCoreTag"], "Left column should show core tag after markCore"
    assert result["hasCoreClass"], "Core tag should have pa-tag--core class"


# ---------- S25-PW-6: coverage summary 更新 ---------- #


def test_pw_06_coverage_summary_updates(page):
    """S25-PW-6: 覆盖度摘要随选中资料更新."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const wb = window.WorkspaceBoard;
        const candStep = rs.steps.candidates;
        // Add all 3 candidates
        candStep.blocks.forEach(function(cardId) {
            wb.addToSelected(rs.cards[cardId]);
        });
        const cov = wb.computeCoverage();
        const summaryHtml = wb.renderCoverageSummary();
        return {
            totalSelected: cov.totalSelected,
            hasCoverageHtml: summaryHtml.includes('ws-coverage'),
            hasPaperCount: summaryHtml.includes('论文'),
        };
    }""")
    assert result["totalSelected"] == 3, f"Expected 3 selected, got {result['totalSelected']}"
    assert result["hasCoverageHtml"], "Coverage summary HTML should be present"
    assert result["hasPaperCount"], "Coverage should show paper count"


# ---------- S25-PW-7: 加入左栏不生成EvidenceRef ---------- #


def test_pw_07_no_evidence_created(page):
    """S25-PW-7: addToSelected 不写入 Evidence — Selected != Evidence."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const wb = window.WorkspaceBoard;
        const candStep = rs.steps.candidates;
        const cardId = candStep.blocks[0];
        wb.addToSelected(rs.cards[cardId]);
        const selected = wb.getSelectedResources();
        const sel = selected[0];
        // Should NOT have support_level or evidence fields
        const noEvidence = !sel.support_level && !sel.evidence_status;
        // Check there are no EvidenceRefCards created
        const evidenceCards = Object.values(rs.cards).filter(function(c) {
            return c.type === 'EvidenceRefCard' || c.component === 'EvidenceRefCard';
        });
        return {
            noEvidence,
            evidenceCardCount: evidenceCards.length,
            selectedKeys: Object.keys(sel),
        };
    }""")
    assert result["noEvidence"], f"Selected should not have evidence fields: {result['selectedKeys']}"
    assert result["evidenceCardCount"] == 0, "No EvidenceRefCard should be created"


# ---------- S25-PW-8: S21-S24主流程不回退 ---------- #


def test_pw_08_s21_s24_no_regression(page):
    """S25-PW-8: S21-S24主流程不回退 — keyword gate、query plan、candidates 完整."""
    _goto_step_deck(page)
    # S21: keyword gate works
    _start_mock_and_wait_keyword(page)
    kr_status = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        return rs.steps.keyword_review.status;
    }""")
    assert kr_status == "awaiting_review", f"S21 keyword gate regressed: {kr_status}"

    # S22: approve keyword → extended mock
    _approve_keyword(page)
    _fire_extended_mock(page)

    # S23: query_plan visible
    qp_result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const s = rs.steps.query_plan;
        return s && s.blocks && s.blocks.length > 0;
    }""")
    assert qp_result, "S23 query_plan should have blocks"

    # S24: candidates visible
    _approve_query_plan(page)
    _fire_candidates_mock(page)
    cand_result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const s = rs.steps.candidates;
        return s && s.blocks && s.blocks.length === 3;
    }""")
    assert cand_result, "S24 should have 3 candidate cards"

    # S25: workspace board accessible
    wb_result = page.evaluate("""() => {
        const wb = window.WorkspaceBoard;
        return wb && typeof wb.renderWorkspace === 'function' && wb.isReady();
    }""")
    assert wb_result, "S25 WorkspaceBoard should be accessible"
