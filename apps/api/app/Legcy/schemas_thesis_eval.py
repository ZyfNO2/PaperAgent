"""Session 51: 工科学位论文题录可行性评估 schemas.

数据模型对齐 SOP §4.1:
- ThesisRecord         题录事实 (title/year/source_url/abstract_snippet, 全部可 URL verified)
- ThesisAssessment     对一条题录的完整评估 (实验需求/难度/周期/可行性/evidence_refs)
- ThesisEvalResult     单条题录的评估对比结果 (predicted vs gold + 4 任务指标)
- ThesisEvalReport     一次评估运行的聚合报告 (4 任务聚合指标 + baseline 对比 + 回归警告)

核心原则 (SOP §1):
- 题录链接是事实, 必须 URL verified, 不许替换伪造.
- 全文拿不到时降级为「题录/摘要级证据」, 不许编造全文内容.
- H100 不是默认需求; 真正风险是数据和硬件.
- 报告每个关键判断必须能回溯到题录/摘要/链接.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .schemas import EvidenceRef

# ---------- 枚举 (对齐 SOP §4.1 + 测试集文档 §6.2) ---------- #

ThesisDomain = Literal[
    "三维视觉/SLAM/点云",
    "土木/交通基础设施损伤检测",
    "工业缺陷检测/机器视觉",
    "自动驾驶/交通感知",
    "电力/轨交巡检视觉",
    "工科AI/计算机视觉",
    "机器人/机械臂实验系统",
    "遥感/无人机目标检测",
    "能源装备/故障诊断",
    "医学/人体三维视觉",
]

Difficulty = Literal["低-中", "中", "中-高", "高"]

# 实验需求多标签 (对齐测试集文档 §6.2, 9 个)
ExperimentNeedTag = Literal[
    "single_gpu_ok",
    "cpu_or_light_gpu_ok",
    "large_gpu_optional",
    "h100_level_not_recommended",
    "self_collected_dataset",
    "public_dataset_available",
    "hardware_platform_required",
    "annotation_heavy",
    "domain_data_permission_risk",
]

VerifiedStatus = Literal["verified", "partial", "failed"]
AssessmentMode = Literal["llm", "heuristic"]
GraduationFeasibility = Literal["可做", "收缩后可做", "可转向", "暂缓", "不建议"]
SubsetName = Literal["smoke_20", "regression_60", "hard_20", "all_100"]

# 题录三态对齐 RealityCheck 资源四层 (SOP §9 映射表)
REALITY_TIER_BY_DIFFICULTY: dict[Difficulty, str] = {
    "低-中": "existing_env",
    "中": "rent_compute",
    "中-高": "self_collect_data",
    "高": "infeasible",
}


# ---------- 4 个核心模型 ---------- #


class ThesisRecord(BaseModel):
    """题录事实 (抓取/解析产出, 全部可 URL verified).

    失败时降级为题录级证据, 绝不编造全文/摘要/作者结论.
    """

    model_config = ConfigDict(extra="forbid")

    thesis_id: str = Field(description="ENG-THESIS-001")
    title: str = Field(default="", description="题名 (空表示未抓到)")
    year: int | None = Field(default=None, description="学位年份")
    source_url: str = Field(description="原始题录链接, 必须保真不可替换")
    domain: ThesisDomain | None = Field(default=None, description="工科方向归类")
    abstract_snippet: str | None = Field(
        default=None, description="题录摘要片段 (≤ 500 字), 抓不到为 None"
    )
    verified_status: VerifiedStatus = Field(
        default="failed",
        description="verified=题录页可访问且字段完整; partial=仅部分字段; failed=抓取失败",
    )
    fallback_used: bool = Field(
        default=False, description="是否使用了测试集已给字段做题录级降级证据"
    )


class ThesisAssessment(BaseModel):
    """对一条题录的完整可行性评估."""

    model_config = ConfigDict(extra="forbid")

    thesis_id: str
    record: ThesisRecord
    experiment_needs: list[ExperimentNeedTag] = Field(default_factory=list)
    difficulty: Difficulty | None = None
    cycle: str | None = Field(default=None, description="单轮实验周期, 如 '1–3天/轮'")
    repeatability: str | None = Field(default=None, description="毕业前可迭代次数, 如 '8–15轮'")
    graduation_feasibility: GraduationFeasibility | None = None
    reality_tier: str | None = Field(default=None, description="映射 RealityCheck.resource_tier")
    evidence_refs: list[EvidenceRef] = Field(
        default_factory=list, description="每个关键判断挂题录/摘要引用"
    )
    unsupported_claims: list[str] = Field(
        default_factory=list, description="无法回溯到题录/摘要的判断 (防空口)"
    )
    risk_tags: list[str] = Field(default_factory=list, description="主风险标签 (硬件/数据/合规/部署)")
    assessment_mode: AssessmentMode = Field(default="heuristic")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ThesisEvalResult(BaseModel):
    """单条题录的评估对比结果 (predicted vs gold)."""

    model_config = ConfigDict(extra="forbid")

    thesis_id: str
    predicted: ThesisAssessment
    gold: dict = Field(description="测试集真值 (compute/data/hardware need + difficulty/cycle/repeatability)")
    task_metrics: dict = Field(description="4 任务各自指标 (按 thesis 维度)")
    hits: dict = Field(description="各判断是否命中真值 (url_fidelity/title/year/difficulty/tags...)")


class ThesisEvalReport(BaseModel):
    """一次评估运行的聚合报告."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    created_at: str
    subset: SubsetName
    thesis_count: int
    results: list[ThesisEvalResult] = Field(default_factory=list)
    aggregate_metrics: dict = Field(description="4 任务聚合指标")
    baseline_diff: dict = Field(default_factory=dict, description="与 baseline 的差值")
    regressions: list[str] = Field(default_factory=list, description="回归警告项")
