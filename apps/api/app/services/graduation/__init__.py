"""Session 62: GraduationDirection — LLM-first director + heuristic-fail-fast.

ponytail: 方向生成委托给 llm_director (走 arXiv + LLM), 失败直接抛 DirectionPlannerError.
"""
from .direction_planner import (
    GraduationDirection,
    plan_directions,
    DirectionPlannerError,
)
from .risk_scorer import score_direction, RiskBreakdown, RiskLevel
from .evidence_bundle import build_evidence_bundle, EvidenceBundle
from .baseline_advisor import recommend_baselines, BaselineRecommendation
from .module_extension_advisor import recommend_modules, ExtensionModule
from .decision_report import build_decision_report, DirectionDecisionReport

__all__ = [
    "GraduationDirection",
    "plan_directions",
    "DirectionPlannerError",
    "score_direction",
    "RiskBreakdown",
    "RiskLevel",
    "build_evidence_bundle",
    "EvidenceBundle",
    "recommend_baselines",
    "BaselineRecommendation",
    "recommend_modules",
    "ExtensionModule",
    "build_decision_report",
    "DirectionDecisionReport",
]