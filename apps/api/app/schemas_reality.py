"""Session 45: RealityCheck — 资源可达性四层 + 实验周期三档.

资源四层: existing_env / rent_compute / self_collect_data / infeasible
实验周期: week / month / year
毕业风险: low / medium / high

与现有 FeasibilitySummary 5 档并列输出, 融合降级.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------- 枚举 ---------- #

ResourceTier = Literal["existing_env", "rent_compute", "self_collect_data", "infeasible"]
ExperimentCycle = Literal["week", "month", "year"]
GraduationRisk = Literal["low", "medium", "high"]

# ---------- 中文映射 ---------- #

RESOURCE_TIER_ZH: dict[ResourceTier, str] = {
    "existing_env": "现有环境能做",
    "rent_compute": "需租算力能做",
    "self_collect_data": "需自采数据集",
    "infeasible": "真做不到",
}

EXPERIMENT_CYCLE_ZH: dict[ExperimentCycle, str] = {
    "week": "一周左右",
    "month": "一个月左右",
    "year": "一年左右",
}

GRADUATION_RISK_ZH: dict[GraduationRisk, str] = {
    "low": "低风险",
    "medium": "中风险",
    "high": "高风险",
}


# ---------- RealityCheck ---------- #

class RealityCheck(BaseModel):
    """现实约束评估: 资源可达性 + 实验周期 + 毕业风险."""

    model_config = ConfigDict(extra="forbid")

    resource_tier: ResourceTier = Field(description="资源可达性四层")
    resource_reason: str = Field(default="", description="资源层判断理由")
    experiment_cycle: ExperimentCycle = Field(description="实验周期三档")
    cycle_reason: str = Field(default="", description="周期判断理由")
    max_experiment_rounds: int = Field(ge=0, description="周期决定能做几轮实验")
    graduation_risk: GraduationRisk = Field(description="毕业风险等级")
    score: int = Field(ge=0, le=100, description="现实约束评分 0-100")
    suggestion: str = Field(default="", description="建议")


# ---------- 实验轮数矩阵 ---------- #

# (goal_level, cycle) → (max_rounds, risk)
_CYCLE_MATRIX: dict[tuple[str, ExperimentCycle], tuple[int, GraduationRisk]] = {
    ("保毕业", "week"): (5, "low"),
    ("保毕业", "month"): (2, "medium"),
    ("保毕业", "year"): (1, "high"),
    ("已有小论文", "week"): (5, "low"),
    ("已有小论文", "month"): (3, "low"),
    ("已有小论文", "year"): (1, "medium"),
}


def get_cycle_matrix(goal_level: str, cycle: ExperimentCycle) -> tuple[int, GraduationRisk]:
    """查表: goal_level + cycle → (max_rounds, risk)."""
    return _CYCLE_MATRIX.get((goal_level, cycle), (1, "high"))
