"""Small Paper → Thesis expansion (Session 49: Track B 闭环).

主入口:
- extract_small_paper_card(project_id, paper_id, prefer) → SmallPaperCard
- build_extension_plan(project_id, paper_id, card) → ExtensionPlan
- detect_repeat_risks(card, plan) → list[RepeatRiskWarning]

LLM 路径走 chat_json (app.services.llm), 失败 fallback heuristic.
"""

from __future__ import annotations

import logging

from ...schemas_small_paper import (
    ExtensionPlan,
    RepeatRiskWarning,
    SmallPaperCard,
)
from .contribution_extractor import extract_small_paper_card
from .extension_planner import build_extension_plan
from .repeat_risk import detect_repeat_risks

logger = logging.getLogger(__name__)


__all__ = [
    "extract_small_paper_card",
    "build_extension_plan",
    "detect_repeat_risks",
    "SmallPaperCard",
    "ExtensionPlan",
    "RepeatRiskWarning",
]
