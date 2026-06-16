"""Phase 08 domain models: FinalPackage / ExportSection / QAPair.

对齐 Plan/TopicPilot-CN_SOP_Phases/Phase_08_最终材料导出与MVP验收.md §3
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


MVPVerdict = Literal["PASS", "PARTIAL", "BLOCKED"]


class FinalTopic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_zh: str = Field(min_length=1)
    topic_en: str = Field(min_length=1)
    boundary: str = Field(min_length=1, description="题目边界 / 可验证承诺")
    from_pivot: bool
    pivot_rationale: str | None = None


class ProposalSectionState(BaseModel):
    """开题报告 10 节的状态。"""

    model_config = ConfigDict(extra="forbid")

    section_key: str
    title: str
    status: Literal["DRAFT", "TEMPLATE_ONLY", "TBD"]
    evidence_source: str
    needs_supplement: list[str] = Field(default_factory=list)


class WorkPackageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wp_id: str
    title: str
    innovation: str
    chapter: str
    main_experiment: str
    supporting_experiments: list[str] = Field(default_factory=list)


class EvidenceArchive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: str
    count: int
    storage: str
    risk: str = "低"


class QAPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    answer: str
    evidence: str


class ThesisStagePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    task: str
    deliverable: str
    risk: str = "中"


class FinalPackage(BaseModel):
    """Phase 08 产物。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    project_id: str = Field(default="")
    goal_level: Literal["保毕业", "稳中求新", "冲高水平"]

    final_topic: FinalTopic
    proposal_sections: list[ProposalSectionState] = Field(min_length=10)
    thesis_outline: list[dict] = Field(default_factory=list)
    work_packages: list[WorkPackageSummary] = Field(default_factory=list)
    evidence_archive: list[EvidenceArchive] = Field(default_factory=list)
    qa_pairs: list[QAPair] = Field(default_factory=list)
    future_stages: list[ThesisStagePlan] = Field(default_factory=list)

    backend_verification: MVPVerdict = "BLOCKED"
    ui_verification: MVPVerdict = "BLOCKED"
    playwright_verification: MVPVerdict = "BLOCKED"
    ready_for_thesis: bool = False
    block_reasons: list[str] = Field(default_factory=list)

    proposal_markdown: str = Field(default="", description="完整 Markdown 初稿")

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
