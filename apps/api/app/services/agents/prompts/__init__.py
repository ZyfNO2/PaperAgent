"""Top-level prompts for the new research agent.

Re-exports the 4 LLM step contracts. Kept as a package so the orchestrator
file stays small and the system prompts travel together.
"""

from .parse_topic import PARSE_TOPIC_SYSTEM
from .plan_tools import PLAN_TOOLS_SYSTEM, USER_TEMPLATE_PLAN_TOOLS
from .synthesize import SYNTHESIZE_SYSTEM, USER_TEMPLATE_SYNTHESIZE
from .devils_advocate import DEVILS_ADVOCATE_SYSTEM, USER_TEMPLATE_DEVILS_ADVOCATE

__all__ = [
    "PARSE_TOPIC_SYSTEM",
    "PLAN_TOOLS_SYSTEM",
    "SYNTHESIZE_SYSTEM",
    "DEVILS_ADVOCATE_SYSTEM",
    "USER_TEMPLATE_PLAN_TOOLS",
    "USER_TEMPLATE_SYNTHESIZE",
    "USER_TEMPLATE_DEVILS_ADVOCATE",
]
