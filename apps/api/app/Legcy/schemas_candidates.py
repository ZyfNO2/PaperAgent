"""Session 24: Candidate Resource schemas (SOP §4-5).

候选资源统一结构，与 Evidence 明确隔离。
Candidate != Evidence, Candidate URL != URLVerified, Candidate recommendation != supports.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------- Query Plan ---------- #


class QueryItem(BaseModel):
    """单条检索 query."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["paper", "dataset", "repo"] = Field(description="资源类型")
    query: str = Field(min_length=1, description="检索词")
    keywords: list[str] = Field(default_factory=list, description="来源关键词")
    priority: Literal["high", "medium", "low"] = Field(default="medium")
    reason: str = Field(default="", description="为什么需要这条检索")


class QueryPlan(BaseModel):
    """S24: 检索计划 — 来自 keyword_review 确认后."""

    model_config = ConfigDict(extra="forbid")

    queries: list[QueryItem] = Field(min_length=1, description="检索 query 列表")

    def by_source(self, source: str) -> list[QueryItem]:
        return [q for q in self.queries if q.source == source]


# ---------- Candidate Resource ---------- #

CandidateKind = Literal["paper", "dataset", "repo", "thesis_template", "benchmark"]
CandidateStatus = Literal["candidate"]
UserMark = Literal["unreviewed", "saved", "rejected", "needs_review", "selected"]


class CandidateResource(BaseModel):
    """S24: 候选资源 — 不等于 Evidence.

    关键约束:
    - status 始终为 "candidate"
    - user_mark 控制用户交互状态
    - risk_flags 记录风险（如 url_unverified）
    - promote_to_selected 只标记 selected，不写 Evidence
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1, description="候选 ID")
    kind: CandidateKind
    title: str = Field(min_length=1, description="资源标题")
    url: str = Field(default="", description="资源 URL（可能未验证）")
    source: str = Field(default="unknown", description="来源平台")
    matched_keywords: list[str] = Field(default_factory=list)
    summary: str = Field(default="", description="为什么可能有用")
    risk_flags: list[str] = Field(default_factory=lambda: ["url_unverified"])
    status: CandidateStatus = Field(default="candidate")
    user_mark: UserMark = Field(default="unreviewed")


class CandidateList(BaseModel):
    """候选资源列表."""

    model_config = ConfigDict(extra="forbid")

    candidates: list[CandidateResource] = Field(default_factory=list)
    query_plan: QueryPlan | None = Field(default=None, description="关联检索计划")
    total_found: int = Field(default=0)
    search_time_ms: int = Field(default=0)


# ---------- User Actions on Candidates ---------- #

CandidateAction = Literal[
    "save_candidate",
    "reject_candidate",
    "mark_needs_review",
    "promote_to_selected",
]


class CandidateActionRequest(BaseModel):
    """对候选资源执行操作."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    action: CandidateAction
    note: str = Field(default="", description="用户备注")


# ---------- Blocked Response ---------- #


class BlockedResponse(BaseModel):
    """keyword 未 approved 时返回."""

    blocked: bool = Field(default=True)
    reason: str = Field(default="keyword_review not yet approved")


# ---------- Verify Candidate != Evidence ---------- #


def candidate_is_not_evidence(cand: CandidateResource) -> bool:
    """验证候选资源不等于证据.

    候选资源:
    - status == "candidate" (不是 "evidence")
    - 没有 support_level 字段
    - 没有 verification_status 字段
    """
    return cand.status == "candidate"
