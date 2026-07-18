from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperagent.academic_tailoring import (
    EvidenceScope,
    EvidenceState,
    ProposalReadiness,
    TailoringDecision,
    TailoringTask,
    compose_tailored_research_proposal,
)
from paperagent.academic_tailoring_guard import (
    compose_tailored_research_proposal as compatibility_compose,
)
from paperagent.api import SQLiteReviewRepository, SQLiteTaskRepository
from paperagent.api.diagnostics import collect_runtime_diagnostics
from paperagent.plugins.academic_method import (
    AcademicMethodTailoringPlugin,
    AuditVerdict,
    MethodPlan,
    audit_method_plan,
)
from paperagent.plugins.academic_method_guard import (
    AcademicMethodTailoringPlugin as CompatibilityPlugin,
)
from paperagent.plugins.academic_method_guard import (
    audit_method_plan as compatibility_audit,
)
from paperagent.plugins.contracts import PluginRequest

_ROOT = Path(__file__).resolve().parents[2]
_TAILORING_TASK = _ROOT / "evals" / "academic_tailoring" / "npc"
_GO_PLAN = _ROOT / "examples" / "v0_8" / "go-plan.json"


def _load_tailoring_payload() -> dict[str, object]:
    from paperagent.academic_tailoring_fixtures import load_tailoring_task_bundle

    return load_tailoring_task_bundle(_TAILORING_TASK).model_dump(mode="json")


def _load_go_plan() -> dict[str, object]:
    parsed = json.loads(_GO_PLAN.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _failed_check_ids(plan_payload: dict[str, object]) -> set[str]:
    report = audit_method_plan(MethodPlan.model_validate(plan_payload))
    return {item.check_id for item in report.checks if not item.passed}


def test_policy_compatibility_modules_do_not_rebind_core_symbols() -> None:
    assert compatibility_compose is compose_tailored_research_proposal
    assert compatibility_audit is audit_method_plan
    assert CompatibilityPlugin is AcademicMethodTailoringPlugin


def test_synthetic_go_is_explicitly_not_scientific_release_ready() -> None:
    task = TailoringTask.model_validate(_load_tailoring_payload())

    proposal = compose_tailored_research_proposal(task)

    assert proposal.decision is TailoringDecision.GO
    assert proposal.evidence_scope is EvidenceScope.SYNTHETIC_EVALUATION
    assert proposal.readiness is ProposalReadiness.SYNTHETIC_EVALUATION_ONLY
    assert proposal.scientific_release_ready is False
    assert any("verified real-world evidence" in item for item in proposal.release_conditions)

    plugin = AcademicMethodTailoringPlugin()
    result = plugin.invoke(
        PluginRequest(
            request_id="synthetic-readiness",
            operation="propose",
            payload=task.model_dump(mode="json"),
        )
    )
    assert result.evidence["evidence_scope"] == "synthetic_evaluation"
    assert result.evidence["readiness"] == "synthetic_evaluation_only"
    assert result.evidence["scientific_release_ready"] is False


def test_mixed_real_and_synthetic_cards_are_not_reported_as_real_verified() -> None:
    payload = _load_tailoring_payload()
    papers = payload["papers"]
    assert isinstance(papers, list)
    first = papers[0]
    assert isinstance(first, dict)
    first["evidence_state"] = EvidenceState.VERIFIED.value

    proposal = compose_tailored_research_proposal(TailoringTask.model_validate(payload))

    assert proposal.evidence_scope is EvidenceScope.MIXED_OR_UNVERIFIED
    assert proposal.readiness is ProposalReadiness.SYNTHETIC_EVALUATION_ONLY
    assert proposal.scientific_release_ready is False


def test_real_verified_cards_are_only_ready_for_controlled_experiment() -> None:
    payload = _load_tailoring_payload()
    papers = payload["papers"]
    assert isinstance(papers, list)
    for paper in papers:
        assert isinstance(paper, dict)
        paper["evidence_state"] = EvidenceState.VERIFIED.value
    task = TailoringTask.model_validate(payload)

    proposal = compose_tailored_research_proposal(task)

    assert proposal.decision is TailoringDecision.GO
    assert proposal.evidence_scope is EvidenceScope.REAL_VERIFIED
    assert proposal.readiness is ProposalReadiness.READY_FOR_CONTROLLED_EXPERIMENT
    assert proposal.scientific_release_ready is False
    assert any("fixed baseline" in item for item in proposal.release_conditions)


def test_novelty_composition_variants_require_revision() -> None:
    payload = _load_tailoring_payload()
    payload["novelty_thesis"] = "We stack the existing modules."
    payload["why_not_simple_splice"] = "This is a combination of two components."

    proposal = compose_tailored_research_proposal(TailoringTask.model_validate(payload))

    assert proposal.decision is TailoringDecision.REVISE
    assert any("module composition" in item for item in proposal.risks)


def test_tailoring_contract_rejects_duplicate_stable_identifiers() -> None:
    payload = _load_tailoring_payload()
    papers = payload["papers"]
    assert isinstance(papers, list)
    first = papers[0]
    second = papers[1]
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    second["stable_identifier"] = first["stable_identifier"]

    with pytest.raises(ValueError, match="duplicate stable paper identifier"):
        TailoringTask.model_validate(payload)


def test_tailoring_contract_rejects_duplicate_seeds() -> None:
    payload = _load_tailoring_payload()
    payload["seeds"] = [1, 1]

    with pytest.raises(ValueError, match="seeds must be non-empty and unique"):
        TailoringTask.model_validate(payload)


def test_tailoring_contract_rejects_nonfinite_targets() -> None:
    payload = _load_tailoring_payload()
    expected_results = payload["expected_results"]
    assert isinstance(expected_results, list)
    first = expected_results[0]
    assert isinstance(first, dict)
    first["target_value"] = float("nan")

    with pytest.raises(ValueError, match="finite number"):
        TailoringTask.model_validate(payload)


def test_method_audit_requires_machine_verifiable_provenance() -> None:
    payload = _load_go_plan()
    evidence = payload["evidence"]
    assert isinstance(evidence, list)
    baseline_evidence = evidence[0]
    assert isinstance(baseline_evidence, dict)
    baseline_evidence["stable_identifier"] = None
    baseline_evidence["supported_claims"] = []

    report = audit_method_plan(MethodPlan.model_validate(payload))

    assert report.verdict is AuditVerdict.NO_GO
    assert "baseline-provenance" in {item.check_id for item in report.checks if not item.passed}


def test_method_audit_rejects_unfair_budget_and_unknown_modules() -> None:
    payload = _load_go_plan()
    experiments = payload["experiments"]
    assert isinstance(experiments, list)
    full = next(item for item in experiments if isinstance(item, dict) and item["name"] == "full")
    full["tuning_budget"] = "Unlimited trials"
    full["included_modules"] = ["support-scorer", "undeclared-module"]

    failures = _failed_check_ids(payload)

    assert "experiment-fairness" in failures
    assert "experiment-module-references" in failures


def test_trainable_module_requires_an_explicit_loss() -> None:
    payload = _load_go_plan()
    modules = payload["modules"]
    assert isinstance(modules, list)
    module = modules[0]
    assert isinstance(module, dict)
    module["loss_terms"] = []

    failures = _failed_check_ids(payload)

    assert "module-contract:support-scorer" in failures


def test_experiment_contract_rejects_duplicate_comparison_values() -> None:
    payload = _load_go_plan()
    experiments = payload["experiments"]
    assert isinstance(experiments, list)
    experiment = experiments[0]
    assert isinstance(experiment, dict)
    experiment["seeds"] = [1, 1]

    with pytest.raises(ValueError, match="duplicate seed"):
        MethodPlan.model_validate(payload)


def test_runtime_diagnostics_reports_actual_sqlite_journal_mode(tmp_path: Path) -> None:
    database = tmp_path / "paperagent.db"
    repository = SQLiteTaskRepository(database)
    SQLiteReviewRepository(repository)

    snapshot = collect_runtime_diagnostics(database)

    assert snapshot["database"]["journal_mode"] == "wal"


def test_proposal_fingerprint_covers_non_plan_proposal_content() -> None:
    original_payload = _load_tailoring_payload()
    changed_payload = _load_tailoring_payload()
    changed_reproduction = changed_payload["reproduction"]
    assert isinstance(changed_reproduction, dict)
    changed_reproduction["implementation_ref"] = "different-implementation-reference"

    original = compose_tailored_research_proposal(TailoringTask.model_validate(original_payload))
    changed = compose_tailored_research_proposal(TailoringTask.model_validate(changed_payload))

    assert original.plan_fingerprint == changed.plan_fingerprint
    assert original.proposal_fingerprint != changed.proposal_fingerprint


def test_baseline_decision_uses_full_canonical_audit() -> None:
    payload = _load_tailoring_payload()
    papers = payload["papers"]
    assert isinstance(papers, list)
    baseline = papers[0]
    assert isinstance(baseline, dict)
    baseline["license"] = "proprietary-no-reuse"

    proposal = compose_tailored_research_proposal(TailoringTask.model_validate(payload))

    assert proposal.decision is TailoringDecision.NO_GO
    assert proposal.baseline.decision == "not ready for modification"
