"""Session 27: RunEvent Schema (SOP §2).

RunEvent = 事件持久化单元。
字段：event_id, seq, run_id, project_id, step_key, event_type, status, payload, ts, source
RunStatus = pending | running | completed | failed | aborted
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


RunStatus = Literal["pending", "running", "completed", "failed", "aborted"]


class RunEvent(BaseModel):
    """事件持久化单元 — 流式 run 的每一个事件."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(description="事件唯一 ID")
    seq: int = Field(ge=0, description="序列号（run 内唯一递增）")
    run_id: str = Field(description="所属 run ID")
    project_id: str = Field(description="所属项目 ID")
    step_key: str = Field(description="步骤标识（keyword_review / query_plan / ...）")
    event_type: str = Field(description="事件类型")
    status: RunStatus = Field(default="running")
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: str = Field(description="ISO 时间戳")
    source: str = Field(default="server", description="事件来源")


class RunState(BaseModel):
    """Run 状态快照 — 持久化到 state.json."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    project_id: str
    status: RunStatus = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    last_seq: int = 0
    last_step_key: str | None = None
    user_patches: int = 0


class RunCreateRequest(BaseModel):
    """POST /runs 请求体."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    run_id: str | None = Field(default=None, description="自定义 run_id，None 则自动生成")
    initial_step: str | None = Field(default=None, description="初始 step_key")
    mock_mode: bool = Field(default=False, description="模拟模式（不调 LLM）")


class RunCreateResponse(BaseModel):
    """POST /runs 响应体."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    project_id: str
    status: RunStatus
    events_url: str
    stream_url: str


class RunEventListResponse(BaseModel):
    """GET /events 响应体."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    project_id: str
    total: int
    last_seq: int
    status: RunStatus
    events: list[RunEvent]


class RunEventAppendRequest(BaseModel):
    """POST /runs/{run_id}/events 请求体（追加事件）."""

    model_config = ConfigDict(extra="forbid")

    step_key: str
    event_type: str
    status: RunStatus = "running"
    payload: dict[str, Any] = Field(default_factory=dict)
    source: str = "server"


class RunEventAppendResponse(BaseModel):
    """POST /runs/{run_id}/events 响应体."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    seq: int
    run_id: str
    status: RunStatus


class RunResumeRequest(BaseModel):
    """POST /runs/{run_id}/resume 请求体 — 用户 patch + 重放策略."""

    model_config = ConfigDict(extra="forbid")

    from_seq: int = Field(default=0, ge=0, description="从此序列号开始重放")
    user_patch: dict[str, Any] = Field(default_factory=dict, description="用户对 run 的修正")
    strategy: Literal["replay", "continue", "branch"] = "continue"
    skip_steps: list[str] = Field(default_factory=list, description="跳过的 step_key 列表")
