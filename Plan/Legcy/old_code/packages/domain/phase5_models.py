"""Phase 05 domain models: RiskScore (六维) / PivotCandidate / RiskEvaluation.

对齐 Plan/TopicPilot-CN_SOP_Phases/Phase_05_风险评分与Pivot决策.md §3 / §4
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


DimensionKey = Literal[
    "方向成熟度",
    "数据可得性",
    "baseline清晰度",
    "实验可行性",
    "工作量可拆性",
    "毕业时间风险",
]


class DimensionScore(BaseModel):
    """六维评分单项。

    `pluses` / `minuses` 列出该维度的加分/减分信号 (用户友好),
    如 ["方向论文多 +5", "综述 +2"] 或 ["baseline 复现难 -15"].
    `score` 仍是 0-100 浮点, `evidence_summary` 是单行总评.
    """

    model_config = ConfigDict(extra="forbid")

    key: DimensionKey
    score: float = Field(ge=0.0, le=100.0)
    evidence_summary: str = Field(min_length=1, description="一句话解释评分依据")
    risk_note: str | None = None
    pluses: list[str] = Field(default_factory=list, description="加分项信号 (++)")
    minuses: list[str] = Field(default_factory=list, description="减分项信号 (--)")


class RiskScore(BaseModel):
    """六维综合风险评分。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(default="")
    evidence_ledger_id: str = Field(default="")
    goal_level: Literal["保毕业", "稳中求新", "冲高水平"]

    dimensions: list[DimensionScore] = Field(min_length=6)
    overall_score: float = Field(ge=0.0, le=100.0)
    overall_rating: Literal["A", "B", "C", "D"]

    max_risk_dimension: DimensionKey
    min_viable_path: str = Field(min_length=1, description="最小可行毕业路线")

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PivotCandidate(BaseModel):
    """Pivot 候选方案。"""

    model_config = ConfigDict(extra="forbid")

    pivot_id: str = Field(min_length=1, description="如 P01 / P02")
    pivot_type: Literal["收缩", "换向"]
    new_topic: str = Field(min_length=1, description="收缩 / 转向后的新题目")
    rationale: str = Field(min_length=1, description="为什么这样 pivot")
    preserved_evidence: list[str] = Field(
        default_factory=list, description="可保留的论文 / baseline / 数据"
    )
    new_evidence_needed: list[str] = Field(
        default_factory=list, description="需补的证据"
    )
    residual_risk: Literal["低", "中", "高", "未知"] = "中"


class RiskEvaluation(BaseModel):
    """Phase 05 产物。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    project_id: str = Field(default="")
    evidence_ledger_id: str = Field(default="")
    goal_level: Literal["保毕业", "稳中求新", "冲高水平"]

    risk_score: RiskScore
    decision: Literal["继续", "收缩", "转向"]
    decision_rationale: str = Field(min_length=1)

    pivot_candidates: list[PivotCandidate] = Field(default_factory=list)
    must_supplement: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
