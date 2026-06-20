"""Session 29: 开题报告草稿 Playwright 测试.

覆盖 S29-PW-1~8:
1. S29-PW-1: 报告草稿页可打开
2. S29-PW-2: 12 节可折叠浏览
3. S29-PW-3: 每节显示证据绑定
4. S29-PW-4: 缺证据警告可见
5. S29-PW-5: 工作量卡可见
6. S29-PW-6: 创新点卡可见
7. S29-PW-7: 无证据段落不会显示高置信
8. S29-PW-8: S28 风险裁决可见
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


# ---------- Mock draft data ---------- #

MOCK_DRAFT = {
    "topic_title": "钢铁缺陷检测研究",
    "feasibility_summary": "PIVOT (34/100)",
    "bound_evidence": ["ev_1", "ev_2"],
    "overall_missing": ["Baseline 论文", "实验设计"],
    "sections": [
        {"section_id": "topic_direction", "title": "题目与研究方向", "content": "钢铁缺陷检测", "evidence_refs": ["ev_1"], "selected_refs": [], "candidate_refs": [], "missing_evidence": [], "confidence": "high"},
        {"section_id": "background", "title": "研究背景与意义", "content": "工业质检重要性", "evidence_refs": ["ev_1", "ev_2"], "selected_refs": [], "candidate_refs": [], "missing_evidence": [], "confidence": "high"},
        {"section_id": "literature_review", "title": "国内外研究现状", "content": "现有检测方法", "evidence_refs": [], "selected_refs": ["sel_1"], "candidate_refs": [], "missing_evidence": [], "confidence": "medium"},
        {"section_id": "research_objectives", "title": "研究目标", "content": "提高检测精度", "evidence_refs": ["ev_2"], "selected_refs": [], "candidate_refs": [], "missing_evidence": [], "confidence": "high"},
        {"section_id": "research_content", "title": "研究内容", "content": "改进检测模型", "evidence_refs": ["ev_2"], "selected_refs": [], "candidate_refs": [], "missing_evidence": [], "confidence": "high"},
        {"section_id": "technical_approach", "title": "技术路线", "content": "ResNet 改进", "evidence_refs": ["ev_2"], "selected_refs": [], "candidate_refs": [], "missing_evidence": [], "confidence": "high"},
        {"section_id": "dataset_experiment", "title": "数据集与实验设计", "content": "NEU 数据集", "evidence_refs": ["ev_1"], "selected_refs": [], "candidate_refs": [], "missing_evidence": [], "confidence": "high"},
        {"section_id": "innovation", "title": "预期创新点", "content": "轻量改进", "evidence_refs": ["ev_2"], "selected_refs": [], "candidate_refs": [], "missing_evidence": [], "confidence": "high"},
        {"section_id": "workload", "title": "工作量拆解", "content": "7 个月", "evidence_refs": [], "selected_refs": [], "candidate_refs": [], "missing_evidence": ["工作量估算依据"], "confidence": "low"},
        {"section_id": "feasibility_risk", "title": "可行性与风险", "content": "PIVOT 裁决", "evidence_refs": [], "selected_refs": [], "candidate_refs": [], "missing_evidence": ["无 baseline", "无实验"], "confidence": "low"},
        {"section_id": "reference_resources", "title": "参考资源清单", "content": "5 条参考", "evidence_refs": ["ev_1", "ev_2"], "selected_refs": ["sel_1"], "candidate_refs": ["cand_1"], "missing_evidence": [], "confidence": "high"},
        {"section_id": "missing_evidence", "title": "待补证据", "content": "Baseline；实验设计", "evidence_refs": [], "selected_refs": [], "candidate_refs": [], "missing_evidence": ["Baseline 论文", "实验设计"], "confidence": "low"},
    ],
    "innovation_points": [
        {"title": "面向特定场景的方法适配", "description": "针对钢铁缺陷进行工程化适配", "evidence_base": "基于已收集证据", "risk": "待实验验证"},
        {"title": "实验对比与消融分析", "description": "系统性对比现有方法", "evidence_base": "需要 baseline", "risk": "数据集获取难度"},
    ],
    "workload_items": [
        {"item": "数据准备"}, {"item": "baseline 复现"}, {"item": "方法改进"},
        {"item": "实验对比"}, {"item": "消融实验"}, {"item": "系统或可视化 Demo"},
        {"item": "论文写作与答辩材料"},
    ],
}


def _inject_draft(page):
    page.evaluate("""(draft) => {
        const pd = window.ProposalDraft;
        const container = document.getElementById('proposal-draft-area') ||
            (() => {
                const d = document.createElement('div');
                d.id = 'proposal-draft-area';
                document.body.appendChild(d);
                return d;
            })();
        container.innerHTML = pd.renderDraft(draft);
    }""", MOCK_DRAFT)


# ---------- S29-PW-1: 报告草稿页可打开 ---------- #


def test_pw_01_draft_visible(page):
    """S29-PW-1: 开题报告草稿页可渲染."""
    _goto_step_deck(page)
    result = page.evaluate("""(draft) => {
        const pd = window.ProposalDraft;
        const html = pd.renderDraft(draft);
        return {
            hasProposalDraft: !!window.ProposalDraft,
            hasRenderDraft: typeof pd.renderDraft === 'function',
            htmlLength: html.length,
            hasTopicTitle: html.includes('钢铁缺陷检测研究'),
        };
    }""", MOCK_DRAFT)
    assert result["hasProposalDraft"], "ProposalDraft module should be loaded"
    assert result["hasRenderDraft"], "renderDraft should be a function"
    assert result["htmlLength"] > 100, "Should produce substantial HTML"
    assert result["hasTopicTitle"], "Should include topic title"


# ---------- S29-PW-2: 12 节可折叠浏览 ---------- #


def test_pw_02_twelve_sections_collapsible(page):
    """S29-PW-2: 12 个 section 可折叠."""
    _goto_step_deck(page)
    result = page.evaluate("""(draft) => {
        const pd = window.ProposalDraft;
        const html = pd.renderDraft(draft);
        const sectionCount = (html.match(/class="proposal-section"/g) || []).length;
        const hasToggle = html.includes('section-toggle');
        const hasOnClick = html.includes('classList.toggle');
        const sectionIds = draft.sections.map(s => s.section_id);
        const allPresent = sectionIds.every(id => html.includes('data-section-id="' + id + '"'));
        return { sectionCount, hasToggle, hasOnClick, allPresent };
    }""", MOCK_DRAFT)
    assert result["sectionCount"] == 12, "Should render 12 sections"
    assert result["hasToggle"], "Should have toggle arrows"
    assert result["hasOnClick"], "Should have onclick for collapse"
    assert result["allPresent"], "All 12 section IDs should be present"


# ---------- S29-PW-3: 每节显示证据绑定 ---------- #


def test_pw_03_evidence_binding(page):
    """S29-PW-3: 证据绑定区域可见."""
    _goto_step_deck(page)
    result = page.evaluate("""(draft) => {
        const pd = window.ProposalDraft;
        const html = pd.renderDraft(draft);
        return {
            hasEvidenceSection: html.includes('section-evidence'),
            hasEvidenceRef: html.includes('EvidenceRef'),
            hasSelected: html.includes('Selected'),
            hasCandidate: html.includes('Candidate'),
        };
    }""", MOCK_DRAFT)
    assert result["hasEvidenceSection"], "Should have evidence sections"
    assert result["hasEvidenceRef"], "Should show EvidenceRef label"
    assert result["hasSelected"], "Should show Selected label"
    assert result["hasCandidate"], "Should show Candidate label"


# ---------- S29-PW-4: 缺证据警告可见 ---------- #


def test_pw_04_missing_warning(page):
    """S29-PW-4: 缺少证据的节显示警告."""
    _goto_step_deck(page)
    result = page.evaluate("""(draft) => {
        const pd = window.ProposalDraft;
        const html = pd.renderDraft(draft);
        return {
            hasMissingTag: html.includes('missing-tag'),
            hasMissingOverall: html.includes('proposal-overall-missing'),
            hasWarningIcon: html.includes('⚠️ 缺证据'),
            hasMissingLabel: html.includes('缺少'),
        };
    }""", MOCK_DRAFT)
    assert result["hasMissingTag"], "Should have missing tags"
    assert result["hasMissingOverall"], "Should have overall missing section"
    assert result["hasWarningIcon"], "Should show warning icon"
    assert result["hasMissingLabel"], "Should show missing label"


# ---------- S29-PW-5: 工作量卡可见 ---------- #


def test_pw_05_workload_visible(page):
    """S29-PW-5: 工作量拆解卡片可见."""
    _goto_step_deck(page)
    result = page.evaluate("""(draft) => {
        const pd = window.ProposalDraft;
        const html = pd.renderDraft(draft);
        const workloadCount = (html.match(/class="workload-item"/g) || []).length;
        return {
            hasWorkloadSection: html.includes('proposal-workload'),
            workloadCount: workloadCount,
            hasWorkloadTitle: html.includes('工作量拆解'),
        };
    }""", MOCK_DRAFT)
    assert result["hasWorkloadSection"], "Should have workload section"
    assert result["workloadCount"] == 7, "Should have 7 workload items"
    assert result["hasWorkloadTitle"], "Should show workload title"


# ---------- S29-PW-6: 创新点卡可见 ---------- #


def test_pw_06_innovation_visible(page):
    """S29-PW-6: 创新点卡片可见."""
    _goto_step_deck(page)
    result = page.evaluate("""(draft) => {
        const pd = window.ProposalDraft;
        const html = pd.renderDraft(draft);
        const innovationCount = (html.match(/class="innovation-card"/g) || []).length;
        return {
            hasInnovationSection: html.includes('proposal-innovation'),
            innovationCount: innovationCount,
            hasInnovationTitle: html.includes('创新点'),
            hasEvidenceBase: html.includes('证据基础'),
            hasRisk: html.includes('风险'),
        };
    }""", MOCK_DRAFT)
    assert result["hasInnovationSection"], "Should have innovation section"
    assert result["innovationCount"] == 2, "Should have 2 innovation cards"
    assert result["hasInnovationTitle"], "Should show innovation title"
    assert result["hasEvidenceBase"], "Should show evidence base"
    assert result["hasRisk"], "Should show risk"


# ---------- S29-PW-7: 无证据段落不会显示高置信 ---------- #


def test_pw_07_no_high_without_evidence(page):
    """S29-PW-7: 无证据段落的置信度不会是高."""
    _goto_step_deck(page)
    result = page.evaluate("""(draft) => {
        const pd = window.ProposalDraft;
        const html = pd.renderDraft(draft);
        // workload (index 8) has no evidence → should be low
        // feasibility_risk (index 9) has no evidence → should be low
        // missing_evidence (index 11) has no evidence → should be low
        const workloadConf = html.includes('data-section-id="workload"') ?
            html.match(/data-section-id="workload"[\s\S]*?confidence-badge[^"]*"/)?.[0] || '' : '';
        const hasHighInNoEvidence = html.includes('🟢 高置信') &&
            (html.match(/confidence--high/g) || []).length >
            draft.sections.filter(s => (s.evidence_refs && s.evidence_refs.length) || (s.selected_refs && s.selected_refs.length)).length;
        return {
            hasConfidenceBadges: html.includes('confidence-badge'),
            hasHigh: html.includes('高置信'),
            hasMedium: html.includes('中置信'),
            hasLow: html.includes('低置信'),
            noExtraHigh: !hasHighInNoEvidence,
        };
    }""", MOCK_DRAFT)
    assert result["hasConfidenceBadges"], "Should have confidence badges"
    assert result["hasLow"], "Should have low confidence badges"
    assert result["noExtraHigh"], "No-evidence sections should not have high confidence"


# ---------- S29-PW-8: S28 风险裁决可见 ---------- #


def test_pw_08_feasibility_visible(page):
    """S29-PW-8: S28 风险裁决在报告中可见."""
    _goto_step_deck(page)
    result = page.evaluate("""(draft) => {
        const pd = window.ProposalDraft;
        const html = pd.renderDraft(draft);
        return {
            hasFeasSummary: html.includes('PIVOT'),
            hasFeasDisplay: html.includes('proposal-feasibility'),
            hasScore: html.includes('34/100'),
        };
    }""", MOCK_DRAFT)
    assert result["hasFeasSummary"], "Should show PIVOT verdict"
    assert result["hasFeasDisplay"], "Should have feasibility display"
    assert result["hasScore"], "Should show score"
