"""Session 37: Multi-Agent 扩展设计 + 成本控制 Playwright E2E (5 条).

S37-PW-1: agent_router 模块可导入
S37-PW-2: 7 个 agent role 都有 spec
S37-PW-3: cost budget 默认值合理
S37-PW-4: MultiAgent_Expansion_Design 文档存在
S37-PW-5: 不修改 S31 单流程 (回归检查)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))


# ------------------------------------------------------------------- #
# S37-PW-1: agent_router 模块可导入
# ------------------------------------------------------------------- #


class TestAgentRouterImportable:
    def test_router_importable(self):
        from app.services import agent_router
        assert hasattr(agent_router, "route_task")
        assert hasattr(agent_router, "check_budget")
        assert hasattr(agent_router, "tally_votes")
        assert hasattr(agent_router, "build_default_plan")


# ------------------------------------------------------------------- #
# S37-PW-2: 7 个 agent role 都有 spec
# ------------------------------------------------------------------- #


class TestAgentRoleSpecs:
    def test_all_7_roles_have_specs(self):
        from app.services.agent_router import AGENT_ROLE_SPECS
        assert len(AGENT_ROLE_SPECS) >= 7
        expected = ("supervisor", "keyword", "retrieval", "verification",
                    "feasibility", "proposal", "review")
        for r in expected:
            assert r in AGENT_ROLE_SPECS

    def test_no_agent_can_write_evidence(self):
        """关键不变量: 任何 agent 都不能直接写 evidence."""
        from app.services.agent_router import AGENT_ROLE_SPECS
        for role, spec in AGENT_ROLE_SPECS.items():
            assert spec.can_write_evidence is False, (
                f"role {role} must not write evidence directly"
            )


# ------------------------------------------------------------------- #
# S37-PW-3: cost budget 默认值合理
# ------------------------------------------------------------------- #


class TestCostBudget:
    def test_default_budget_values(self):
        from app.services.agent_router import make_default_budget
        b = make_default_budget()
        assert b.max_agent_count >= 5
        assert b.max_llm_calls >= 10
        assert b.max_rounds >= 3
        assert b.fallback_to_single_agent is True
        assert b.early_stop_on_gate_blocked is True


# ------------------------------------------------------------------- #
# S37-PW-4: 文档存在
# ------------------------------------------------------------------- #


class TestMultiAgentDoc:
    def test_expansion_design_doc_exists(self):
        doc = ROOT / "docs" / "interview" / "MultiAgent_Expansion_Design.md"
        assert doc.exists(), f"MultiAgent_Expansion_Design.md missing at {doc}"
        content = doc.read_text(encoding="utf-8")
        assert "Supervisor" in content or "supervisor" in content
        assert "成本" in content or "cost" in content.lower()
        assert "fallback" in content.lower() or "降级" in content


# ------------------------------------------------------------------- #
# S37-PW-5: S31 单流程不受影响
# ------------------------------------------------------------------- #


class TestSingleFlowStillWorks:
    def test_analyze_endpoint_returns_200(self, page: Page):
        result = page.evaluate("""
            () => fetch('http://127.0.0.1:18181/api/v1/one-topic/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    raw_topic: '基于YOLO的钢材表面缺陷检测',
                    goal_level: '保毕业',
                    prefer: 'heuristic'
                })
            }).then(r => r.json())
        """)
        assert "project_id" in result
        assert "feasibility" in result