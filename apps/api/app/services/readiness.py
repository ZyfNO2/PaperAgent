"""Session 32: 学校模板合规与导出前检查 service.

8 readiness dimensions:
  1. section_completeness — 所有必要章节非空
  2. evidence_binding — 至少部分章节绑定了 evidence
  3. reference_integrity — 参考资源中至少 1 条 verified
  4. school_template_fit — 模板要求的章节全部存在
  5. risk_disclosure — 可行性/风险章节非空
  6. workload_clarity — 工作量章节非空且条目 >= 3
  7. innovation_claim_safety — 无夸大创新词
  8. format_basic — 报告 Markdown 存在且长度 >= 200
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set

from app.schemas_readiness import (
    ReadinessDimension,
    ReadinessReport,
    ReadinessStatus,
    SchoolTemplate,
)

# ---------------------------------------------------------------------------
# Template → required section keys
# ---------------------------------------------------------------------------

_TEMPLATE_SECTIONS: Dict[str, Set[str]] = {
    "default": {
        "background", "literature_review", "research_content",
        "technical_approach", "workload", "reference_resources",
    },
    "engineering": {
        "background", "literature_review", "research_content",
        "technical_approach", "dataset_experiment", "workload",
        "feasibility_risk", "reference_resources",
    },
    "cv_ai": {
        "background", "literature_review", "research_content",
        "technical_approach", "dataset_experiment", "innovation",
        "workload", "feasibility_risk", "reference_resources",
    },
}

# All sections that can appear in a proposal draft
_ALL_SECTIONS = [
    "topic_direction", "background", "literature_review",
    "research_objectives", "research_content", "technical_approach",
    "dataset_experiment", "innovation", "workload",
    "feasibility_risk", "reference_resources", "missing_evidence",
]

# Hype / exaggerated innovation words
_INFLATED_WORDS = [
    "首创", "首次", "完全解决", "彻底解决", "革命性",
    "颠覆性", "国际领先", "填补空白", "零的突破",
]

# Hard-block checks (fail = export not allowed)
_HARD_BLOCK_DIMENSIONS = {
    "section_completeness", "reference_integrity",
    "school_template_fit", "innovation_claim_safety",
}


def _check_section_completeness(
    sections: List[dict],
) -> ReadinessDimension:
    """Check that all 12 proposal sections are present and non-empty."""
    present = {s.get("section_id", ""): s for s in sections}
    missing = []
    empty = []
    for key in _ALL_SECTIONS:
        if key not in present:
            missing.append(key)
        elif not (present[key].get("content") or "").strip():
            empty.append(key)

    if missing:
        return ReadinessDimension(
            dimension="section_completeness",
            status=ReadinessStatus.fail,
            message=f"缺少 {len(missing)} 个必要章节: {', '.join(missing)}",
            required_fix=f"补充章节: {', '.join(missing)}",
            section_refs=missing,
        )
    if empty:
        return ReadinessDimension(
            dimension="section_completeness",
            status=ReadinessStatus.warn,
            message=f"{len(empty)} 个章节内容为空: {', '.join(empty)}",
            required_fix=f"填充内容: {', '.join(empty)}",
            section_refs=empty,
        )
    return ReadinessDimension(
        dimension="section_completeness",
        status=ReadinessStatus.pass_,
        message="所有 12 个章节均存在且非空",
    )


def _check_evidence_binding(
    sections: List[dict],
) -> ReadinessDimension:
    """Check at least some sections have evidence_refs."""
    bound = [s.get("section_id", "") for s in sections if s.get("evidence_refs")]
    total = len(sections)
    ratio = len(bound) / total if total else 0
    if ratio < 0.1:
        return ReadinessDimension(
            dimension="evidence_binding",
            status=ReadinessStatus.fail,
            message=f"仅 {len(bound)}/{total} 个章节绑定了证据",
            required_fix="为更多章节添加 evidence_refs",
            section_refs=[s.get("section_id", "") for s in sections if not s.get("evidence_refs")],
        )
    if ratio < 0.4:
        return ReadinessDimension(
            dimension="evidence_binding",
            status=ReadinessStatus.warn,
            message=f"仅 {len(bound)}/{total} 个章节绑定了证据",
            required_fix="建议为更多章节添加 evidence_refs",
        )
    return ReadinessDimension(
        dimension="evidence_binding",
        status=ReadinessStatus.pass_,
        message=f"{len(bound)}/{total} 个章节绑定了证据",
    )


def _check_reference_integrity(
    citations: List[dict],
) -> ReadinessDimension:
    """Check at least 1 citation is verified or accepted."""
    if not citations:
        return ReadinessDimension(
            dimension="reference_integrity",
            status=ReadinessStatus.fail,
            message="参考资源为空",
            required_fix="添加至少一条参考资源",
            section_refs=["reference_resources"],
        )
    verified = [c for c in citations if c.get("review_status") in ("accepted", "core", "background")]
    if not verified:
        return ReadinessDimension(
            dimension="reference_integrity",
            status=ReadinessStatus.fail,
            message=f"所有 {len(citations)} 条参考资源均未验证",
            required_fix="至少验证一条参考资源",
            section_refs=["reference_resources"],
        )
    return ReadinessDimension(
        dimension="reference_integrity",
        status=ReadinessStatus.pass_,
        message=f"{len(verified)}/{len(citations)} 条参考资源已验证",
    )


def _check_school_template_fit(
    sections: List[dict],
    template_key: str,
) -> ReadinessDimension:
    """Check template-specific required sections exist."""
    required = _TEMPLATE_SECTIONS.get(template_key, _TEMPLATE_SECTIONS["default"])
    present = {s.get("section_id", "") for s in sections}
    missing = required - present
    if missing:
        return ReadinessDimension(
            dimension="school_template_fit",
            status=ReadinessStatus.fail,
            message=f"模板 '{template_key}' 要求的章节缺失: {', '.join(sorted(missing))}",
            required_fix=f"补充模板要求章节: {', '.join(sorted(missing))}",
            section_refs=sorted(missing),
        )
    return ReadinessDimension(
        dimension="school_template_fit",
        status=ReadinessStatus.pass_,
        message=f"模板 '{template_key}' 要求的 {len(required)} 个章节全部存在",
    )


def _check_risk_disclosure(
    sections: List[dict],
) -> ReadinessDimension:
    """Check feasibility_risk section is non-empty."""
    risk = [s for s in sections if s.get("section_id") == "feasibility_risk"]
    if not risk or not (risk[0].get("content") or "").strip():
        return ReadinessDimension(
            dimension="risk_disclosure",
            status=ReadinessStatus.fail,
            message="可行性与风险章节为空或缺失",
            required_fix="补充可行性与风险分析",
            section_refs=["feasibility_risk"],
        )
    return ReadinessDimension(
        dimension="risk_disclosure",
        status=ReadinessStatus.pass_,
        message="可行性与风险章节已填写",
    )


def _check_workload_clarity(
    sections: List[dict],
) -> ReadinessDimension:
    """Check workload section is non-empty and has >= 3 items."""
    wl = [s for s in sections if s.get("section_id") == "workload"]
    if not wl:
        return ReadinessDimension(
            dimension="workload_clarity",
            status=ReadinessStatus.fail,
            message="工作量章节缺失",
            required_fix="添加工作量拆解章节",
            section_refs=["workload"],
        )
    content = (wl[0].get("content") or "").strip()
    if not content:
        return ReadinessDimension(
            dimension="workload_clarity",
            status=ReadinessStatus.fail,
            message="工作量章节内容为空",
            required_fix="填充工作量拆解内容",
            section_refs=["workload"],
        )
    # Count items: lines starting with - or * or digit
    items = [l for l in content.split("\n") if re.match(r"^\s*[-*\d]", l)]
    if len(items) < 3:
        return ReadinessDimension(
            dimension="workload_clarity",
            status=ReadinessStatus.warn,
            message=f"工作量仅 {len(items)} 项 (建议 >= 3)",
            required_fix="补充更多工作量条目",
            section_refs=["workload"],
        )
    return ReadinessDimension(
        dimension="workload_clarity",
        status=ReadinessStatus.pass_,
        message=f"工作量 {len(items)} 项",
    )


def _check_innovation_claim_safety(
    sections: List[dict],
) -> ReadinessDimension:
    """Check no exaggerated innovation claims."""
    innov = [s for s in sections if s.get("section_id") == "innovation"]
    if not innov:
        return ReadinessDimension(
            dimension="innovation_claim_safety",
            status=ReadinessStatus.fail,
            message="创新点章节缺失",
            required_fix="添加创新点章节",
            section_refs=["innovation"],
        )
    content = (innov[0].get("content") or "").strip()
    if not content:
        return ReadinessDimension(
            dimension="innovation_claim_safety",
            status=ReadinessStatus.fail,
            message="创新点章节内容为空",
            required_fix="填充创新点内容",
            section_refs=["innovation"],
        )
    found_hype = [w for w in _INFLATED_WORDS if w in content]
    if found_hype:
        return ReadinessDimension(
            dimension="innovation_claim_safety",
            status=ReadinessStatus.fail,
            message=f"创新点含夸大用词: {', '.join(found_hype)}",
            required_fix=f"移除夸大用词: {', '.join(found_hype)}",
            section_refs=["innovation"],
        )
    return ReadinessDimension(
        dimension="innovation_claim_safety",
        status=ReadinessStatus.pass_,
        message="创新点用词安全",
    )


def _check_format_basic(
    proposal_markdown: Optional[str],
) -> ReadinessDimension:
    """Check report markdown exists and is reasonable length."""
    if not proposal_markdown:
        return ReadinessDimension(
            dimension="format_basic",
            status=ReadinessStatus.fail,
            message="报告 Markdown 为空",
            required_fix="生成报告 Markdown",
        )
    if len(proposal_markdown) < 200:
        return ReadinessDimension(
            dimension="format_basic",
            status=ReadinessStatus.warn,
            message=f"报告 Markdown 仅 {len(proposal_markdown)} 字符 (建议 >= 200)",
            required_fix="充实报告内容",
        )
    return ReadinessDimension(
        dimension="format_basic",
        status=ReadinessStatus.pass_,
        message=f"报告 Markdown {len(proposal_markdown)} 字符",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_readiness(
    sections: List[dict],
    citations: List[dict],
    template_key: str = "default",
    proposal_markdown: Optional[str] = None,
    project_id: str = "",
) -> ReadinessReport:
    """Run all 8 readiness dimensions and return a report."""
    dims = [
        _check_section_completeness(sections),
        _check_evidence_binding(sections),
        _check_reference_integrity(citations),
        _check_school_template_fit(sections, template_key),
        _check_risk_disclosure(sections),
        _check_workload_clarity(sections),
        _check_innovation_claim_safety(sections),
        _check_format_basic(proposal_markdown),
    ]

    hard_blocks = [
        d.dimension for d in dims
        if d.dimension in _HARD_BLOCK_DIMENSIONS and d.status == ReadinessStatus.fail
    ]

    # Overall status: worst of all dimensions
    statuses = [d.status for d in dims]
    if ReadinessStatus.fail in statuses:
        overall = ReadinessStatus.fail
    elif ReadinessStatus.warn in statuses:
        overall = ReadinessStatus.warn
    else:
        overall = ReadinessStatus.pass_

    export_allowed = overall != ReadinessStatus.fail

    return ReadinessReport(
        project_id=project_id,
        template_key=SchoolTemplate(template_key) if template_key in SchoolTemplate.__members__.values() else SchoolTemplate.default,
        overall_status=overall,
        dimensions=dims,
        hard_blocks=hard_blocks,
        export_allowed=export_allowed,
    )
