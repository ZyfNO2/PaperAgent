"""Re5.X: Experiment A — Controlled ReAct action selector.

Minimal change: keeps the current think→call→observe loop, but
constrains the LLM to only choose from allowed_actions and
forbids it from directly stopping.

The LLM output is validated against the ActionSelector schema;
invalid output falls back to the deterministic planner.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, field_validator


class ActionSelection(BaseModel):
    """Validated output of the Experiment A action selector."""
    action: str = Field(description="execute_query | stop_with_gap")
    query_id: str | None = Field(default=None, description="Must come from allowed_actions")
    diagnosis_code: str = Field(
        description="role_gap | low_precision | source_failure | budget_exhausted | coverage_complete"
    )
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str = Field(max_length=100)

    @field_validator("action")
    @classmethod
    def _valid_action(cls, v: str) -> str:
        if v not in ("execute_query", "stop_with_gap"):
            raise ValueError(f"action must be execute_query or stop_with_gap, got '{v}'")
        return v

    @field_validator("diagnosis_code")
    @classmethod
    def _valid_code(cls, v: str) -> str:
        valid = {"role_gap", "low_precision", "source_failure",
                 "budget_exhausted", "coverage_complete"}
        if v not in valid:
            raise ValueError(f"diagnosis_code must be one of {valid}")
        return v


EXPERIMENT_A_SYSTEM = """你是"检索动作选择器"，不是最终研究评审员。

你只能从 INPUT.allowed_actions 中选择一个 action；不得选用未提供的
source、query_id 或 candidate_id，不得发明论文、数据集、工具或事实。

优先级：
1. 关闭优先级最高的 evidence_role_gap；
2. 在同一角色内提高 relevant_verified 数；
3. 只有 required_roles 已满足且最近两张 SearchCard 的增益均为 0 时，才建议停止。

注意：source_status=empty 只表示该查询没有命中，不代表 source 失效；
只有 failed、rate_limited、disabled 的 source 不可再选。

返回且只返回：
{
  "action": "execute_query|stop_with_gap",
  "query_id": "必须来自 allowed_actions",
  "diagnosis_code": "role_gap|low_precision|source_failure|budget_exhausted|coverage_complete",
  "evidence_ids": ["必须来自 observations"],
  "reason": "不超过30字"
}

[OUTPUT CONTRACT] 你必须输出且仅输出一个合法 JSON 对象，不要输出其他内容。"""


def build_experiment_a_prompt(
    allowed_actions: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    required_roles: dict[str, int],
    current_coverage: dict[str, int],
    gaps: list[str],
    last_two_gains: list[int],
    budget_remaining: int,
) -> str:
    """Build the user prompt for Experiment A action selector."""
    import json
    return json.dumps({
        "allowed_actions": allowed_actions,
        "observations": observations[-5:],
        "required_roles": required_roles,
        "current_coverage": current_coverage,
        "gaps": gaps,
        "last_two_card_gains": last_two_gains,
        "budget_remaining": budget_remaining,
    }, ensure_ascii=False, indent=2)


def parse_action_selection(raw: dict[str, Any]) -> ActionSelection | None:
    """Parse and validate LLM output. Returns None if invalid."""
    try:
        return ActionSelection(**raw)
    except Exception:
        return None
