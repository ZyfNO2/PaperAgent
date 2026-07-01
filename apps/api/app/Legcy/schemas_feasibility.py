"""Session 28: 可行性风险裁决与 PIVOT 路线 (SOP §2-5).

7 维风险评估：EvidenceSupport, DataAvailability, BaselineReadiness,
ExperimentalClarity, ScopeControl, ResourceFit, NoveltyDifferentiation

裁决：GO / CONDITIONAL / PIVOT / PARK / STOP
硬性否决规则：无数据集→不得GO；无指标→不得GO；无baseline→不得GO 等
PIVOT 路线：保守 / 平衡 / 进取，至少三条
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------- 风险维度 ---------- #

RiskLevel = Literal["low", "medium", "high", "fatal"]


class RiskDimension(BaseModel):
    """单个风险维度."""

    model_config = ConfigDict(extra="forbid")

    dimension: str = Field(description="维度名")
    score: int = Field(ge=0, le=100, description="0-100 分")
    level: RiskLevel
    evidence_refs: list[str] = Field(default_factory=list, description="支撑该维度的 EvidenceRef ID")
    reason: str = Field(default="")
    suggestion: str = Field(default="")
    missing_evidence: list[str] = Field(default_factory=list, description="该维度缺少的证据描述")


# ---------- 裁决 ---------- #

FeasibilityVerdict = Literal["GO", "CONDITIONAL", "PIVOT", "PARK", "STOP"]


class HardVeto(BaseModel):
    """硬性否决项."""

    model_config = ConfigDict(extra="forbid")

    rule: str = Field(description="否决规则名")
    description: str = Field(description="否决规则描述")
    triggered: bool = Field(default=False)
    blocked_verdicts: list[FeasibilityVerdict] = Field(default_factory=list)


# ---------- PIVOT 路线 ---------- #

PivotType = Literal["conservative", "balanced", "aggressive"]


class PivotRoute(BaseModel):
    """PIVOT 路线建议."""

    model_config = ConfigDict(extra="forbid")

    route_type: PivotType
    new_topic: str = Field(description="建议的新题目")
    changed_keywords: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list, description="需要补充的证据")
    expected_workload: str = Field(default="", description="预期工作量")
    risk_delta: str = Field(default="", description="风险变化")
    recommended_for: str = Field(default="", description="适合谁/什么情况")


# ---------- 裁决结果 ---------- #

class FeasibilityAssessment(BaseModel):
    """可行性评估完整结果."""

    model_config = ConfigDict(extra="forbid")

    dimensions: list[RiskDimension] = Field(description="7 维风险评估")
    overall_score: int = Field(ge=0, le=100, description="综合评分")
    verdict: FeasibilityVerdict
    hard_vetoes: list[HardVeto] = Field(default_factory=list)
    pivot_routes: list[PivotRoute] = Field(default_factory=list, description="PIVOT 时至少三条路线")
    summary: str = Field(default="")
    bound_evidence: list[str] = Field(default_factory=list, description="绑定的所有 EvidenceRef ID")
    missing_evidence: list[str] = Field(default_factory=list, description="全局缺口")


# ---------- 输入 ---------- #

class FeasibilityInput(BaseModel):
    """可行性评估输入."""

    model_config = ConfigDict(extra="forbid")

    topic_title: str = Field(min_length=1)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list, description="已晋升的 EvidenceRef 列表")
    candidate_count: int = Field(default=0, description="候选资源总数")
    has_dataset: bool = Field(default=False)
    has_baseline: bool = Field(default=False)
    has_metrics: bool = Field(default=False)
    has_experiment_plan: bool = Field(default=False)
    has_verified_urls: bool = Field(default=False)
    evidence_count: int = Field(default=0, description="EvidenceRef 数量")
    min_evidence_threshold: int = Field(default=3, description="最低证据阈值")


# ---------- 硬性否决规则 ---------- #

HARD_VETO_RULES: list[dict[str, Any]] = [
    {
        "rule": "no_dataset",
        "description": "无数据集不得 GO",
        "condition": lambda inp: not inp.has_dataset,
        "blocked_verdicts": ["GO"],
    },
    {
        "rule": "no_metrics",
        "description": "无评价指标不得 GO",
        "condition": lambda inp: not inp.has_metrics,
        "blocked_verdicts": ["GO"],
    },
    {
        "rule": "no_baseline",
        "description": "无 baseline/repo/可比较方法不得 GO",
        "condition": lambda inp: not inp.has_baseline,
        "blocked_verdicts": ["GO"],
    },
    {
        "rule": "no_experiment_plan",
        "description": "只有文字方案无实验不得 GO",
        "condition": lambda inp: not inp.has_experiment_plan,
        "blocked_verdicts": ["GO"],
    },
    {
        "rule": "no_verified_urls",
        "description": "URL 全部未验证不得 GO",
        "condition": lambda inp: not inp.has_verified_urls,
        "blocked_verdicts": ["GO"],
    },
    {
        "rule": "insufficient_evidence",
        "description": "EvidenceRef 少于最低阈值不得 GO",
        "condition": lambda inp: inp.evidence_count < inp.min_evidence_threshold,
        "blocked_verdicts": ["GO"],
    },
]


def check_hard_vetoes(inp: FeasibilityInput) -> list[HardVeto]:
    """检查硬性否决规则."""
    vetoes: list[HardVeto] = []
    for rule in HARD_VETO_RULES:
        triggered = rule["condition"](inp)
        vetoes.append(HardVeto(
            rule=rule["rule"],
            description=rule["description"],
            triggered=triggered,
            blocked_verdicts=rule["blocked_verdicts"],
        ))
    return vetoes


def _assess_dimensions(inp: FeasibilityInput) -> list[RiskDimension]:
    """评估 7 个风险维度."""
    ev_ids = [e.get("evidence_id", "") for e in inp.evidence_refs]

    dims: list[RiskDimension] = []

    # 1. EvidenceSupport
    ev_score = min(100, inp.evidence_count * 20)
    ev_level: RiskLevel = "fatal" if ev_score < 20 else "high" if ev_score < 40 else "medium" if ev_score < 70 else "low"
    dims.append(RiskDimension(
        dimension="EvidenceSupport",
        score=ev_score,
        level=ev_level,
        evidence_refs=ev_ids,
        reason=f"{inp.evidence_count} EvidenceRef(s)" + (" (below threshold)" if inp.evidence_count < inp.min_evidence_threshold else ""),
        suggestion="Collect more evidence" if inp.evidence_count < inp.min_evidence_threshold else "Sufficient",
        missing_evidence=[] if inp.evidence_count >= inp.min_evidence_threshold else [f"Need {inp.min_evidence_threshold - inp.evidence_count} more EvidenceRef(s)"],
    ))

    # 2. DataAvailability
    da_score = 80 if inp.has_dataset else 0
    da_level: RiskLevel = "low" if da_score >= 80 else "fatal"
    dims.append(RiskDimension(
        dimension="DataAvailability",
        score=da_score,
        level=da_level,
        reason="Dataset available" if inp.has_dataset else "No dataset identified",
        suggestion="Verify dataset access" if inp.has_dataset else "Find or create dataset urgently",
        missing_evidence=[] if inp.has_dataset else ["Public dataset URL or repo"],
    ))

    # 3. BaselineReadiness
    br_score = 70 if inp.has_baseline else 0
    br_level: RiskLevel = "low" if br_score >= 70 else "high"
    dims.append(RiskDimension(
        dimension="BaselineReadiness",
        score=br_score,
        level=br_level,
        reason="Baseline available" if inp.has_baseline else "No baseline identified",
        suggestion="Verify baseline implementation" if inp.has_baseline else "Find baseline paper or code",
        missing_evidence=[] if inp.has_baseline else ["Baseline paper or GitHub repo"],
    ))

    # 4. ExperimentalClarity
    ec_score = 60 if inp.has_experiment_plan else 0
    ec_level: RiskLevel = "low" if ec_score >= 60 else "high"
    dims.append(RiskDimension(
        dimension="ExperimentalClarity",
        score=ec_score,
        level=ec_level,
        reason="Experiment plan exists" if inp.has_experiment_plan else "No experiment plan",
        suggestion="Refine experimental setup" if inp.has_experiment_plan else "Design experiments before proceeding",
    ))

    # 5. ScopeControl
    sc_score = 70 if inp.has_dataset and inp.has_baseline else 30
    sc_level: RiskLevel = "low" if sc_score >= 70 else "medium" if sc_score >= 30 else "high"
    dims.append(RiskDimension(
        dimension="ScopeControl",
        score=sc_score,
        level=sc_level,
        reason="Scope well-defined" if sc_score >= 70 else "Scope needs clarification",
        suggestion="Keep scope narrow for graduation",
    ))

    # 6. ResourceFit
    rf_score = 60 if inp.has_dataset and inp.has_verified_urls else 20
    rf_level: RiskLevel = "low" if rf_score >= 60 else "medium" if rf_score >= 20 else "high"
    dims.append(RiskDimension(
        dimension="ResourceFit",
        score=rf_score,
        level=rf_level,
        reason="Resources accessible" if rf_score >= 60 else "Resource access uncertain",
        suggestion="Verify all resource URLs",
    ))

    # 7. NoveltyDifferentiation
    nd_score = 50 if inp.evidence_count >= 2 else 20
    nd_level: RiskLevel = "medium" if nd_score >= 50 else "high"
    dims.append(RiskDimension(
        dimension="NoveltyDifferentiation",
        score=nd_score,
        level=nd_level,
        reason="Some differentiation evidence" if nd_score >= 50 else "Weak novelty evidence",
        suggestion="Collect more comparison evidence",
    ))

    return dims


def _determine_verdict(
    dims: list[RiskDimension],
    vetoes: list[HardVeto],
    inp: FeasibilityInput,
) -> FeasibilityVerdict:
    """根据维度分数和否决规则确定裁决."""
    # 检查是否有 fatal 维度
    has_fatal = any(d.level == "fatal" for d in dims)
    overall = sum(d.score for d in dims) // len(dims) if dims else 0

    # 检查 GO 是否被否决
    go_blocked = any(v.triggered and "GO" in v.blocked_verdicts for v in vetoes)

    if has_fatal and overall < 30:
        return "STOP"
    elif has_fatal or go_blocked:
        if overall < 40:
            return "PIVOT"
        elif overall < 60:
            return "CONDITIONAL"
        else:
            return "CONDITIONAL"
    elif overall >= 70:
        return "GO"
    elif overall >= 50:
        return "CONDITIONAL"
    elif overall >= 30:
        return "PIVOT"
    else:
        return "PARK"


def _generate_pivot_routes(inp: FeasibilityInput, dims: list[RiskDimension]) -> list[PivotRoute]:
    """生成至少三条 PIVOT 路线."""
    routes: list[PivotRoute] = []

    # 保守路线：缩小对象/任务
    routes.append(PivotRoute(
        route_type="conservative",
        new_topic=f"{inp.topic_title} — 简化版（缩小范围）",
        changed_keywords=["简化任务", "单一数据集", "明确指标"],
        required_evidence=["简化后的 baseline 实现", "小规模数据集验证"],
        expected_workload="3-4 个月",
        risk_delta="大幅降低（去掉复杂部分）",
        recommended_for="时间紧迫、需要保证毕业",
    ))

    # 平衡路线：保留方法，换更可验证数据
    routes.append(PivotRoute(
        route_type="balanced",
        new_topic=f"{inp.topic_title} — 替换数据集版",
        changed_keywords=["公开数据集", "可复现 baseline", "标准指标"],
        required_evidence=["新数据集 URL", "baseline 复现代码"],
        expected_workload="4-5 个月",
        risk_delta="中等降低（方法不变，数据更可靠）",
        recommended_for="方法有创新但数据不足",
    ))

    # 进取路线：保留创新点，补充风险条件
    routes.append(PivotRoute(
        route_type="aggressive",
        new_topic=f"{inp.topic_title} — 创新版（补齐条件）",
        changed_keywords=["补充实验", "增加 baseline 对比", "验证数据集"],
        required_evidence=["实验设计方案", "多个 baseline 对比", "数据集验证报告"],
        expected_workload="5-6 个月",
        risk_delta="略高（需要更多工作量）",
        recommended_for="有充足时间和资源，追求更高创新度",
    ))

    return routes


def assess_feasibility(inp: FeasibilityInput) -> FeasibilityAssessment:
    """执行可行性评估."""
    dims = _assess_dimensions(inp)
    vetoes = check_hard_vetoes(inp)
    verdict = _determine_verdict(dims, vetoes, inp)

    overall = sum(d.score for d in dims) // len(dims) if dims else 0
    bound_ev = []
    for d in dims:
        for eid in d.evidence_refs:
            if eid and eid not in bound_ev:
                bound_ev.append(eid)

    missing = []
    for d in dims:
        for m in d.missing_evidence:
            if m not in missing:
                missing.append(m)

    pivot_routes = _generate_pivot_routes(inp, dims) if verdict in ("PIVOT", "PARK", "STOP") else []

    summary = f"Verdict: {verdict}, Score: {overall}/100"
    if verdict == "GO":
        summary += " — 条件基本齐全，可继续"
    elif verdict == "CONDITIONAL":
        summary += " — 可做但需补关键资源"
    elif verdict == "PIVOT":
        summary += " — 需要收缩或换方向"
    elif verdict == "PARK":
        summary += " — 条件不足，暂挂"
    elif verdict == "STOP":
        summary += " — 核心条件不可验证，不建议继续"

    return FeasibilityAssessment(
        dimensions=dims,
        overall_score=overall,
        verdict=verdict,
        hard_vetoes=vetoes,
        pivot_routes=pivot_routes,
        summary=summary,
        bound_evidence=bound_ev,
        missing_evidence=missing,
    )
