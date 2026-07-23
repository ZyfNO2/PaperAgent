from __future__ import annotations

from types import SimpleNamespace

import pytest

import paperagent.nodes.method_design as method_design_module
from paperagent.graph import _after_method_design
from paperagent.method_design_deferral import classify_method_design_deferral
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceSynthesis,
    ExecutionMeta,
    NodeErrorRecord,
    ResearchPlan,
    ResearchRequest,
)


def test_deferral_classifier_keeps_schema_failures_as_implementation_failures() -> None:
    assert classify_method_design_deferral("invalid JSON returned by provider") is None
    assert classify_method_design_deferral("METHOD_CANONICALIZATION_FAILED") is None


def test_deferral_classifier_maps_independent_evidence_failure() -> None:
    assert (
        classify_method_design_deferral(
            "module_design_deferred: no independent accepted module evidence satisfies "
            "identity, relation, and relevance requirements"
        )
        == "insufficient_independent_evidence"
    )


def test_deferral_classifier_maps_contract_failures() -> None:
    assert (
        classify_method_design_deferral(
            "module_design_deferred: module_identity_not_supported, "
            "module_relation_not_independent"
        )
        == "parallel_module_identity_missing"
    )
    assert (
        classify_method_design_deferral(
            "module_design_deferred: input_shape_missing_or_generic, "
            "shape_rank_not_explicit_or_projected"
        )
        == "semantic_incompatibility"
    )
    assert (
        classify_method_design_deferral(
            "module_design_deferred: loss_terms_missing_or_generic, "
            "gradient_path_missing_or_generic"
        )
        == "objective_incompatibility"
    )


@pytest.mark.asyncio
async def test_method_design_scientific_deferral_routes_to_report_without_runtime_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {
        "request": ResearchRequest(question="test scientific method design"),
        "plan": ResearchPlan(
            status="ready",
            problem_statement="test problem",
            scope="test scope",
            evidence_gaps=[],
            search_queries=[],
            success_criteria=["test criterion"],
            risks=[],
        ),
        "evidence": EvidenceBundle(),
        "synthesis": EvidenceSynthesis(
            gap_assessments=[],
            verified_findings=[],
            conflicts=[],
            feasibility="not_feasible",
            limitations=["independent module evidence is unavailable"],
        ),
    }
    execution = ExecutionMeta(
        status="failed",
        last_error=NodeErrorRecord(
            code="insufficient_independent_evidence",
            message="module_design_deferred: no independent accepted module evidence",
            node="method_design_node",
            retryable=False,
        ),
    )

    async def fake_call_structured(**_: object):
        return {"execution": execution, "trace": []}, None

    monkeypatch.setattr(method_design_module, "call_structured", fake_call_structured)
    monkeypatch.setattr(
        method_design_module,
        "get_services",
        lambda _config: SimpleNamespace(llm=SimpleNamespace(provider_name="openai")),
    )
    monkeypatch.setattr(
        method_design_module,
        "make_event",
        lambda *_args, **kwargs: SimpleNamespace(route=kwargs.get("route")),
    )

    patch = await method_design_module.method_design_node(state, {})

    assert patch["execution"].status == "blocked"
    assert patch["quality"].verdict == "blocked"
    assert patch["quality"].reason_codes == ["insufficient_independent_evidence"]
    assert patch["trace"][-1].route == "blocked"
    assert _after_method_design({"execution": patch["execution"]}) == "blocked"
