"""Session 30: 委员会复核服务 — 5 视角 heuristic review engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.schemas_review import (
    ReviewHistory,
    ReviewIssue,
    ReviewPerspective,
    ReviewRequest,
    ReviewRound,
    ReviewVerdict,
    RevisionAction,
    RevisionActionType,
    Severity,
    can_verdict_pass,
)


# ---------------------------------------------------------------------------
# In-memory store (per-session)
# ---------------------------------------------------------------------------

_review_history: Dict[str, ReviewHistory] = {}


# ---------------------------------------------------------------------------
# Issue generators per perspective
# ---------------------------------------------------------------------------


def _check_advisor(sections: List[Dict[str, Any]], feasibility: Optional[Dict[str, Any]]) -> List[ReviewIssue]:
    """导师视角: 题目是否可控."""
    issues: List[ReviewIssue] = []
    topic_sec = next((s for s in sections if s.get("section_id") == "topic_direction"), None)
    scope_sec = next((s for s in sections if s.get("section_id") == "research_content"), None)

    if not topic_sec or not topic_sec.get("content"):
        issues.append(ReviewIssue(
            issue_id="adv_01",
            perspective=ReviewPerspective.advisor,
            severity=Severity.fatal,
            section_id="topic_direction",
            message="缺少研究题目",
            suggested_fix="填写研究题目与方向",
            evidence_refs=[],
        ))

    if scope_sec and not scope_sec.get("evidence_refs") and not scope_sec.get("selected_refs"):
        issues.append(ReviewIssue(
            issue_id="adv_02",
            perspective=ReviewPerspective.advisor,
            severity=Severity.medium,
            section_id="research_content",
            message="研究内容缺少证据支撑，范围可能不可控",
            suggested_fix="为研究内容添加 EvidenceRef 或 SelectedResource",
            evidence_refs=[],
        ))

    return issues


def _check_method(sections: List[Dict[str, Any]], feasibility: Optional[Dict[str, Any]]) -> List[ReviewIssue]:
    """方法视角: 技术路线是否说得通."""
    issues: List[ReviewIssue] = []
    tech_sec = next((s for s in sections if s.get("section_id") == "technical_approach"), None)

    if not tech_sec or not tech_sec.get("content"):
        issues.append(ReviewIssue(
            issue_id="met_01",
            perspective=ReviewPerspective.method,
            severity=Severity.high,
            section_id="technical_approach",
            message="技术路线为空",
            suggested_fix="描述具体方法和模型",
            evidence_refs=[],
        ))
    elif not tech_sec.get("evidence_refs") and not tech_sec.get("selected_refs"):
        issues.append(ReviewIssue(
            issue_id="met_02",
            perspective=ReviewPerspective.method,
            severity=Severity.medium,
            section_id="technical_approach",
            message="技术路线无证据支撑",
            suggested_fix="添加相关论文的 EvidenceRef",
            evidence_refs=[],
        ))

    return issues


def _check_experiment(sections: List[Dict[str, Any]], feasibility: Optional[Dict[str, Any]]) -> List[ReviewIssue]:
    """实验视角: 数据、baseline、指标是否齐."""
    issues: List[ReviewIssue] = []
    ds_sec = next((s for s in sections if s.get("section_id") == "dataset_experiment"), None)

    # Check feasibility vetoes for dataset/baseline
    if feasibility:
        vetoes = feasibility.get("hard_vetoes", [])
        for v in vetoes:
            if not v.get("triggered"):
                continue
            rule = v.get("rule", "")
            if rule == "no_dataset":
                issues.append(ReviewIssue(
                    issue_id="exp_01",
                    perspective=ReviewPerspective.experiment,
                    severity=Severity.fatal,
                    section_id="dataset_experiment",
                    message="缺少数据集，无法开展实验",
                    suggested_fix="确认可访问的公开数据集",
                    evidence_refs=[],
                ))
            elif rule == "no_baseline":
                issues.append(ReviewIssue(
                    issue_id="exp_02",
                    perspective=ReviewPerspective.experiment,
                    severity=Severity.fatal,
                    section_id="dataset_experiment",
                    message="缺少 baseline，无法进行对比实验",
                    suggested_fix="找到 baseline 论文及代码",
                    evidence_refs=[],
                ))
            elif rule == "no_experiment_plan":
                issues.append(ReviewIssue(
                    issue_id="exp_03",
                    perspective=ReviewPerspective.experiment,
                    severity=Severity.high,
                    section_id="dataset_experiment",
                    message="缺少实验方案",
                    suggested_fix="设计对比实验和消融实验",
                    evidence_refs=[],
                ))

    # Also check if dataset_experiment section lacks evidence
    if ds_sec and not ds_sec.get("evidence_refs") and not ds_sec.get("selected_refs"):
        if not any(i.issue_id.startswith("exp_") for i in issues):
            issues.append(ReviewIssue(
                issue_id="exp_04",
                perspective=ReviewPerspective.experiment,
                severity=Severity.high,
                section_id="dataset_experiment",
                message="数据集与实验设计缺少证据",
                suggested_fix="添加数据集 EvidenceRef",
                evidence_refs=[],
            ))

    return issues


def _check_writing(sections: List[Dict[str, Any]], feasibility: Optional[Dict[str, Any]]) -> List[ReviewIssue]:
    """写作视角: 报告结构是否像开题报告."""
    issues: List[ReviewIssue] = []
    required_ids = {"topic_direction", "background", "literature_review", "research_objectives",
                    "research_content", "technical_approach", "dataset_experiment", "innovation"}
    present = {s.get("section_id") for s in sections}
    missing = required_ids - present
    for mid in sorted(missing):
        issues.append(ReviewIssue(
            issue_id=f"wrt_{mid}",
            perspective=ReviewPerspective.writing,
            severity=Severity.medium,
            section_id=mid,
            message=f"缺少必要章节: {mid}",
            suggested_fix=f"补充 {mid} 内容",
            evidence_refs=[],
        ))

    # Check if any section is empty
    for s in sections:
        sid = s.get("section_id", "")
        if not s.get("content") and sid not in missing:
            issues.append(ReviewIssue(
                issue_id=f"wrt_empty_{sid}",
                perspective=ReviewPerspective.writing,
                severity=Severity.low,
                section_id=sid,
                message=f"章节 {sid} 内容为空",
                suggested_fix=f"补充 {sid} 内容",
                evidence_refs=[],
            ))

    return issues


def _check_risk(sections: List[Dict[str, Any]], feasibility: Optional[Dict[str, Any]]) -> List[ReviewIssue]:
    """风险视角: 是否存在毕业风险."""
    issues: List[ReviewIssue] = []

    if feasibility:
        verdict = feasibility.get("verdict", "")
        score = feasibility.get("overall_score", 50)

        if verdict in ("PIVOT", "PARK", "STOP"):
            issues.append(ReviewIssue(
                issue_id="risk_01",
                perspective=ReviewPerspective.risk,
                severity=Severity.fatal if verdict == "STOP" else Severity.high,
                section_id="feasibility_risk",
                message=f"可行性裁决: {verdict} (评分 {score}/100)",
                suggested_fix="参考 PIVOT 路线或补充证据",
                evidence_refs=[],
            ))

    # Check for missing evidence in multiple sections
    sections_no_evidence = [
        s.get("section_id") for s in sections
        if not s.get("evidence_refs") and not s.get("selected_refs")
        and s.get("section_id") not in ("missing_evidence",)
    ]
    if len(sections_no_evidence) >= 5:
        issues.append(ReviewIssue(
            issue_id="risk_02",
            perspective=ReviewPerspective.risk,
            severity=Severity.high,
            section_id="missing_evidence",
            message=f"有 {len(sections_no_evidence)} 个章节缺少证据支撑",
            suggested_fix="补充更多 EvidenceRef",
            evidence_refs=[],
        ))

    return issues


# ---------------------------------------------------------------------------
# Review engine
# ---------------------------------------------------------------------------


def _generate_actions(issues: List[ReviewIssue]) -> tuple[List[RevisionAction], List[RevisionAction]]:
    """Generate required and optional revision actions from issues."""
    required: List[RevisionAction] = []
    optional: List[RevisionAction] = []

    for issue in issues:
        if issue.severity in (Severity.fatal, Severity.high):
            required.append(RevisionAction(
                action_id=f"act_{issue.issue_id}",
                action_type=RevisionActionType.accept_fix,
                target_issue_id=issue.issue_id,
                description=f"处理: {issue.message} → {issue.suggested_fix}",
                section_id=issue.section_id,
            ))
        else:
            optional.append(RevisionAction(
                action_id=f"act_{issue.issue_id}",
                action_type=RevisionActionType.accept_fix,
                target_issue_id=issue.issue_id,
                description=f"可选: {issue.message} → {issue.suggested_fix}",
                section_id=issue.section_id,
            ))

    return required, optional


def _determine_verdict(issues: List[ReviewIssue]) -> ReviewVerdict:
    """Determine overall verdict based on issues."""
    has_fatal = any(i.severity == Severity.fatal for i in issues)
    has_high = any(i.severity == Severity.high for i in issues)
    has_medium = any(i.severity == Severity.medium for i in issues)

    if has_fatal:
        return ReviewVerdict.revise
    if has_high:
        return ReviewVerdict.conditional_pass
    if has_medium:
        return ReviewVerdict.conditional_pass
    return ReviewVerdict.pass_


def _collect_evidence_gaps(issues: List[ReviewIssue]) -> List[str]:
    """Collect all evidence gaps from issues."""
    gaps: List[str] = []
    for issue in issues:
        if issue.section_id and not issue.evidence_refs:
            gaps.append(f"{issue.section_id}: {issue.suggested_fix}")
    return sorted(set(gaps))


def _build_revision_prompt(issues: List[ReviewIssue]) -> str:
    """Build next revision prompt."""
    fatal = [i for i in issues if i.severity == Severity.fatal]
    high = [i for i in issues if i.severity == Severity.high]

    if fatal:
        return f"有 {len(fatal)} 个致命问题需处理: " + "; ".join(i.message for i in fatal)
    if high:
        return f"有 {len(high)} 个高优先级问题: " + "; ".join(i.message for i in high)
    return "建议处理剩余问题后重新复核"


def run_review(request: ReviewRequest) -> ReviewRound:
    """Run a single review round on a proposal draft."""
    all_issues: List[ReviewIssue] = []

    # Run all 5 perspectives
    all_issues.extend(_check_advisor(request.sections, request.feasibility))
    all_issues.extend(_check_method(request.sections, request.feasibility))
    all_issues.extend(_check_experiment(request.sections, request.feasibility))
    all_issues.extend(_check_writing(request.sections, request.feasibility))
    all_issues.extend(_check_risk(request.sections, request.feasibility))

    # Apply revision actions (mark issues as resolved)
    for action in request.revision_actions:
        target_id = action.get("issue_id", "")
        for issue in all_issues:
            if issue.issue_id == target_id:
                issue.resolved = True

    # Generate actions, verdict, gaps
    required, optional = _generate_actions(all_issues)
    verdict = _determine_verdict(all_issues)
    gaps = _collect_evidence_gaps(all_issues)
    prompt = _build_revision_prompt(all_issues)

    # Build round
    topic = request.topic_title
    history = _review_history.get(topic)
    if not history:
        history = ReviewHistory(topic_title=topic)
        _review_history[topic] = history

    round_num = len(history.rounds) + 1
    round_data = ReviewRound(
        round_id=round_num,
        verdict=verdict,
        issues=all_issues,
        required_actions=required,
        optional_actions=optional,
        evidence_gaps=gaps,
        next_revision_prompt=prompt,
    )

    history.rounds.append(round_data)
    return round_data


def get_review_history(topic_title: str) -> ReviewHistory:
    """Get review history for a topic."""
    return _review_history.get(topic_title, ReviewHistory(topic_title=topic_title))


def clear_review_history(topic_title: str) -> None:
    """Clear review history for a topic (for testing)."""
    _review_history.pop(topic_title, None)
