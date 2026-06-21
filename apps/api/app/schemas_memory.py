"""Session 35: Agent Memory / Transcript / Replay Schemas.

四层记忆：
1. ShortContext — 当前浏览器状态（不可持久）
2. Transcript — RunEvent JSONL（可 replay）
3. ProjectMemory — 项目级摘要（跨 session 保留）
4. EvidenceMemory — EvidenceRef/URLVerified/Promotion（最高可信）
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Memory Layers
# ---------------------------------------------------------------------------


MemoryLayer = Literal["short_context", "transcript", "project_memory", "evidence_memory"]


class ShortContextEntry(BaseModel):
    """ShortContext 状态条目 — 浏览器 step deck 运行时."""

    model_config = ConfigDict(extra="forbid")

    step_key: str
    state: dict[str, Any] = Field(default_factory=dict)
    last_updated: str


class TranscriptEvent(BaseModel):
    """Transcript 单条事件 — RunEvent 持久化格式."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    seq: int
    run_id: str
    project_id: str
    step_key: str
    event_type: str
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: str
    source: str = "server"

    # 压缩标记
    is_critical: bool = Field(
        default=False,
        description="关键事件（gate / user_patch / promotion）不被压缩",
    )
    is_compressed: bool = Field(
        default=False,
        description="是否已被压缩成摘要",
    )


# ---------------------------------------------------------------------------
# Project Memory
# ---------------------------------------------------------------------------


class ProjectMemorySnapshot(BaseModel):
    """项目级记忆快照 — 跨 session 保留.

    关键设计：把 token 重的 fields（long abstracts, full report markdown）从 RunEvent
    里剥离到 snapshot，避免 replay 时回放太多冗余数据。
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str
    snapshot_id: str
    created_at: str

    # 项目核心信息
    raw_topic: str
    normalized_topic: str | None = None
    goal_level: str | None = None

    # 关键词 / 检索计划
    confirmed_keywords: dict[str, Any] = Field(default_factory=dict)
    confirmed_search_plan: dict[str, Any] = Field(default_factory=dict)

    # 候选资源状态
    candidate_count: int = 0
    paper_candidates: int = 0
    dataset_candidates: int = 0
    repo_candidates: int = 0

    # 证据状态
    evidence_count: int = 0
    accepted_evidence: int = 0
    core_evidence: int = 0
    rejected_evidence: int = 0

    # 可行性 / 报告
    feasibility_verdict: str | None = None
    proposal_markdown: str | None = None
    proposal_markdown_tokens: int = 0

    # 检查
    last_readiness_status: str | None = None

    # 压缩元信息
    compressed_event_count: int = 0
    last_compressed_seq: int = 0


# ---------------------------------------------------------------------------
# Evidence Memory
# ---------------------------------------------------------------------------


class EvidenceMemoryEntry(BaseModel):
    """EvidenceMemory 单元 — 不可压缩/不可覆盖的记忆."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    project_id: str
    evidence_type: str
    title: str
    url: str | None = None
    review_status: str
    verification_status: str | None = None
    promotion_history: list[dict[str, Any]] = Field(default_factory=list)
    url_verified_at: str | None = None

    # 不可变性标记
    is_immutable: bool = Field(
        default=True,
        description="EvidenceMemory 不会被普通压缩覆盖",
    )


# ---------------------------------------------------------------------------
# Compression
# ---------------------------------------------------------------------------


class CompressionConfig(BaseModel):
    """压缩策略配置."""

    model_config = ConfigDict(extra="forbid")

    max_events_before_compress: int = Field(default=200, ge=10, le=10000)
    keep_critical_types: list[str] = Field(
        default_factory=lambda: [
            "user_patch",
            "gate",
            "evidence_promotion",
            "url_verified",
            "readiness_check",
            "llm_call",
        ]
    )
    keep_last_n: int = Field(default=50, ge=1, le=500)


class CompressionResult(BaseModel):
    """压缩结果."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    run_id: str
    compressed_count: int
    kept_critical_count: int
    kept_recent_count: int
    snapshot_id: str
    compressed_at: str


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


class ReplayRequest(BaseModel):
    """POST /memory/replay 请求体."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    run_id: str | None = None
    from_seq: int = 0
    strategy: Literal["replay", "continue", "branch"] = "replay"
    skip_steps: list[str] = Field(default_factory=list)


class ReplayState(BaseModel):
    """Replay 后的状态 — 用作前端恢复 step deck."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    run_id: str
    strategy: str
    snapshot: ProjectMemorySnapshot | None = None
    recent_events: list[TranscriptEvent] = Field(default_factory=list)
    step_states: dict[str, dict[str, Any]] = Field(default_factory=dict)
    last_seq: int = 0
    replay_source: Literal["snapshot", "transcript", "both"] = "both"


# ---------------------------------------------------------------------------
# Memory Query
# ---------------------------------------------------------------------------


class MemoryQueryRequest(BaseModel):
    """GET /memory 层查询."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    layers: list[MemoryLayer] = Field(
        default_factory=lambda: ["project_memory", "evidence_memory"]
    )
    include_compressed: bool = True


class MemoryQueryResponse(BaseModel):
    """Memory 查询响应."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    snapshot: ProjectMemorySnapshot | None = None
    evidence_memory: list[EvidenceMemoryEntry] = Field(default_factory=list)
    transcript_size: int = 0
    compressed_size: int = 0