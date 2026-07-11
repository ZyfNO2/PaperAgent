"""Re5.X: Experiment C — Plan revision controller.

Uses the deterministic template planner as the control arm.
LLM only proposes small edits to failed cards, not a full rewrite.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, field_validator


class PlanEdit(BaseModel):
    """A single edit to the search plan."""
    operation: str = Field(description="replace | append | disable")
    card_id: str = Field(description="ID of card to edit (for replace/disable)")
    replacement: dict[str, str] | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    expected_increment: str | None = None

    @field_validator("operation")
    @classmethod
    def _valid_op(cls, v: str) -> str:
        if v not in ("replace", "append", "disable"):
            raise ValueError("operation must be replace/append/disable")
        return v


class PlanRevision(BaseModel):
    """Output of the Experiment C plan reviser."""
    edits: list[PlanEdit] = Field(default_factory=list)
    unresolved_gaps: list[str] = Field(default_factory=list)


EXPERIMENT_C_SYSTEM = """你是检索计划修订器。已有 deterministic SearchCard，不要重写整份计划。

每次最多做两项 edit：
1. 替换一张 low_precision SearchCard；
2. 为缺失 evidence role 追加一张卡；
3. 将 rate_limited / failed source 切换为 allowed alternate source；
4. 明确 no_repair_route。

每个 edit 必须引用被替换的 card_id 和 observation evidence_ids；
不得改变已经满足的 evidence role；不得生成无对象词的泛方法查询。

返回：
{
  "edits": [{
    "operation": "replace|append|disable",
    "card_id": "...",
    "replacement": {"source":"...", "query":"...", "target_role":"..."},
    "evidence_ids": ["..."],
    "expected_increment": "..."
  }],
  "unresolved_gaps": []
}

[OUTPUT CONTRACT] 你必须输出且仅输出一个合法 JSON 对象，不要输出其他内容。"""


def build_experiment_c_prompt(
    current_cards: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    gaps: list[str],
    allowed_sources: list[str],
    alternate_map: dict[str, str],
) -> str:
    """Build the user prompt for Experiment C plan reviser."""
    import json
    return json.dumps({
        "current_cards": current_cards,
        "observations": observations[-5:],
        "gaps": gaps,
        "allowed_sources": allowed_sources,
        "alternate_map": alternate_map,
    }, ensure_ascii=False, indent=2)


def parse_plan_revision(raw: dict[str, Any]) -> PlanRevision | None:
    """Parse and validate LLM output. Returns None if invalid."""
    try:
        return PlanRevision(**raw)
    except Exception:
        return None
