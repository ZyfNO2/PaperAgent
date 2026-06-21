"""Session 37: Multi-Agent 扩展设计的 Pydantic schema.

不直接执行多 Agent, 而是定义 role / route / cost budget / fallback 规则.
让外部面试可讲、未来可逐步落地.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---- Agent 角色 ---- #

AgentRole = Literal[
    "supervisor",
    "keyword",
    "retrieval",
    "verification",
    "feasibility",
    "proposal",
    "review",
]


class AgentRoleSpec(BaseModel):
    """Agent 角色描述."""

    model_config = ConfigDict(extra="forbid")

    role: AgentRole
    description: str
    can_write_evidence: bool = False
    can_call_llm: bool = True
    can_modify_supports: bool = False
    cost_weight: int = 1  # 用于成本预算分配


# ---- 路由 ---- #


class RouteTaskRequest(BaseModel):
    """路由一个 task 到合适的 agent."""

    model_config = ConfigDict(extra="forbid")

    task_type: Literal[
        "keyword_decompose",
        "candidate_retrieve",
        "url_verify",
        "feasibility_decide",
        "proposal_draft",
        "review_check",
        "trace_query",
        "memory_replay",
    ]
    project_id: str
    payload: dict = Field(default_factory=dict)


class RouteDecision(BaseModel):
    """路由决策."""

    model_config = ConfigDict(extra="forbid")

    task_type: str
    assigned_role: AgentRole
    confidence: float  # 0.0 - 1.0
    fallback_to: AgentRole = "supervisor"  # 置信度低时回退目标
    reason: str


# ---- 成本控制 ---- #


class CostBudget(BaseModel):
    """单次 multi-agent run 的成本预算."""

    model_config = ConfigDict(extra="forbid")

    max_agent_count: int = 8
    max_llm_calls: int = 20
    max_parallel_tasks: int = 3
    max_rounds: int = 5
    fallback_to_single_agent: bool = True
    early_stop_on_gate_blocked: bool = True


class CostUsage(BaseModel):
    """实际使用情况."""

    model_config = ConfigDict(extra="forbid")

    agent_count: int = 0
    llm_calls: int = 0
    parallel_tasks: int = 0
    rounds: int = 0
    exceeded: bool = False
    exceeded_dimension: str = ""
    fallback_triggered: bool = False


# ---- 投票 / 冲突解决 ---- #


class AgentVote(BaseModel):
    """单个 agent 的投票结果."""

    model_config = ConfigDict(extra="forbid")

    agent_role: AgentRole
    decision: str  # "approve" / "reject" / "warn"
    confidence: float
    evidence_id: str | None = None
    reason: str = ""


class VoteConsensus(BaseModel):
    """多 agent 投票后的共识."""

    model_config = ConfigDict(extra="forbid")

    task_type: str
    votes: list[AgentVote]
    final_decision: str
    approved: bool
    vote_distribution: dict[str, int] = Field(default_factory=dict)


# ---- Plan 状态 ---- #


class AgentPlanStep(BaseModel):
    """Multi-agent plan 中的一个 step."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    role: AgentRole
    task_type: str
    depends_on: list[str] = Field(default_factory=list)
    parallel_group: int = 0
    estimated_cost: int = 1


class AgentPlan(BaseModel):
    """完整的 multi-agent plan."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    project_id: str
    steps: list[AgentPlanStep]
    budget: CostBudget
    notes: str = ""
