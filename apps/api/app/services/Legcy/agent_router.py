"""Session 37: Agent router — 任务路由 + 成本控制 + 投票 + 失败回退.

不执行实际 agent 逻辑, 只做:
  - 静态路由表: task_type -> 首选 agent
  - 成本预算检查
  - 投票共识
  - 失败回退
"""

from __future__ import annotations

import uuid
from typing import Any

from app.schemas_agent_plan import (
    AgentPlan,
    AgentPlanStep,
    AgentRole,
    AgentRoleSpec,
    AgentVote,
    CostBudget,
    CostUsage,
    RouteDecision,
    RouteTaskRequest,
    VoteConsensus,
)


# ---- Agent 角色表 ---- #


AGENT_ROLE_SPECS: dict[AgentRole, AgentRoleSpec] = {
    "supervisor": AgentRoleSpec(
        role="supervisor",
        description="流程控制，不直接生成证据",
        can_write_evidence=False,
        can_modify_supports=False,
        cost_weight=1,
    ),
    "keyword": AgentRoleSpec(
        role="keyword",
        description="题目拆解，输出 method/dataset/metric 关键词",
        can_write_evidence=False,
        cost_weight=2,
    ),
    "retrieval": AgentRoleSpec(
        role="retrieval",
        description="候选资源检索（paper/dataset/repo）",
        can_write_evidence=False,
        cost_weight=3,
    ),
    "verification": AgentRoleSpec(
        role="verification",
        description="URLVerified + Evidence 晋升前检查",
        can_write_evidence=False,
        cost_weight=2,
    ),
    "feasibility": AgentRoleSpec(
        role="feasibility",
        description="风险裁决 (可做/可改/不可做)",
        can_write_evidence=False,
        cost_weight=2,
    ),
    "proposal": AgentRoleSpec(
        role="proposal",
        description="报告草稿生成",
        can_write_evidence=False,
        cost_weight=3,
    ),
    "review": AgentRoleSpec(
        role="review",
        description="委员会复核 (低门槛)",
        can_write_evidence=False,
        cost_weight=2,
    ),
}


# ---- 路由表 ---- #


# task_type -> (首选 role, 最低置信度阈值)
TASK_TYPE_TO_ROLE: dict[str, tuple[AgentRole, float]] = {
    "keyword_decompose": ("keyword", 0.7),
    "candidate_retrieve": ("retrieval", 0.7),
    "url_verify": ("verification", 0.8),
    "feasibility_decide": ("feasibility", 0.7),
    "proposal_draft": ("proposal", 0.7),
    "review_check": ("review", 0.6),
    "trace_query": ("supervisor", 0.5),
    "memory_replay": ("supervisor", 0.5),
}


# ---- 路由 ---- #


def route_task(req: RouteTaskRequest) -> RouteDecision:
    """路由 task 到合适的 agent. 置信度不足时回退到 supervisor."""
    entry = TASK_TYPE_TO_ROLE.get(req.task_type)
    if entry is None:
        return RouteDecision(
            task_type=req.task_type,
            assigned_role="supervisor",
            confidence=0.0,
            fallback_to="supervisor",
            reason=f"unknown task_type '{req.task_type}', fallback to supervisor",
        )

    preferred, min_conf = entry
    # 简化模型: 已知 task_type 置信度 = 0.9 (常量)
    confidence = 0.9
    if confidence < min_conf:
        return RouteDecision(
            task_type=req.task_type,
            assigned_role="supervisor",
            confidence=confidence,
            fallback_to="supervisor",
            reason=f"confidence {confidence:.2f} < threshold {min_conf:.2f}, fallback",
        )

    return RouteDecision(
        task_type=req.task_type,
        assigned_role=preferred,
        confidence=confidence,
        fallback_to="supervisor",
        reason=f"task_type '{req.task_type}' routed to {preferred}",
    )


# ---- 成本控制 ---- #


def make_default_budget() -> CostBudget:
    return CostBudget()


def check_budget(usage: CostUsage, budget: CostBudget) -> tuple[bool, str]:
    """检查成本是否超限. 返回 (allowed, reason)."""
    if usage.agent_count > budget.max_agent_count:
        return False, f"agent_count {usage.agent_count} > max {budget.max_agent_count}"
    if usage.llm_calls > budget.max_llm_calls:
        return False, f"llm_calls {usage.llm_calls} > max {budget.max_llm_calls}"
    if usage.parallel_tasks > budget.max_parallel_tasks:
        return (
            False,
            f"parallel_tasks {usage.parallel_tasks} > max {budget.max_parallel_tasks}",
        )
    if usage.rounds > budget.max_rounds:
        return False, f"rounds {usage.rounds} > max {budget.max_rounds}"
    return True, "ok"


def should_fallback(usage: CostUsage, budget: CostBudget, gate_blocked: bool = False) -> bool:
    """是否回退到单 agent 模式."""
    if gate_blocked and budget.early_stop_on_gate_blocked:
        return True
    if usage.exceeded and budget.fallback_to_single_agent:
        return True
    return False


# ---- 投票 / 共识 ---- #


def tally_votes(task_type: str, votes: list[AgentVote]) -> VoteConsensus:
    """聚合多个 agent 的投票."""
    if not votes:
        return VoteConsensus(
            task_type=task_type,
            votes=[],
            final_decision="reject",
            approved=False,
            vote_distribution={},
        )

    dist: dict[str, int] = {}
    for v in votes:
        dist[v.decision] = dist.get(v.decision, 0) + 1

    # 简单多数: approve 数最多且 > reject
    approve = dist.get("approve", 0)
    reject = dist.get("reject", 0)
    warn = dist.get("warn", 0)

    if approve > reject and approve > warn:
        final = "approve"
        approved = True
    elif reject > approve:
        final = "reject"
        approved = False
    else:
        final = "warn"
        approved = False

    return VoteConsensus(
        task_type=task_type,
        votes=votes,
        final_decision=final,
        approved=approved,
        vote_distribution=dist,
    )


# ---- Plan 构造 ---- #


def build_default_plan(
    project_id: str,
    budget: CostBudget | None = None,
) -> AgentPlan:
    """构造一个默认的 multi-agent plan (走完整 SOP 流程)."""
    steps: list[AgentPlanStep] = []
    for i, (task_type, (role, _)) in enumerate(TASK_TYPE_TO_ROLE.items()):
        if task_type in ("trace_query", "memory_replay"):
            continue  # 运维类, 不进入业务 plan
        steps.append(
            AgentPlanStep(
                step_id=f"step_{i:02d}_{task_type}",
                role=role,
                task_type=task_type,  # type: ignore[arg-type]
                depends_on=[],
                parallel_group=i,
                estimated_cost=AGENT_ROLE_SPECS[role].cost_weight,
            )
        )
    return AgentPlan(
        plan_id=f"plan_{uuid.uuid4().hex[:10]}",
        project_id=project_id,
        steps=steps,
        budget=budget or make_default_budget(),
    )


# ---- Agent 能力检查 ---- #


def can_role_write_evidence(role: AgentRole) -> bool:
    return AGENT_ROLE_SPECS[role].can_write_evidence


def can_role_modify_supports(role: AgentRole) -> bool:
    return AGENT_ROLE_SPECS[role].can_modify_supports


def role_cost_weight(role: AgentRole) -> int:
    return AGENT_ROLE_SPECS[role].cost_weight
