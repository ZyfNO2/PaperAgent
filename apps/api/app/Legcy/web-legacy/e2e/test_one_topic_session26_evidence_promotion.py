"""Session 26: Evidence Promotion e2e tests (SOP §6).

覆盖 S26-PW-1~8:
1. S26-PW-1: 候选未选中时晋升按钮 disabled
2. S26-PW-2: 选中但 URL 未验证时显示 blocked
3. S26-PW-3: URLVerified 后按钮可用
4. S26-PW-4: 晋升后 EvidenceRefCard 出现
5. S26-PW-5: EvidenceRef 可追溯到 Candidate
6. S26-PW-6: 晋升不生成 supports
7. S26-PW-7: 失败 URL 显示原因
8. S26-PW-8: S25 双栏不回退
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


def _get_first_candidate(page):
    return page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const candStep = rs.steps.candidates;
        const cardId = candStep.blocks[0];
        return { id: cardId, card: rs.cards[cardId] };
    }""")


# ---------- S26-PW-1: 候选未选中时晋升按钮 disabled ---------- #


def test_pw_01_unselected_promote_disabled(page):
    """S26-PW-1: 未选中的候选显示 disabled 晋升按钮."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const candStep = rs.steps.candidates;
        const card = rs.cards[candStep.blocks[0]];
        const ep = window.EvidencePromotion;
        const html = ep.renderPromotionButton(card, [], {});
        return {
            hasDisabled: html.includes('disabled'),
            hasLock: html.includes('🔒'),
            hasNotSelected: html.includes('not selected'),
        };
    }""")
    assert result["hasDisabled"], "Button should be disabled for unselected candidate"
    assert result["hasLock"], "Should show lock icon"
    assert result["hasNotSelected"], "Should explain not selected"


# ---------- S26-PW-2: 选中但 URL 未验证时显示 blocked ---------- #


def test_pw_02_selected_unverified_blocked(page):
    """S26-PW-2: 选中但 URL 未验证时晋升被阻止."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const candStep = rs.steps.candidates;
        const card = rs.cards[candStep.blocks[0]];
        const wb = window.WorkspaceBoard;
        const ep = window.EvidencePromotion;
        // Add to selected (verification_status defaults to 'unchecked')
        wb.addToSelected(card);
        const selected = wb.getSelectedResources();
        const html = ep.renderPromotionButton(card, selected, {});
        return {
            hasDisabled: html.includes('disabled'),
            hasNotVerified: html.includes('not verified'),
        };
    }""")
    assert result["hasDisabled"], "Should be disabled when URL unchecked"
    assert result["hasNotVerified"], "Should explain URL not verified"


# ---------- S26-PW-3: URLVerified 后按钮可用 ---------- #


def test_pw_03_verified_url_promote_enabled(page):
    """S26-PW-3: URL 验证通过后晋升按钮可用."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const candStep = rs.steps.candidates;
        const card = rs.cards[candStep.blocks[0]];
        const wb = window.WorkspaceBoard;
        const ep = window.EvidencePromotion;
        wb.addToSelected(card);
        // Manually set verification status to verified
        const selected = wb.getSelectedResources();
        selected[0].verificationStatus = 'verified';
        const html = ep.renderPromotionButton(card, selected, {});
        return {
            hasPromoteBtn: html.includes('promote_to_evidence'),
            notDisabled: !html.includes('disabled'),
        };
    }""")
    assert result["hasPromoteBtn"], "Should have promote button"
    assert result["notDisabled"], "Button should not be disabled"


# ---------- S26-PW-4: 晋升后 EvidenceRefCard 出现 ---------- #


def test_pw_04_promote_creates_evidence_ref(page):
    """S26-PW-4: 晋升操作生成 EvidenceRef."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const candStep = rs.steps.candidates;
        const card = rs.cards[candStep.blocks[0]];
        const ep = window.EvidencePromotion;
        // Setup: selected + verified
        const wb = window.WorkspaceBoard;
        wb.addToSelected(card);
        const selected = wb.getSelectedResources();
        selected[0].verificationStatus = 'verified';
        // Promote
        const promoResult = ep.promoteToEvidence(card, selected, {}, 'Key baseline paper', 'supports baseline comparison');
        return {
            status: promoResult.status,
            hasEvidenceRef: !!promoResult.evidence_ref,
            evId: promoResult.evidence_ref && promoResult.evidence_ref.evidence_id,
            title: promoResult.evidence_ref && promoResult.evidence_ref.title,
        };
    }""")
    assert result["status"] == "promoted", f"Expected promoted, got {result['status']}"
    assert result["hasEvidenceRef"], "Should have evidence_ref"
    assert result["evId"], "EvidenceRef should have ID"
    assert result["title"], "EvidenceRef should have title"


# ---------- S26-PW-5: EvidenceRef 可追溯到 Candidate ---------- #


def test_pw_05_evidence_traces_to_candidate(page):
    """S26-PW-5: EvidenceRef 包含 candidate 引用信息."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const candStep = rs.steps.candidates;
        const card = rs.cards[candStep.blocks[0]];
        const ep = window.EvidencePromotion;
        const wb = window.WorkspaceBoard;
        wb.addToSelected(card);
        const selected = wb.getSelectedResources();
        selected[0].verificationStatus = 'verified';
        const promoResult = ep.promoteToEvidence(card, selected, {}, 'Promoted from candidate ' + card.id);
        const ev = promoResult.evidence_ref;
        return {
            hasCandidateRef: ev.reason.includes(card.id),
            hasUrl: !!ev.url,
            reviewStatus: ev.review_status,
        };
    }""")
    assert result["hasCandidateRef"], "EvidenceRef reason should reference candidate ID"
    assert result["reviewStatus"] == "pending", "review_status should be pending"


# ---------- S26-PW-6: 晋升不生成 supports ---------- #


def test_pw_06_promote_no_supports(page):
    """S26-PW-6: 晋升不自动生成 final supports — review_status 为 pending."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const candStep = rs.steps.candidates;
        const card = rs.cards[candStep.blocks[0]];
        const ep = window.EvidencePromotion;
        const wb = window.WorkspaceBoard;
        wb.addToSelected(card);
        const selected = wb.getSelectedResources();
        selected[0].verificationStatus = 'verified';
        const promoResult = ep.promoteToEvidence(card, selected, {});
        const ev = promoResult.evidence_ref;
        return {
            reviewPending: ev.review_status === 'pending',
            noReportParagraph: !ev.report_paragraph,
            noConclusion: !ev.conclusion,
        };
    }""")
    assert result["reviewPending"], "review_status should be pending, not final"
    assert result["noReportParagraph"], "Should not have report_paragraph"
    assert result["noConclusion"], "Should not have conclusion"


# ---------- S26-PW-7: 失败 URL 显示原因 ---------- #


def test_pw_07_failed_url_shows_reason(page):
    """S26-PW-7: URL 验证失败时显示失败原因."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const candStep = rs.steps.candidates;
        const card = rs.cards[candStep.blocks[0]];
        const ep = window.EvidencePromotion;
        const wb = window.WorkspaceBoard;
        wb.addToSelected(card);
        const selected = wb.getSelectedResources();
        // URL failed with reason
        const urlVerifications = {};
        urlVerifications[card.id] = { status: 'failed', failure_reason: '404 Not Found' };
        const html = ep.renderPromotionButton(card, selected, urlVerifications);
        return {
            hasDisabled: html.includes('disabled'),
            hasFailed: html.includes('验证失败') || html.includes('failed'),
            hasReason: html.includes('404') || html.includes('Not Found'),
        };
    }""")
    assert result["hasDisabled"], "Button should be disabled for failed URL"
    assert result["hasFailed"], "Should show verification failed"
    assert result["hasReason"], "Should show failure reason"


# ---------- S26-PW-8: S25 双栏不回退 ---------- #


def test_pw_08_s25_workspace_no_regression(page):
    """S26-PW-8: S25 双栏工作台功能不回退."""
    _setup_full_candidates(page)
    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const wb = window.WorkspaceBoard;
        const ep = window.EvidencePromotion;
        // S25: WorkspaceBoard works
        const candStep = rs.steps.candidates;
        const card = rs.cards[candStep.blocks[0]];
        const selId = wb.addToSelected(card);
        const selected = wb.getSelectedResources();
        const cov = wb.computeCoverage();
        // S26: EvidencePromotion module loaded
        const epReady = ep && ep.isReady();
        return {
            s25_addOk: !!selId,
            s25_selectedCount: selected.length,
            s25_coverageTotal: cov.totalSelected,
            s26_epReady: epReady,
        };
    }""")
    assert result["s25_addOk"], "S25 addToSelected should still work"
    assert result["s25_selectedCount"] == 1, "S25 selected count should be 1"
    assert result["s25_coverageTotal"] == 1, "S25 coverage should reflect selection"
    assert result["s26_epReady"], "S26 EvidencePromotion should be ready"
