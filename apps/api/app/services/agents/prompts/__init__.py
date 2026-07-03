"""Top-level prompts for the new research agent.

Re-exports the 9 LLM step contracts. Kept as a package so the
orchestrator file stays small and the system prompts travel together.
"""
from .devils_advocate import DEVILS_ADVOCATE_SYSTEM, USER_TEMPLATE_DEVILS_ADVOCATE
from .gap_repair_planner import GAP_REPAIR_PLANNER_SYSTEM, render_gap_repair
from .parse_topic import PARSE_TOPIC_SYSTEM
from .plan_tools import PLAN_TOOLS_SYSTEM, USER_TEMPLATE_PLAN_TOOLS
from .synthesize import (
    EVIDENCE_REVIEW_SYSTEM,
    LOW_BAR_REVIEWER_SYSTEM,
    RE04_EVIDENCE_REVIEW_SYSTEM,
    SYNTHESIZE_SYSTEM,
    USER_TEMPLATE_EVIDENCE_REVIEW,
    USER_TEMPLATE_LOW_BAR,
    USER_TEMPLATE_SYNTHESIZE,
    USER_TEMPLATE_SYNTHESIZE_V2,
)
from .verify_candidate import VERIFY_CANDIDATE_SYSTEM, render_verify_candidate
from .work_package_brainstorm import (
    WORK_PACKAGE_BRAINSTORM_SYSTEM,
    render_work_package_brainstorm,
)

__all__ = [
    # Step 1 — parse topic
    "PARSE_TOPIC_SYSTEM",
    # Step 2 — multi-round plan
    "PLAN_TOOLS_SYSTEM",
    "USER_TEMPLATE_PLAN_TOOLS",
    # Step 3 — synthesize (Re02: consumes reviewed evidence + candidate pool)
    "SYNTHESIZE_SYSTEM",
    "USER_TEMPLATE_SYNTHESIZE",
    "USER_TEMPLATE_SYNTHESIZE_V2",
    # Step 3.5 — EvidenceReview (Re02 new)
    "EVIDENCE_REVIEW_SYSTEM",
    "RE04_EVIDENCE_REVIEW_SYSTEM",  # Re04-fix SOP §4: Chinese-language prompt.
    "USER_TEMPLATE_EVIDENCE_REVIEW",
    # Step 4 — Low-bar Reviewer (Re02 new)
    "LOW_BAR_REVIEWER_SYSTEM",
    "USER_TEMPLATE_LOW_BAR",
    # Step 5 — DevilsAdvocate (kept from Re01; optional)
    "DEVILS_ADVOCATE_SYSTEM",
    "USER_TEMPLATE_DEVILS_ADVOCATE",
    # Re08 — per-candidate verifier (SOP §4.1 + §5.1)
    "VERIFY_CANDIDATE_SYSTEM",
    "render_verify_candidate",
    # Re08 — gap-repair planner (SOP §4.3 + §5.2)
    "GAP_REPAIR_PLANNER_SYSTEM",
    "render_gap_repair",
    # Re08 — work-package brainstorm (SOP §5.3)
    "WORK_PACKAGE_BRAINSTORM_SYSTEM",
    "render_work_package_brainstorm",
]