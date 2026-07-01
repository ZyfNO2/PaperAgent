"""Session 25: Workspace Board schemas (SOP §3-5).

双栏工作台：左栏 SelectedResource（用户选中），右栏 CandidateResource（系统候选）。
Selected != Evidence：加入左栏不等于进入证据链。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas_candidates import CandidateKind


# ---------- Selected Resource ---------- #

VerificationStatus = Literal["unchecked", "url_verified", "failed", "partial"]
EvidenceStatus = Literal["not_promoted", "eligible", "promoted", "rejected"]


class SelectedResource(BaseModel):
    """用户选中资料 — 仍然不等于 Evidence。

    关键约束：
    - 来源于 CandidateResource 的用户操作（add_to_selected）
    - verification_status 记录 URL 验证状态
    - evidence_status 记录是否已晋升为 Evidence
    - 不能直接支持报告结论
    """

    model_config = ConfigDict(extra="forbid")

    selected_id: str = Field(min_length=1, description="选中资源 ID")
    candidate_id: str = Field(min_length=1, description="来源候选 ID")
    kind: CandidateKind
    title: str = Field(min_length=1, description="资源标题")
    url: str = Field(default="", description="资源 URL")
    source: str = Field(default="unknown", description="来源平台")
    selected_reason: str = Field(default="", description="用户选中理由")
    user_note: str = Field(default="", description="用户备注")
    selected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    verification_status: VerificationStatus = Field(default="unchecked")
    evidence_status: EvidenceStatus = Field(default="not_promoted")
    is_core: bool = Field(default=False, description="是否为核心资料")
    needs_review: bool = Field(default=False, description="是否需要复核")


# ---------- Workspace Board ---------- #


class WorkspaceBoard(BaseModel):
    """工作台状态：左栏 selected，右栏 candidates。"""

    model_config = ConfigDict(extra="forbid")

    selected_resources: list[SelectedResource] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list, description="右栏候选 ID 列表")
    project_id: str = Field(default="", description="项目 ID")

    def has_candidate(self, candidate_id: str) -> bool:
        return candidate_id in self.candidate_ids

    def get_selected(self, candidate_id: str) -> SelectedResource | None:
        for s in self.selected_resources:
            if s.candidate_id == candidate_id:
                return s
        return None


# ---------- User Actions ---------- #

WorkspaceAction = Literal[
    "add_to_selected",
    "remove_from_selected",
    "mark_core",
    "mark_needs_review",
    "open_candidate_drawer",
]


class WorkspaceActionRequest(BaseModel):
    """工作台操作请求."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1, description="候选资源 ID")
    action: WorkspaceAction
    reason: str = Field(default="", description="操作理由")
    note: str = Field(default="", description="用户备注")


class WorkspaceActionResult(BaseModel):
    """工作台操作结果."""

    model_config = ConfigDict(extra="forbid")

    ok: bool = Field(default=True)
    action: str = Field(description="执行的操作")
    selected_id: str | None = Field(default=None, description="关联选中资源 ID")
    message: str = Field(default="")


# ---------- Coverage Summary ---------- #


class CoverageSummary(BaseModel):
    """选题资料覆盖度摘要."""

    model_config = ConfigDict(extra="forbid")

    selected_paper_count: int = Field(default=0)
    selected_dataset_count: int = Field(default=0)
    selected_repo_count: int = Field(default=0)
    selected_template_count: int = Field(default=0)
    selected_benchmark_count: int = Field(default=0)
    has_dataset: bool = Field(default=False, description="至少有 1 个数据集")
    has_baseline: bool = Field(default=False, description="至少有 1 个 baseline/repo")
    has_url_unverified: bool = Field(default=False, description="存在未验证 URL")
    has_needs_review: bool = Field(default=False, description="存在需要复核的资料")
    total_selected: int = Field(default=0)


def compute_coverage(board: WorkspaceBoard) -> CoverageSummary:
    """计算覆盖度摘要."""
    kind_map: dict[str, int] = {}
    has_unverified = False
    has_review = False

    for s in board.selected_resources:
        kind_map[s.kind] = kind_map.get(s.kind, 0) + 1
        if s.verification_status == "unchecked" or s.verification_status == "failed":
            has_unverified = True
        if s.needs_review:
            has_review = True

    paper_count = kind_map.get("paper", 0)
    dataset_count = kind_map.get("dataset", 0)
    repo_count = kind_map.get("repo", 0)
    template_count = kind_map.get("thesis_template", 0)
    benchmark_count = kind_map.get("benchmark", 0)

    return CoverageSummary(
        selected_paper_count=paper_count,
        selected_dataset_count=dataset_count,
        selected_repo_count=repo_count,
        selected_template_count=template_count,
        selected_benchmark_count=benchmark_count,
        has_dataset=dataset_count > 0,
        has_baseline=repo_count > 0 or benchmark_count > 0,
        has_url_unverified=has_unverified,
        has_needs_review=has_review,
        total_selected=len(board.selected_resources),
    )


# ---------- Workspace helpers ---------- #

_id_counter = 0


def add_to_selected(board: WorkspaceBoard, candidate_id: str, candidate_title: str = "",
                    candidate_kind: str = "paper", candidate_url: str = "",
                    candidate_source: str = "unknown", reason: str = "", note: str = "") -> WorkspaceActionResult:
    """将候选加入左栏（幂等）."""
    global _id_counter

    # 检查是否已存在
    existing = board.get_selected(candidate_id)
    if existing is not None:
        return WorkspaceActionResult(
            ok=True,
            action="add_to_selected",
            selected_id=existing.selected_id,
            message=f"Candidate {candidate_id} already selected (idempotent).",
        )

    _id_counter += 1
    selected_id = f"sel_{_id_counter:03d}"
    sel = SelectedResource(
        selected_id=selected_id,
        candidate_id=candidate_id,
        kind=candidate_kind,  # type: ignore[arg-type]
        title=candidate_title or f"Resource {candidate_id}",
        url=candidate_url,
        source=candidate_source,
        selected_reason=reason,
        user_note=note,
    )
    board.selected_resources.append(sel)
    return WorkspaceActionResult(
        ok=True,
        action="add_to_selected",
        selected_id=selected_id,
        message=f"Added {candidate_id} to selected.",
    )


def remove_from_selected(board: WorkspaceBoard, candidate_id: str) -> WorkspaceActionResult:
    """从左栏移除（不删除原始 Candidate）."""
    before = len(board.selected_resources)
    board.selected_resources = [s for s in board.selected_resources if s.candidate_id != candidate_id]
    after = len(board.selected_resources)
    removed = before - after
    return WorkspaceActionResult(
        ok=removed > 0,
        action="remove_from_selected",
        message=f"Removed {removed} selected resource(s) for {candidate_id}.",
    )


def mark_core(board: WorkspaceBoard, candidate_id: str, core: bool = True) -> WorkspaceActionResult:
    """标记核心资料."""
    sel = board.get_selected(candidate_id)
    if sel is None:
        return WorkspaceActionResult(ok=False, action="mark_core", message=f"{candidate_id} not selected.")
    sel.is_core = core
    return WorkspaceActionResult(
        ok=True,
        action="mark_core",
        selected_id=sel.selected_id,
        message=f"{'Marked' if core else 'Unmarked'} {candidate_id} as core.",
    )


def mark_needs_review(board: WorkspaceBoard, candidate_id: str, needs: bool = True) -> WorkspaceActionResult:
    """标记需要复核."""
    sel = board.get_selected(candidate_id)
    if sel is None:
        return WorkspaceActionResult(ok=False, action="mark_needs_review", message=f"{candidate_id} not selected.")
    sel.needs_review = needs
    return WorkspaceActionResult(
        ok=True,
        action="mark_needs_review",
        selected_id=sel.selected_id,
        message=f"{'Marked' if needs else 'Unmarked'} {candidate_id} for review.",
    )
