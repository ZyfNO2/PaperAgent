"""Session 29: 开题报告草稿后端测试.

覆盖 SOP §5 后端 8 条:
1. 报告 12 节齐全
2. 每节有 evidence_refs 或 missing_evidence
3. 无证据段落 confidence 不得 high
4. 工作量不少于 5 项
5. 创新点不少于 2 项且无夸大词
6. 参考资源来自 Candidate/Selected/Evidence
7. 不编造 URL
8. S28 裁决进入报告
"""

from __future__ import annotations

import pytest
from app.schemas_proposal_draft import (
    ConfidenceLevel,
    ProposalDraft,
    ProposalSection,
    REQUIRED_SECTIONS,
    validate_proposal,
)
from app.services.proposal_draft import generate_proposal_draft


# ------------------------------------------------------------------- #
# helpers
# ------------------------------------------------------------------- #

MOCK_EVIDENCE = ["ev_1", "ev_2", "ev_3"]
MOCK_SELECTED = ["sel_1"]
MOCK_CANDIDATE = ["cand_1", "cand_2"]

MOCK_FEASIBILITY = {
    "verdict": "PIVOT",
    "overall_score": 34,
    "hard_vetoes": [
        {"rule": "no_baseline", "triggered": True, "description": "无 baseline"},
        {"rule": "no_experiment_plan", "triggered": True, "description": "无实验"},
    ],
}


def _make_sections_with_evidence():
    """Build sections with evidence for most, missing for some."""
    return [
        {"section_id": "topic_direction", "content": "钢铁缺陷检测研究", "evidence_refs": ["ev_1"]},
        {"section_id": "background", "content": "工业质检很重要", "evidence_refs": ["ev_1", "ev_2"]},
        {"section_id": "literature_review", "content": "现有方法综述", "selected_refs": ["sel_1"]},
        {"section_id": "research_objectives", "content": "提高检测精度", "evidence_refs": ["ev_2"]},
        {"section_id": "research_content", "content": "改进检测模型", "evidence_refs": ["ev_3"]},
        {"section_id": "technical_approach", "content": "使用 ResNet", "evidence_refs": ["ev_2"]},
        {"section_id": "dataset_experiment", "content": "NEU 数据集", "evidence_refs": ["ev_1"]},
        {"section_id": "innovation", "content": "轻量化改进", "evidence_refs": ["ev_3"]},
        {"section_id": "workload", "content": "7 个月工作"},
        {"section_id": "feasibility_risk", "content": "中等风险"},
        {"section_id": "reference_resources", "content": "5 条参考"},
        {"section_id": "missing_evidence", "content": "缺 baseline"},
    ]


# ------------------------------------------------------------------- #
# S29-1: 报告 12 节齐全
# ------------------------------------------------------------------- #


class TestTwelveSections:
    def test_empty_input_still_produces_12(self):
        """S29-1a: 即使无输入也生成 12 节."""
        draft = generate_proposal_draft(
            topic_title="Test Topic",
            sections=[],
            evidence_refs=[],
            selected_refs=[],
            candidate_refs=[],
        )
        section_ids = {s.section_id for s in draft.sections}
        assert section_ids == set(REQUIRED_SECTIONS)
        assert len(draft.sections) == 12

    def test_partial_sections_still_12(self):
        """S29-1b: 部分输入也补全到 12 节."""
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=[{"section_id": "topic_direction", "content": "题目"}],
            evidence_refs=["ev_1"],
            selected_refs=[],
            candidate_refs=[],
        )
        assert len(draft.sections) == 12


# ------------------------------------------------------------------- #
# S29-2: 每节有 evidence_refs 或 missing_evidence
# ------------------------------------------------------------------- #


class TestEvidenceOrMissing:
    def test_reference_resources_auto_populated(self):
        """S29-2: reference_resources 自动填充 evidence/selected/candidate."""
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=_make_sections_with_evidence(),
            evidence_refs=MOCK_EVIDENCE,
            selected_refs=MOCK_SELECTED,
            candidate_refs=MOCK_CANDIDATE,
        )
        ref_section = next(s for s in draft.sections if s.section_id == "reference_resources")
        assert len(ref_section.evidence_refs) >= 1 or len(ref_section.selected_refs) >= 1

    def test_missing_section_auto_populated(self):
        """S29-2b: missing_evidence 节自动聚合所有缺口."""
        sections = _make_sections_with_evidence()
        # Add a missing evidence to workload section
        sections[8]["missing_evidence"] = ["Baseline 论文"]
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=sections,
            evidence_refs=MOCK_EVIDENCE,
            selected_refs=MOCK_SELECTED,
            candidate_refs=MOCK_CANDIDATE,
        )
        missing_sec = next(s for s in draft.sections if s.section_id == "missing_evidence")
        assert len(missing_sec.missing_evidence) >= 1 or "暂无缺口" in missing_sec.content


# ------------------------------------------------------------------- #
# S29-3: 无证据段落 confidence 不得 high
# ------------------------------------------------------------------- #


class TestConfidenceNotHigh:
    def test_no_evidence_cannot_be_high(self):
        """S29-3: 无 evidence_refs → confidence 不能是 high."""
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=[
                {"section_id": "topic_direction", "content": "题目", "evidence_refs": []},
            ],
            evidence_refs=[],
            selected_refs=[],
            candidate_refs=[],
        )
        for s in draft.sections:
            if not s.evidence_refs and not s.selected_refs:
                assert s.confidence != ConfidenceLevel.high, \
                    f"Section '{s.section_id}' has no evidence but high confidence"

    def test_candidate_only_is_low(self):
        """S29-3b: 只有 candidate_refs → confidence 不能是 high."""
        sections = [
            {"section_id": "topic_direction", "content": "题目", "candidate_refs": ["cand_1"]},
        ]
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=sections,
            evidence_refs=[],
            selected_refs=[],
            candidate_refs=["cand_1"],
        )
        topic = next(s for s in draft.sections if s.section_id == "topic_direction")
        assert topic.confidence in (ConfidenceLevel.low, ConfidenceLevel.medium)


# ------------------------------------------------------------------- #
# S29-4: 工作量不少于 5 项
# ------------------------------------------------------------------- #


class TestWorkloadMinimum:
    def test_default_workload_has_7(self):
        """S29-4: 默认工作量 7 项."""
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=[],
            evidence_refs=[],
            selected_refs=[],
            candidate_refs=[],
        )
        assert len(draft.workload_items) >= 5

    def test_custom_workload_preserved(self):
        """S29-4b: 自定义工作量保留."""
        sections = [{"section_id": "workload", "workload_items": [
            {"item": "A"}, {"item": "B"}, {"item": "C"},
            {"item": "D"}, {"item": "E"}, {"item": "F"},
        ]}]
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=sections,
            evidence_refs=[],
            selected_refs=[],
            candidate_refs=[],
        )
        assert len(draft.workload_items) == 6


# ------------------------------------------------------------------- #
# S29-5: 创新点不少于 2 项且无夸大词
# ------------------------------------------------------------------- #


class TestInnovationNoInflation:
    def test_default_has_2_innovations(self):
        """S29-5: 默认 2 个创新点."""
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=[],
            evidence_refs=[],
            selected_refs=[],
            candidate_refs=[],
        )
        assert len(draft.innovation_points) >= 2

    def test_no_inflated_words(self):
        """S29-5b: 创新点无夸大词."""
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=[],
            evidence_refs=[],
            selected_refs=[],
            candidate_refs=[],
        )
        errors = validate_proposal(draft)
        inflation_errors = [e for e in errors if "inflated" in e.lower() or "夸大" in e]
        assert len(inflation_errors) == 0, f"Inflation errors: {inflation_errors}"


# ------------------------------------------------------------------- #
# S29-6: 参考资源来自 Candidate/Selected/Evidence
# ------------------------------------------------------------------- #


class TestReferencesFromExisting:
    def test_ref_resources_match_input(self):
        """S29-6: 参考资源节的 refs 来自输入."""
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=[],
            evidence_refs=MOCK_EVIDENCE,
            selected_refs=MOCK_SELECTED,
            candidate_refs=MOCK_CANDIDATE,
        )
        ref_sec = next(s for s in draft.sections if s.section_id == "reference_resources")
        assert set(ref_sec.evidence_refs) == set(MOCK_EVIDENCE)
        assert set(ref_sec.selected_refs) == set(MOCK_SELECTED)
        assert set(ref_sec.candidate_refs) == set(MOCK_CANDIDATE)


# ------------------------------------------------------------------- #
# S29-7: 不编造 URL
# ------------------------------------------------------------------- #


class TestNoFabricatedURLs:
    def test_evidence_refs_are_identifiers(self):
        """S29-7: evidence_refs 是标识符，不是编造的 URL."""
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=[],
            evidence_refs=MOCK_EVIDENCE,
            selected_refs=MOCK_SELECTED,
            candidate_refs=MOCK_CANDIDATE,
        )
        assert set(draft.bound_evidence) == set(MOCK_EVIDENCE + MOCK_SELECTED)


# ------------------------------------------------------------------- #
# S29-8: S28 裁决进入报告
# ------------------------------------------------------------------- #


class TestFeasibilityInReport:
    def test_feasibility_summary_in_draft(self):
        """S29-8a: S28 裁决 summary 进入报告."""
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=[],
            evidence_refs=MOCK_EVIDENCE,
            selected_refs=[],
            candidate_refs=[],
            feasibility=MOCK_FEASIBILITY,
        )
        assert draft.feasibility_summary is not None
        assert "PIVOT" in draft.feasibility_summary

    def test_feasibility_vetoes_in_section(self):
        """S29-8b: 硬性否决项进入 feasibility_risk 节."""
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=[],
            evidence_refs=MOCK_EVIDENCE,
            selected_refs=[],
            candidate_refs=[],
            feasibility=MOCK_FEASIBILITY,
        )
        feas_sec = next(s for s in draft.sections if s.section_id == "feasibility_risk")
        assert len(feas_sec.missing_evidence) >= 1 or "PIVOT" in feas_sec.content


# ------------------------------------------------------------------- #
# Validate helper
# ------------------------------------------------------------------- #


class TestValidateProposal:
    def test_valid_draft_passes(self):
        """validate_proposal with good draft → no errors."""
        draft = generate_proposal_draft(
            topic_title="Test",
            sections=_make_sections_with_evidence(),
            evidence_refs=MOCK_EVIDENCE,
            selected_refs=MOCK_SELECTED,
            candidate_refs=MOCK_CANDIDATE,
        )
        errors = validate_proposal(draft)
        assert errors == [], f"Unexpected errors: {errors}"
