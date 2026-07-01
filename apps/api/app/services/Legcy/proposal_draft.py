"""Session 29: 开题报告草稿生成服务.

Generates a 12-section proposal draft with evidence binding.
Heuristic-only — no LLM calls needed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.schemas_feasibility import FeasibilityAssessment
from app.schemas_proposal_draft import (
    ConfidenceLevel,
    InnovationPoint,
    ProposalDraft,
    ProposalSection,
    REQUIRED_SECTIONS,
    SectionKey,
    WorkloadItem,
    WORKLOAD_TEMPLATE,
)


# ---------------------------------------------------------------------------
# Section title mapping
# ---------------------------------------------------------------------------

SECTION_TITLES: Dict[str, str] = {
    "topic_direction": "题目与研究方向",
    "background": "研究背景与意义",
    "literature_review": "国内外研究现状",
    "research_objectives": "研究目标",
    "research_content": "研究内容",
    "technical_approach": "技术路线",
    "dataset_experiment": "数据集与实验设计",
    "innovation": "预期创新点",
    "workload": "工作量拆解",
    "feasibility_risk": "可行性与风险",
    "reference_resources": "参考资源清单",
    "missing_evidence": "待补证据",
}


def _empty_section(section_id: str) -> ProposalSection:
    return ProposalSection(
        section_id=section_id,
        title=SECTION_TITLES.get(section_id, section_id),
        content="",
        evidence_refs=[],
        selected_refs=[],
        candidate_refs=[],
        missing_evidence=[],
        confidence=ConfidenceLevel.low,
    )


def _infer_confidence(
    evidence_refs: List[str],
    selected_refs: List[str],
    candidate_refs: List[str],
) -> ConfidenceLevel:
    if evidence_refs:
        return ConfidenceLevel.high
    if selected_refs:
        return ConfidenceLevel.medium
    if candidate_refs:
        return ConfidenceLevel.low
    return ConfidenceLevel.low


def _collect_all_evidence(
    sections: List[ProposalSection],
) -> tuple[List[str], List[str]]:
    """Return (bound_evidence, overall_missing) across all sections."""
    bound = set()
    missing = set()
    for s in sections:
        bound.update(s.evidence_refs)
        bound.update(s.selected_refs)
        missing.update(s.missing_evidence)
    return sorted(bound), sorted(missing)


def generate_proposal_draft(
    topic_title: str,
    sections: List[Dict[str, Any]],
    evidence_refs: List[str],
    selected_refs: List[str],
    candidate_refs: List[str],
    feasibility: Optional[Dict[str, Any]] = None,
) -> ProposalDraft:
    """Generate a full proposal draft with evidence binding.

    Args:
        topic_title: The topic title
        sections: Optional user-provided sections (list of dicts with section_id, content, etc.)
        evidence_refs: Bound evidence references
        selected_refs: Selected resource references
        candidate_refs: Candidate resource references
        feasibility: Optional feasibility assessment summary

    Returns:
        ProposalDraft with 12 sections, innovation points, workload items
    """
    # Build section map from user input
    user_sections: Dict[str, Dict[str, Any]] = {}
    for s in sections:
        sid = s.get("section_id", "")
        if sid:
            user_sections[sid] = s

    # Generate all 12 sections
    proposal_sections: List[ProposalSection] = []

    for section_key in REQUIRED_SECTIONS:
        if section_key in user_sections:
            us = user_sections[section_key]
            section = ProposalSection(
                section_id=section_key,
                title=SECTION_TITLES.get(section_key, section_key),
                content=us.get("content", ""),
                evidence_refs=us.get("evidence_refs", []),
                selected_refs=us.get("selected_refs", []),
                candidate_refs=us.get("candidate_refs", []),
                missing_evidence=us.get("missing_evidence", []),
                confidence=us.get("confidence", ConfidenceLevel.low),
            )
            # reference_resources always gets input evidence/candidate refs merged in
            if section_key == "reference_resources":
                section.evidence_refs = list(set(section.evidence_refs) | set(evidence_refs))
                section.selected_refs = list(set(section.selected_refs) | set(selected_refs))
                section.candidate_refs = list(set(section.candidate_refs) | set(candidate_refs))
                section.confidence = _infer_confidence(
                    section.evidence_refs, section.selected_refs, section.candidate_refs
                )
        else:
            section = _empty_section(section_key)
            # Auto-assign evidence to reference_resources section
            if section_key == "reference_resources":
                section.evidence_refs = list(evidence_refs)
                section.selected_refs = list(selected_refs)
                section.candidate_refs = list(candidate_refs)
                section.content = f"共 {len(evidence_refs)} 条 EvidenceRef，{len(selected_refs)} 条 SelectedResource，{len(candidate_refs)} 条 Candidate"
                section.confidence = _infer_confidence(evidence_refs, selected_refs, candidate_refs)

            # Auto-infer missing evidence
            if section_key == "missing_evidence":
                all_missing = set()
                for ps in proposal_sections:
                    all_missing.update(ps.missing_evidence)
                section.content = "；".join(sorted(all_missing)) if all_missing else "暂无缺口"
                section.missing_evidence = sorted(all_missing)

            # Auto-populate feasibility summary
            if section_key == "feasibility_risk" and feasibility:
                verdict = feasibility.get("verdict", "UNKNOWN")
                score = feasibility.get("overall_score", 0)
                section.content = f"可行性裁决: {verdict}，综合评分: {score}/100"
                vetoes = feasibility.get("hard_vetoes", [])
                triggered = [v for v in vetoes if v.get("triggered")]
                if triggered:
                    section.missing_evidence = [v.get("description", "") for v in triggered]
                    section.confidence = ConfidenceLevel.low
                else:
                    section.confidence = ConfidenceLevel.medium

            # Infer confidence
            if section.confidence == ConfidenceLevel.low and not section.evidence_refs:
                section.confidence = _infer_confidence(
                    section.evidence_refs, section.selected_refs, section.candidate_refs
                )

        proposal_sections.append(section)

    # Post-process: aggregate all missing_evidence into the missing_evidence section
    all_missing_agg: set = set()
    for ps in proposal_sections:
        if ps.section_id != "missing_evidence":
            all_missing_agg.update(ps.missing_evidence)
    missing_sec = next((ps for ps in proposal_sections if ps.section_id == "missing_evidence"), None)
    if missing_sec:
        existing = set(missing_sec.missing_evidence)
        merged = sorted(existing | all_missing_agg)
        missing_sec.missing_evidence = merged
        if not missing_sec.content or missing_sec.content == "暂无缺口":
            missing_sec.content = "；".join(merged) if merged else "暂无缺口"

    # Post-process: ensure every section has evidence or missing_evidence
    for ps in proposal_sections:
        if not ps.evidence_refs and not ps.selected_refs and not ps.missing_evidence:
            ps.missing_evidence = [f"{SECTION_TITLES.get(ps.section_id, ps.section_id)} 需补充证据"]
            if ps.confidence == ConfidenceLevel.high:
                ps.confidence = ConfidenceLevel.low

    # Build innovation points from innovation section or defaults
    innovation_points = []
    innovation_section = user_sections.get("innovation", {})
    if "innovation_points" in innovation_section:
        for ip in innovation_section["innovation_points"]:
            innovation_points.append(InnovationPoint(
                title=ip.get("title", ""),
                description=ip.get("description", ""),
                evidence_base=ip.get("evidence_base", "待补充"),
                risk=ip.get("risk", "待评估"),
            ))
    if not innovation_points:
        innovation_points = [
            InnovationPoint(
                title="面向特定场景的方法适配",
                description=f"针对「{topic_title}」进行工程化适配和实验验证",
                evidence_base="基于已收集的证据和方法论",
                risk="待实验验证效果",
            ),
            InnovationPoint(
                title="实验对比与消融分析",
                description="系统性对比现有方法并进行消融实验，量化各模块贡献",
                evidence_base="需要 baseline 代码和标准数据集",
                risk="数据集获取难度",
            ),
        ]

    # Build workload items
    workload_items = []
    workload_section = user_sections.get("workload", {})
    if "workload_items" in workload_section:
        for wi in workload_section["workload_items"]:
            workload_items.append(WorkloadItem(
                item=wi.get("item", ""),
                estimated_weeks=wi.get("estimated_weeks"),
            ))
    if not workload_items:
        workload_items = [WorkloadItem(item=w) for w in WORKLOAD_TEMPLATE]

    # Feasibility summary
    feas_summary = None
    if feasibility:
        verdict = feasibility.get("verdict", "UNKNOWN")
        score = feasibility.get("overall_score", 0)
        feas_summary = f"{verdict} ({score}/100)"

    bound_ev, overall_miss = _collect_all_evidence(proposal_sections)

    return ProposalDraft(
        topic_title=topic_title,
        sections=proposal_sections,
        innovation_points=innovation_points,
        workload_items=workload_items,
        feasibility_summary=feas_summary,
        bound_evidence=bound_ev,
        overall_missing=overall_miss,
    )
