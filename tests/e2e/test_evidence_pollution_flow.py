from __future__ import annotations

import pytest

from conftest import load_llm_raw


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_full_graph_rejects_identity_verified_cross_domain_pollution(fixed_time) -> None:
    from paperagent.graph import build_graph
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import (
        FakeLLMProvider,
        FakeSearchProvider,
        FixtureKey,
        SearchFixtureKey,
    )
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import ResearchRequest, SearchCandidate
    from paperagent.testing import FixedClock, SequenceIdFactory

    llm = FakeLLMProvider(
        fixtures={
            FixtureKey(task="planning", scenario="happy_path", call_index=0): load_llm_raw(
                "planning", "happy_path", 0
            ),
            FixtureKey(
                task="evidence_synthesis", scenario="happy_path", call_index=0
            ): load_llm_raw("evidence_synthesis", "happy_path", 0),
            FixtureKey(task="method_design", scenario="happy_path", call_index=0): load_llm_raw(
                "method_design", "happy_path", 0
            ),
            FixtureKey(task="report", scenario="happy_path", call_index=0): load_llm_raw(
                "report", "happy_path", 0
            ),
        }
    )
    search = FakeSearchProvider(
        fixtures={
            SearchFixtureKey(scenario="happy_path", query_id="query-support-01", call_index=0): [
                SearchCandidate(
                    candidate_id="support-001",
                    query_id="query-support-01",
                    gap_id="gap-support",
                    source_type="paper",
                    title="Citation claim support evaluation",
                    locator="fixture://evidence/ev-support-001",
                    snippet="Claim support can be measured with citation evidence labels.",
                    metadata={
                        "license": "MIT",
                        "baseline_reproduced": "true",
                        "baseline_reproduced_metric": "primary_metric=0.50",
                        "baseline_compute_fit": "true",
                        "baseline_parity_verified": "true",
                        "dataset_fingerprint": "sha256:fixture-dataset",
                        "environment_fingerprint": "sha256:fixture-environment",
                    },
                ),
                SearchCandidate(
                    candidate_id="particle-physics-001",
                    query_id="query-support-01",
                    gap_id="gap-support",
                    source_type="paper",
                    title="Boson decay channels in high energy collisions",
                    locator="fixture://evidence/ev-particle-physics-001",
                    snippet="A collider physics measurement of particle decay channels.",
                ),
            ],
            SearchFixtureKey(scenario="happy_path", query_id="query-ablation-01", call_index=0): [
                SearchCandidate(
                    candidate_id="ablation-001",
                    query_id="query-ablation-01",
                    gap_id="gap-ablation",
                    source_type="paper",
                    title="Retrieval generation context ablation",
                    locator="fixture://evidence/ev-ablation-001",
                    snippet="A retrieval generation ablation separates context errors.",
                    metadata={"license": "MIT"},
                )
            ],
        }
    )
    services = RuntimeServices(
        llm,
        search,
        FixedClock(fixed_time),
        SequenceIdFactory("polluted-flow"),
        InMemoryStateStore(),
    )

    result = await build_graph().ainvoke(
        {"request": ResearchRequest(question="Evaluate citation reliability")},
        {"configurable": {"services": services, "scenario": "happy_path"}},
    )

    assert set(result["evidence"].identity_verified_ids) == {
        "ev-support-001",
        "ev-particle-physics-001",
        "ev-ablation-001",
    }
    assert set(result["evidence"].accepted_ids) == {
        "ev-support-001",
        "ev-ablation-001",
    }
    assert result["evidence"].relevance_rejected_ids == ["ev-particle-physics-001"]
    assert result["evidence"].coverage_by_gap == {
        "gap-support": 1,
        "gap-ablation": 1,
    }
    assert result["final_outcome"].scientific_verdict == "GO"
    assert result["trace_audit"].passed is True
    assert "ev-particle-physics-001" not in result["report"].evidence_ids
    assert all(
        "ev-particle-physics-001" not in claim.evidence_ids
        for claim in [
            *result["report"].verified_findings,
            *result["report"].inferred_findings,
        ]
    )
