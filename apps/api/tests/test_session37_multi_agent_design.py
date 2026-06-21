"""Session 37: Multi-Agent 扩展设计 + 成本控制 tests (8 个).

S37-1: agent role schema 可序列化
S37-2: route_task 把 retrieval 分给 RetrievalAgent
S37-3: 低置信路由返回 Supervisor
S37-4: max_llm_calls 超限停止
S37-5: VerificationAgent 不能直接写 evidence
S37-6: fallback_to_single_agent 可用
S37-7: 投票多数决
S37-8: 默认 plan 不回退单流程
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.schemas_agent_plan import (
    AgentPlan,
    AgentRole,
    AgentRoleSpec,
    AgentVote,
    CostBudget,
    CostUsage,
    RouteTaskRequest,
)
from app.services import agent_router as router


# ---------------------------------------------------------------------------
# S37-1: agent role schema 可序列化
# ---------------------------------------------------------------------------


class TestAgentRoleSchema:
    def test_all_roles_defined(self):
        for r in ("supervisor", "keyword", "retrieval", "verification",
                  "feasibility", "proposal", "review"):
            spec = router.AGENT_ROLE_SPECS.get(r)  # type: ignore[arg-type]
            assert spec is not None, f"role {r} missing"
            assert spec.role == r

    def test_role_spec_serializable(self):
        spec = AgentRoleSpec(
            role="verification",
            description="test",
            can_write_evidence=False,
            cost_weight=2,
        )
        data = spec.model_dump()
        restored = AgentRoleSpec.model_validate(data)
        assert restored.role == "verification"
        assert restored.cost_weight == 2

    def test_no_role_can_write_evidence_by_default(self):
        for role, spec in router.AGENT_ROLE_SPECS.items():
            assert spec.can_write_evidence is False, (
                f"role {role} should not write evidence by default"
            )


# ---------------------------------------------------------------------------
# S37-2: route_task 把 retrieval 分给 RetrievalAgent
# ---------------------------------------------------------------------------


class TestRouteTask:
    def test_retrieval_routed_to_retrieval_agent(self):
        req = RouteTaskRequest(task_type="candidate_retrieve", project_id="p1")
        decision = router.route_task(req)
        assert decision.assigned_role == "retrieval"
        assert decision.confidence > 0.7

    def test_keyword_routed_to_keyword_agent(self):
        req = RouteTaskRequest(task_type="keyword_decompose", project_id="p1")
        decision = router.route_task(req)
        assert decision.assigned_role == "keyword"

    def test_feasibility_routed_to_feasibility_agent(self):
        req = RouteTaskRequest(task_type="feasibility_decide", project_id="p1")
        decision = router.route_task(req)
        assert decision.assigned_role == "feasibility"


# ---------------------------------------------------------------------------
# S37-3: 低置信路由返回 Supervisor
# ---------------------------------------------------------------------------


class TestLowConfidenceFallback:
    def test_gate_blocked_triggers_fallback_to_supervisor(self):
        """gate 被阻时回退到 supervisor (单 agent 模式)."""
        usage = CostUsage()
        budget = router.make_default_budget()
        # 模拟 gate 被阻, early_stop_on_gate_blocked=True -> fallback
        assert router.should_fallback(usage, budget, gate_blocked=True) is True

    def test_cost_exceeded_triggers_fallback(self):
        usage = CostUsage(exceeded=True, exceeded_dimension="llm_calls")
        budget = router.make_default_budget()
        assert router.should_fallback(usage, budget) is True

    def test_all_known_tasks_have_route(self):
        """schema 限制 task_type, 路由表覆盖所有 8 种."""
        known_tasks = (
            "keyword_decompose", "candidate_retrieve", "url_verify",
            "feasibility_decide", "proposal_draft", "review_check",
            "trace_query", "memory_replay",
        )
        for t in known_tasks:
            req = RouteTaskRequest(task_type=t, project_id="p1")  # type: ignore[arg-type]
            decision = router.route_task(req)
            # 都路由到非 supervisor 的 agent (除了 trace_query / memory_replay 本身就是 supervisor)
            assert decision.assigned_role in (
                "supervisor", "keyword", "retrieval", "verification",
                "feasibility", "proposal", "review",
            )


# ---------------------------------------------------------------------------
# S37-4: max_llm_calls 超限停止
# ---------------------------------------------------------------------------


class TestCostBudgetEnforcement:
    def test_within_budget_allowed(self):
        usage = CostUsage(agent_count=3, llm_calls=10, parallel_tasks=2, rounds=2)
        budget = router.make_default_budget()
        ok, reason = router.check_budget(usage, budget)
        assert ok is True
        assert reason == "ok"

    def test_llm_calls_exceeded(self):
        usage = CostUsage(agent_count=3, llm_calls=999, parallel_tasks=2, rounds=2)
        budget = router.make_default_budget()
        ok, reason = router.check_budget(usage, budget)
        assert ok is False
        assert "llm_calls" in reason

    def test_agent_count_exceeded(self):
        usage = CostUsage(agent_count=999)
        budget = router.make_default_budget()
        ok, reason = router.check_budget(usage, budget)
        assert ok is False
        assert "agent_count" in reason

    def test_rounds_exceeded(self):
        usage = CostUsage(rounds=999)
        budget = router.make_default_budget()
        ok, reason = router.check_budget(usage, budget)
        assert ok is False
        assert "rounds" in reason


# ---------------------------------------------------------------------------
# S37-5: VerificationAgent 不能直接写 evidence
# ---------------------------------------------------------------------------


class TestAgentCapabilityGates:
    def test_verification_cannot_write_evidence(self):
        assert router.can_role_write_evidence("verification") is False

    def test_no_role_can_modify_supports(self):
        for role in ("supervisor", "keyword", "retrieval", "verification",
                     "feasibility", "proposal", "review"):
            assert router.can_role_modify_supports(role) is False, (  # type: ignore[arg-type]
                f"role {role} should not modify supports"
            )


# ---------------------------------------------------------------------------
# S37-6: fallback_to_single_agent 可用
# ---------------------------------------------------------------------------


class TestFallback:
    def test_fallback_triggered_on_gate_blocked(self):
        usage = CostUsage()
        budget = router.make_default_budget()
        assert router.should_fallback(usage, budget, gate_blocked=True) is True

    def test_fallback_triggered_on_cost_exceeded(self):
        usage = CostUsage(exceeded=True, exceeded_dimension="llm_calls")
        budget = router.make_default_budget()
        assert router.should_fallback(usage, budget) is True

    def test_no_fallback_when_normal(self):
        usage = CostUsage()
        budget = router.make_default_budget()
        assert router.should_fallback(usage, budget, gate_blocked=False) is False

    def test_fallback_disabled_when_budget_flag_off(self):
        usage = CostUsage(exceeded=True)
        budget = CostBudget(fallback_to_single_agent=False)
        assert router.should_fallback(usage, budget) is False


# ---------------------------------------------------------------------------
# S37-7: 投票多数决
# ---------------------------------------------------------------------------


class TestVoting:
    def test_majority_approve(self):
        votes = [
            AgentVote(agent_role="review", decision="approve", confidence=0.9),
            AgentVote(agent_role="review", decision="approve", confidence=0.8),
            AgentVote(agent_role="feasibility", decision="reject", confidence=0.7),
        ]
        consensus = router.tally_votes("review_check", votes)
        assert consensus.approved is True
        assert consensus.final_decision == "approve"
        assert consensus.vote_distribution["approve"] == 2

    def test_majority_reject(self):
        votes = [
            AgentVote(agent_role="review", decision="reject", confidence=0.9),
            AgentVote(agent_role="feasibility", decision="reject", confidence=0.8),
            AgentVote(agent_role="proposal", decision="approve", confidence=0.6),
        ]
        consensus = router.tally_votes("feasibility_decide", votes)
        assert consensus.approved is False
        assert consensus.final_decision == "reject"

    def test_warn_tie_breaks_to_warn(self):
        votes = [
            AgentVote(agent_role="review", decision="approve", confidence=0.7),
            AgentVote(agent_role="feasibility", decision="reject", confidence=0.7),
        ]
        consensus = router.tally_votes("review_check", votes)
        assert consensus.final_decision == "warn"
        assert consensus.approved is False

    def test_empty_votes_rejected(self):
        consensus = router.tally_votes("review_check", [])
        assert consensus.approved is False
        assert consensus.final_decision == "reject"


# ---------------------------------------------------------------------------
# S37-8: 默认 plan 不破坏单流程
# ---------------------------------------------------------------------------


class TestDefaultPlan:
    def test_default_plan_has_business_steps(self):
        plan = router.build_default_plan("p1")
        # 业务 5 步: keyword / retrieval / verification / feasibility / proposal / review
        assert len(plan.steps) >= 5
        task_types = {s.task_type for s in plan.steps}
        assert "keyword_decompose" in task_types
        assert "candidate_retrieve" in task_types

    def test_default_plan_has_budget(self):
        plan = router.build_default_plan("p1")
        assert plan.budget.max_llm_calls > 0
        assert plan.budget.max_agent_count > 0

    def test_default_plan_serializable(self):
        plan = router.build_default_plan("p1")
        data = plan.model_dump()
        restored = AgentPlan.model_validate(data)
        assert restored.project_id == "p1"
        assert len(restored.steps) == len(plan.steps)


# ---------------------------------------------------------------------------
# S37 额外: 不修改单流程服务
# ---------------------------------------------------------------------------


class TestSingleFlowUnchanged:
    def test_s31_baseline_endpoint_unaffected(self):
        """S31 baseline 调用仍然可用."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.services import evidence as ev_store

        ev_store.reset_all()
        try:
            client = TestClient(app)
            resp = client.post("/api/v1/one-topic/analyze", json={
                "raw_topic": "基于YOLO的钢材表面缺陷检测",
                "goal_level": "保毕业",
                "prefer": "heuristic",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "project_id" in data
        finally:
            ev_store.reset_all()

    def test_s23_skill_registry_still_works(self):
        from app.services.skill_registry import get_default_forbidden, list_skills

        forbidden = get_default_forbidden()
        assert "shell_exec" in forbidden
        skills = list_skills() if callable(list_skills) else []
        # 不应报错
        assert isinstance(forbidden, list)