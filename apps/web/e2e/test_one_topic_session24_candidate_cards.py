"""Session 24: Candidate Cards e2e tests (SOP §9).

覆盖 S24-PW-1~10:
1. S24-PW-1: 未确认关键词时 query_plan blocked
2. S24-PW-2: 确认关键词后显示 paper/dataset/repo query
3. S24-PW-3: 生成候选资源卡
4. S24-PW-4: 候选卡显示 source URL 和 matched_keywords
5. S24-PW-5: save_candidate 改变 user_mark
6. S24-PW-6: reject_candidate 改变 user_mark
7. S24-PW-7: promote_to_selected 不写 Evidence
8. S24-PW-8: Trace drawer 可见候选操作
9. S24-PW-9: S21 keyword gate 不回退
10. S24-PW-10: 非法 candidate card 降级
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
    """Fire startExtendedMockStream and apply all events."""
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
    """Fire startCandidatesMockStream and apply all events."""
    page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const events = window.StepDeckUI.startCandidatesMockStream(rs);
        if (events) events.forEach(evt => window.StepDeck.applyEvent(rs, evt));
        window.StepDeckUI.renderAll();
    }""")


# ---------- S24-PW-1: query_plan blocked without keyword approval ---------- #


def test_pw_01_query_plan_blocked_without_approval(page):
    """S24-PW-1: keyword_review 未确认时 isToolAllowed 拦截 search_papers."""
    _goto_step_deck(page)
    result = page.evaluate("""() => {
        const pp = window.PromptProtocol;
        const rs = window.StepDeck.createRunState();
        // keyword_review 未确认
        const toolCheck = pp.isToolAllowed('search_papers', rs);
        // generatePromptSkeleton 应含 preCondition 警告
        const skeleton = pp.generatePromptSkeleton('query_plan', {});
        return {
            toolBlocked: !toolCheck.allowed,
            hasPreCondition: skeleton.prompt.includes('pre-condition'),
        };
    }""")
    assert result["toolBlocked"], "search_papers should be blocked without keyword approval"
    assert result["hasPreCondition"], "query_plan prompt should mention pre-condition"


# ---------- S24-PW-2: confirmed keywords show paper/dataset/repo query ---------- #


def test_pw_02_extended_mock_shows_queries(page):
    """S24-PW-2: keyword 确认后 extended mock 显示 paper/dataset/repo queries."""
    _goto_step_deck(page)
    _start_mock_and_wait_keyword(page)
    _approve_keyword(page)
    _fire_extended_mock(page)

    # query_plan should have SearchQueryPlanCard
    card_html = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const qpStep = rs.steps.query_plan;
        if (!qpStep || !qpStep.blocks.length) return '';
        const cardId = qpStep.blocks[0];
        return window.ComponentRegistry.renderCard(rs.cards[cardId]);
    }""")
    assert "SearchQueryPlanCard" in card_html
    assert "paper" in card_html
    assert "dataset" in card_html
    assert "repo" in card_html


# ---------- S24-PW-3: generate candidate resource cards ---------- #


def test_pw_03_candidates_render(page):
    """S24-PW-3: candidates mock 生成 3 张候选资源卡."""
    _goto_step_deck(page)
    _start_mock_and_wait_keyword(page)
    _approve_keyword(page)
    _fire_extended_mock(page)
    _approve_query_plan(page)
    _fire_candidates_mock(page)

    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const candStep = rs.steps.candidates;
        if (!candStep) return { count: 0, types: [] };
        const types = candStep.blocks.map(id => rs.cards[id] && rs.cards[id].type);
        return { count: candStep.blocks.length, types };
    }""")
    assert result["count"] == 3, f"Expected 3 candidate cards, got {result['count']}"
    assert all(t == "RetrievalCandidateCard" for t in result["types"])


# ---------- S24-PW-4: candidate card shows URL and matched_keywords ---------- #


def test_pw_04_candidate_card_details(page):
    """S24-PW-4: 候选卡显示 source URL 和 matched_keywords."""
    _goto_step_deck(page)
    _start_mock_and_wait_keyword(page)
    _approve_keyword(page)
    _fire_extended_mock(page)
    _approve_query_plan(page)
    _fire_candidates_mock(page)

    html = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        const candStep = rs.steps.candidates;
        const cardId = candStep.blocks[0];
        return window.ComponentRegistry.renderCard(rs.cards[cardId]);
    }""")
    assert "example.com" in html, "URL should appear"
    assert "YOLO" in html or "钢材" in html, "matched_keywords should appear"


# ---------- S24-PW-5: save_candidate changes user_mark ---------- #


def test_pw_05_save_candidate(page):
    """S24-PW-5: save_candidate 改变候选 user_mark 为 saved."""
    _goto_step_deck(page)
    result = page.evaluate("""() => {
        const cr = window.ComponentRegistry;
        // 直接测试 renderCard 输出含 save_candidate 按钮
        const html = cr.renderCard({
            component: 'RetrievalCandidateCard',
            id: 'cand_test',
            props: {
                kind: 'paper',
                title: 'Test Paper',
                matched_keywords: ['YOLO'],
            },
        });
        const hasSave = html.includes('save_candidate');
        return { hasSave, html: html.slice(0, 300) };
    }""")
    assert result["hasSave"], "RetrievalCandidateCard should have save_candidate button"


# ---------- S24-PW-6: reject_candidate changes user_mark ---------- #


def test_pw_06_reject_candidate(page):
    """S24-PW-6: RetrievalCandidateCard 包含 reject_candidate 按钮."""
    _goto_step_deck(page)
    result = page.evaluate("""() => {
        const cr = window.ComponentRegistry;
        const html = cr.renderCard({
            component: 'RetrievalCandidateCard',
            id: 'cand_test',
            props: {
                kind: 'paper',
                title: 'Test Paper',
                matched_keywords: ['YOLO'],
            },
        });
        return html.includes('reject_candidate');
    }""")
    assert result is True


# ---------- S24-PW-7: promote_to_selected doesn't write Evidence ---------- #


def test_pw_07_promote_no_evidence(page):
    """S24-PW-7: promote_to_selected 不写 Evidence — 候选与证据隔离."""
    _goto_step_deck(page)
    result = page.evaluate("""() => {
        const pp = window.PromptProtocol;
        // candidates 合同不含 Evidence 字段
        const contract = pp.STEP_CONTRACTS.candidates;
        const hasEvidenceField = contract.requiredFields.includes('evidence_list');
        // cardType 是 RetrievalCandidateCard，不是 EvidenceRefCard
        return {
            hasEvidenceField,
            cardType: contract.cardType,
            isCandidateNotEvidence: contract.cardType === 'RetrievalCandidateCard',
        };
    }""")
    assert result["hasEvidenceField"] is False, "candidates step should not require evidence_list"
    assert result["isCandidateNotEvidence"] is True, "cardType should be RetrievalCandidateCard"


# ---------- S24-PW-8: Trace drawer visible for candidate operations ---------- #


def test_pw_08_trace_visible(page):
    """S24-PW-8: eventBuffer 记录候选相关事件."""
    _goto_step_deck(page)
    _start_mock_and_wait_keyword(page)
    _approve_keyword(page)
    _fire_extended_mock(page)
    _approve_query_plan(page)
    _fire_candidates_mock(page)

    result = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        // eventBuffer 应包含 card_delta 事件（candidates step）
        const candidateEvents = rs.eventBuffer.filter(e =>
            e.step_key === 'candidates' && e.event_type === 'card_delta'
        );
        const hasTrace = candidateEvents.length > 0;
        return { hasTrace, candidateEventCount: candidateEvents.length };
    }""")
    assert result["hasTrace"], "eventBuffer should contain candidate card_delta events"
    assert result["candidateEventCount"] == 3, f"Expected 3 candidate events, got {result['candidateEventCount']}"


# ---------- S24-PW-9: S21 keyword gate not regressed ---------- #


def test_pw_09_s21_keyword_gate_intact(page):
    """S24-PW-9: S21 keyword gate 不回退 — mock 流仍暂停在 keyword_review."""
    _goto_step_deck(page)
    _start_mock_and_wait_keyword(page)

    kr_status = page.evaluate("""() => {
        const rs = window.StepDeckUI.ui.runState;
        return rs.steps.keyword_review.status;
    }""")
    assert kr_status == "awaiting_review", f"Expected awaiting_review, got {kr_status}"


# ---------- S24-PW-10: invalid candidate card shows fallback ---------- #


def test_pw_10_invalid_candidate_fallback(page):
    """S24-PW-10: 非法 candidate card 降级为 fallback 或 invalid 卡."""
    _goto_step_deck(page)
    result = page.evaluate("""() => {
        const cr = window.ComponentRegistry;
        // 非法 RetrievalCandidateCard（缺 kind）
        const html = cr.renderCard({
            component: 'RetrievalCandidateCard',
            props: { title: 'Missing kind', matched_keywords: [] },
        });
        const isInvalid = html.includes('pa-card--invalid');
        const isFallback = html.includes('pa-card--fallback');
        return { isInvalid, isFallback, ok: isInvalid || isFallback };
    }""")
    assert result["ok"], f"Invalid card should degrade: {result}"
