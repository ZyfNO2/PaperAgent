"""Session 62: GraduationDirection planner/scorer/evidence/baseline/module/report.

ponytail: no LLM, no external state; pure heuristic.
"""
from .direction_planner import (
    GraduationDirection,
    plan_directions,
    RAW_TOPIC_TEMPLATES,
)
from .risk_scorer import score_direction, RiskBreakdown, RiskLevel
from .evidence_bundle import build_evidence_bundle, EvidenceBundle
from .baseline_advisor import recommend_baselines, BaselineRecommendation
from .module_extension_advisor import recommend_modules, ExtensionModule
from .decision_report import build_decision_report, DirectionDecisionReport

__all__ = [
    "GraduationDirection",
    "plan_directions",
    "RAW_TOPIC_TEMPLATES",
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