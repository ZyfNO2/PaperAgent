from __future__ import annotations

import pytest

from conftest import load_llm_raw


def _base_state(fixed_time, accepted_evidence_payload, *, scenario="happy_path"):
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider, FixtureKey
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import (
        EvidenceBundle,
        ExecutionMeta,
        ResearchPlan,
        RunBudgets,
        RunContext,
    )
    from paperagent.testing import FixedClock, SequenceIdFactory

    fixtures = {
        FixtureKey(task="evidence_synthesis", scenario=scenario, call_index=0): load_llm_raw(
            "evidence_synthesis", scenario, 0
        ),
        FixtureKey(task="method_design", scenario="happy_path", call_index=0): load_llm_raw(
            "method_design", "happy_path", 0
        ),
        FixtureKey(task="report", scenario="happy_path", call_index=0): load_llm_raw(
            "report", "happy_path", 0
        ),
        FixtureKey(task="report", scenario="blocked", call_index=0): load_llm_raw(
            "report", "blocked", 0
        ),
    }
    services = RuntimeServices(
        FakeLLMProvider(fixtures=fixtures),
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    plan = ResearchPlan.model_validate_json(load_llm_raw("planning", "happy_path", 0))
    state = {
        "run": RunContext(
            run_id="run-1",
            thread_id="thread-1",
            created_at=fixed_time,
            model_profile="fake",
            network_policy="offline",
            budgets=RunBudgets(),
        ),
        "plan": plan,
        "evidence": EvidenceBundle.model_validate(accepted_evidence_payload),
        "execution": ExecutionMeta(status="running"),
        "trace": [],
    }
    return state, services


@pytest.mark.asyncio
async def test_evidence_synthesis_node__accepted_only__returns_semantically_valid_output(
    fixed_time, accepted_evidence_payload
) -> None:
    from paperagent.nodes.evidence_synthesis import evidence_synthesis_node

    state, services = _base_state(fixed_time, accepted_evidence_payload)
    patch = await evidence_synthesis_node(
        state, {"configurable": {"services": services, "scenario": "happy_path"}}
    )
    assert patch["synthesis"].feasibility == "feasible"
    assert "ev-rejected-001" not in patch["synthesis"].referenced_evidence_ids()
    assert services.llm.calls[0].message_count == 2


@pytest.mark.asyncio
async def test_evidence_synthesis_node__unknown_evidence_id__returns_typed_failure(
    fixed_time, accepted_evidence_payload
) -> None:
    from paperagent.nodes.evidence_synthesis import evidence_synthesis_node

    state, services = _base_state(
        fixed_time, accepted_evidence_payload, scenario="unknown_evidence"
    )
    patch = await evidence_synthesis_node(
        state, {"configurable": {"services": services, "scenario": "unknown_evidence"}}
    )
    assert patch["execution"].last_error.code == "SEMANTIC_UNKNOWN_EVIDENCE_ID"


@pytest.mark.asyncio
async def test_method_quality_report__happy_path__passes_and_preserves_evidence(
    fixed_time, accepted_evidence_payload
) -> None:
    from paperagent.nodes.evidence_synthesis import evidence_synthesis_node
    from paperagent.nodes.method_design import method_design_node
    from paperagent.nodes.quality_gate import quality_gate_node
    from paperagent.nodes.report import report_node
    from paperagent.state import apply_state_patch

    state, services = _base_state(fixed_time, accepted_evidence_payload)
    state = apply_state_patch(
        state,
        await evidence_synthesis_node(
            state, {"configurable": {"services": services, "scenario": "happy_path"}}
        ),
    )
    state = apply_state_patch(
        state,
        await method_design_node(
            state, {"configurable": {"services": services, "scenario": "happy_path"}}
        ),
    )
    state = apply_state_patch(
        state, await quality_gate_node(state, {"configurable": {"services": services}})
    )
    assert state["quality"].verdict == "pass"
    patch = await report_node(
        state, {"configurable": {"services": services, "scenario": "happy_path"}}
    )
    assert patch["report"].status == "completed"
    assert set(patch["report"].evidence_ids) <= set(state["evidence"].accepted_ids)


def test_quality_gate__missing_coverage__repairs_then_blocks_after_budget(
    fixed_time, accepted_evidence_payload
) -> None:
    from paperagent.nodes.quality_gate import evaluate_quality
    from paperagent.schemas import EvidenceBundle, RetrievalState

    state, _ = _base_state(fixed_time, accepted_evidence_payload)
    state["evidence"] = EvidenceBundle()
    state["retrieval"] = RetrievalState(round=1, max_rounds=2)
    first = evaluate_quality(state)
    assert first.verdict == "repair_retrieval"
    state["retrieval"] = RetrievalState(round=2, max_rounds=2, budget_exhausted=True)
    second = evaluate_quality(state)
    assert second.verdict == "blocked"
    assert "Q_RETRIEVAL_BUDGET_EXHAUSTED" in second.reason_codes


@pytest.mark.asyncio
async def test_persist_node__same_state__is_idempotent(
    fixed_time, accepted_evidence_payload
) -> None:
    from paperagent.nodes.persist import persist_node
    from paperagent.schemas import FinalReport

    state, services = _base_state(fixed_time, accepted_evidence_payload)
    state["report"] = FinalReport.model_validate_json(load_llm_raw("report", "blocked", 0))
    first = await persist_node(state, {"configurable": {"services": services}})
    second = await persist_node(state, {"configurable": {"services": services}})
    assert first["execution"].status == second["execution"].status == "blocked"
    assert len(services.store.snapshots) == 1
