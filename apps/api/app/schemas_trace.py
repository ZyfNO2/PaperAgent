"""Session 11: Trace 持久化与操作回放 schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TraceActor = Literal["system", "user", "agent"]


class TraceEvent(BaseModel):
    """一条 Trace 事件 (SOP §4)."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str
    project_id: str
    ts: str
    actor: TraceActor
    action: str
    target_type: str | None = None
    target_id: str | None = None
    evidence_id: str | None = None
    before: dict = Field(default_factory=dict)
    after: dict = Field(default_factory=dict)
    reason: str | None = None
    source: str | None = None
    session: str | None = None


class TraceListResponse(BaseModel):
    """GET /trace 响应."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    events: list[TraceEvent]
    total: int
    filtered: int = 0


class TraceTimelineResponse(BaseModel):
    """GET /evidence/{id}/timeline 响应."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    evidence_id: str
    events: list[TraceEvent]


class TraceSummaryResponse(BaseModel):
    """GET /trace/summary 响应."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    user_actions: int
    system_actions: int
    agent_actions: int = 0
    total: int
    key_decisions: list[str] = Field(default_factory=list)
    last_event_ts: str | None = None


# 必须记录的动作 (SOP §4)
KEY_ACTIONS = frozenset({
    "card_intake_created",
    "workspace_move",
    "review_status_changed",
    "verification_run",
    "manual_verification",
    "ref_rebuild",
    "ref_review",
    "final_package_build",
    "report_download",
    "pivot_selected",
    "keyword_regenerated",
})