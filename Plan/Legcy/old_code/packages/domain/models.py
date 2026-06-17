"""TopicPilot-CN domain models.

Phase 01 子集：只包含 ProjectIntake 系列。后续 Phase（02 题目拆解、03 方向
检索、04 Baseline 账本）会在同一包内追加 TopicSpec / PaperEvidence /
DatasetCandidate / BaselineCandidate / RiskScore / PivotCandidate /
WorkPackage 等模型。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


GoalLevel = Literal["保毕业", "稳中求新", "冲高水平"]
DegreeType = Literal["本科", "硕士", "博士", "未知"]
IntakeRating = Literal["A", "B", "C", "D"]
RiskLevel = Literal["低", "中", "高"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InheritedResource(BaseModel):
    """可继承资源：同门论文、课题组代码、已有数据、已跑通环境、可复用开源。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "同门毕业论文",
        "课题组已有数据",
        "课题组已有代码",
        "已跑通环境",
        "可参考项目",
        "可合法复用开源",
        "导师项目数据",
        "其他",
    ]
    description: str
    available: bool = False
    authorization_or_attribution_risk: RiskLevel = "低"
    note: str | None = None


class StudentResourceProfile(BaseModel):
    """学生资源画像。"""

    model_config = ConfigDict(extra="forbid")

    programming_level: Literal["零基础", "入门", "熟练", "可独立工程化"] = "入门"
    dl_or_algorithm_foundation: Literal["弱", "中", "强"] = "中"
    paper_reading_ability: Literal["弱", "中", "强"] = "中"
    english_reading_ability: Literal["弱", "中", "强"] = "中"
    compute_resource: str = Field(
        default="未知",
        description="如 笔记本 3060 / 实验室 A100×2 / 云 GPU 等",
    )
    weekly_hours: int = Field(default=0, ge=0, le=168)
    data_collection_ability: Literal["弱", "中", "强"] = "中"
    data_annotation_ability: Literal["弱", "中", "强"] = "中"
    code_reproduction_ability: Literal["弱", "中", "强"] = "中"
    system_dev_ability: Literal["弱", "中", "强"] = "中"


class MissingField(BaseModel):
    """显式记录的待补字段。Phase 01 禁止隐式假设。"""

    model_config = ConfigDict(extra="forbid")

    field_name: str
    why_required: str
    impact_if_missing: str
    priority: Literal["P0", "P1", "P2"] = "P1"


class ProjectIntake(BaseModel):
    """LangGraph `TopicPilotGraph` 的入口状态对象。

    字段集合严格对齐 Phase_01 §3.1。任何缺失都必须进入 ``missing_fields``，
    由 IntakeValidationNode 与 HumanClarificationNode 负责补问。
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    case_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=_utcnow)

    major: str | None = None
    degree_type: DegreeType = "未知"
    goal_level: GoalLevel

    thesis_deadline: str | None = None
    proposal_deadline: str | None = None
    first_result_deadline: str | None = None

    advisor_direction: str | None = None
    school_requirements: list[str] = Field(default_factory=list)

    inherited_resources: list[InheritedResource] = Field(default_factory=list)
    student_resources: StudentResourceProfile = Field(default_factory=StudentResourceProfile)

    raw_topic: str = Field(min_length=1)
    must_keep: list[str] = Field(default_factory=list)
    can_drop: list[str] = Field(default_factory=list)

    missing_fields: list[MissingField] = Field(default_factory=list)
    intake_rating: IntakeRating

    @field_validator("thesis_deadline", "proposal_deadline", "first_result_deadline")
    @classmethod
    def _validate_iso_date(cls, v: str | None) -> str | None:
        if v is None:
            return None
        # 接受 YYYY-MM-DD 或 ISO datetime；不强制具体时区
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"时间字段必须是 ISO 8601 字符串（YYYY-MM-DD 或带时间），收到: {v!r}"
            ) from exc
        return v

    @model_validator(mode="after")
    def _enforce_phase01_invariants(self) -> "ProjectIntake":
        """不变量：goal_level/raw_topic 非空（已被 Field 保证），raw_topic 不能只是空白。"""

        if not self.raw_topic.strip():
            raise ValueError("raw_topic 不能为空白字符")
        if not self.case_id.strip():
            raise ValueError("case_id 不能为空白字符")
        return self


_PLACEHOLDER_TOKENS = {"tbd", "todo", "待定", "未知", "占位", "null", "none", ""}


def _is_placeholder(value: str | None) -> bool:
    """判定值是否为占位符（TBD / TODO / 待定 等）。

    用于在题目、case_id、目标档位等关键字段上识别"严重缺失"——
    即用户写了字面 'TBD' 而非真正的留空，这比"未填写"更不可评估。
    """

    if value is None:
        return False
    return value.strip().lower() in _PLACEHOLDER_TOKENS


def derive_missing_fields(payload: ProjectIntake) -> list[MissingField]:
    """根据已采集字段推导 missing_fields。

    用途：IntakeNode 在收到初始输入后调用；与 LLM 自动补全互为补充。
    显式列出的字段优先级 P0 表示阻断 Phase 02，P1 表示强烈建议补充，
    P2 表示锦上添花。
    """

    missing: list[MissingField] = []

    def add(field_name: str, why: str, impact: str, priority: str = "P1") -> None:
        if any(m.field_name == field_name for m in missing):
            return
        missing.append(
            MissingField(
                field_name=field_name,
                why_required=why,
                impact_if_missing=impact,
                priority=priority,  # type: ignore[arg-type]
            )
        )

    # 基础画像
    if not payload.major:
        add(
            "major",
            "专业决定方向池与可用 baseline",
            "无法收敛到专业相关方向，Phase 02 推荐题目失真",
            "P0",
        )
    if payload.degree_type == "未知":
        add(
            "degree_type",
            "学位类型决定工作量与章节深度",
            "可能错配工作量，章节模板定位错误",
            "P1",
        )

    # 时间红线
    if not payload.proposal_deadline:
        add(
            "proposal_deadline",
            "开题时间决定开题报告生成节奏",
            "无法判断资料检索与文献阅读窗口",
            "P0",
        )
    if not payload.thesis_deadline:
        add(
            "thesis_deadline",
            "毕业时间决定方法章节完成节奏",
            "无法判断实验周期是否足够",
            "P0",
        )
    if not payload.first_result_deadline:
        add(
            "first_result_deadline",
            "第一张主结果表是论文生死线",
            "无法评估 baseline 复现是否赶得上",
            "P0",
        )

    # 导师与学院
    if not payload.advisor_direction:
        add(
            "advisor_direction",
            "导师方向决定题目可接受范围",
            "可能与导师期望偏离",
            "P0",
        )
    if not payload.school_requirements:
        add(
            "school_requirements",
            "学院开题模板与格式要求决定目录与文档结构",
            "开题报告可能不符合学院规范",
            "P1",
        )

    # 资源
    if not payload.inherited_resources:
        add(
            "inherited_resources",
            "无继承资源时 Phase 03/04 须显式触发公开 baseline 检索",
            "复现成本与时间风险显著上升",
            "P1",
        )
    if payload.student_resources.weekly_hours <= 0:
        add(
            "student_resources.weekly_hours",
            "每周可投入时间决定工作量上限",
            "无法评估能否按期完成",
            "P1",
        )
    if payload.student_resources.compute_resource == "未知":
        add(
            "student_resources.compute_resource",
            "算力决定模型规模与训练方案",
            "可能选择超出算力的方案",
            "P1",
        )

    # 原始题目取舍
    if not payload.must_keep:
        add(
            "must_keep",
            "没有保留项可能导致改题时丢失关键约束",
            "题目被改得面目全非",
            "P2",
        )

    return missing


def compute_intake_rating(payload: ProjectIntake, missing: list[MissingField]) -> IntakeRating:
    """按 Phase_01 §5 Step 5 计算评级。

    A：输入完整，可直接进入 Phase 02。
    B：基本可用，可进入 Phase 02，但必须带显式假设。
    C：关键缺失，必须补问后再进入 Phase 02。
    D：当前不可评估，题目、目标、时间或资源严重缺失。

    D 的额外触发（对齐 §7.3 阻断条件）：
    - raw_topic / case_id 写成字面占位符（TBD / TODO / 待定）
    - P0 缺失 ≥ 4 且 P1 缺失 ≥ 2
    """

    p0_open = [m for m in missing if m.priority == "P0"]
    p1_open = [m for m in missing if m.priority == "P1"]
    p2_open = [m for m in missing if m.priority == "P2"]

    if (
        _is_placeholder(payload.raw_topic)
        or _is_placeholder(payload.case_id)
        or (len(p0_open) >= 4 and len(p1_open) >= 2)
    ):
        return "D"

    if p0_open:
        return "C"
    if len(p1_open) >= 3:
        return "D"
    if p1_open or p2_open:
        return "B"
    return "A"


class ValidationOutcome(str, Enum):
    OK = "OK"
    NEED_CLARIFICATION = "NEED_CLARIFICATION"
    BLOCKED = "BLOCKED"


def validate_intake(payload: ProjectIntake) -> tuple[ValidationOutcome, IntakeRating, list[MissingField]]:
    """IntakeValidationNode 主入口。

    返回 (outcome, rating, missing_fields)：
    - BLOCKED：评级为 D，严重缺失，禁止进入 Phase 02。
    - NEED_CLARIFICATION：评级为 C，必须进入 HumanClarificationNode。
    - OK：评级为 A/B，可进入 TopicDecompositionNode。
    """

    missing = derive_missing_fields(payload)
    rating = compute_intake_rating(payload, missing)
    if rating == "D":
        return ValidationOutcome.BLOCKED, rating, missing
    if rating == "C":
        return ValidationOutcome.NEED_CLARIFICATION, rating, missing
    return ValidationOutcome.OK, rating, missing
