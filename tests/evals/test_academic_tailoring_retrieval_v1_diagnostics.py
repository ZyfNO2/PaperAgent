from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

_SCORER_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "score_academic_tailoring_retrieval_v1.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "academic_tailoring_retrieval_v1_diagnostics", _SCORER_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_SCORER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SCORER)

_baseline_identity_status = _SCORER._baseline_identity_status
_retrieval_pipeline_diagnostics = _SCORER._retrieval_pipeline_diagnostics


def _review(
    evidence_id: str,
    *,
    identity_verified: bool,
    relevance_passed: bool,
    accepted: bool,
) -> SimpleNamespace:
    return SimpleNamespace(
        evidence_id=evidence_id,
        identity_verified=identity_verified,
        relevance_passed=relevance_passed,
        accepted=accepted,
    )


def test_retrieval_diagnostics_distinguish_empty_provider_results() -> None:
    state = {"evidence": {"items": [], "accepted_ids": []}}
    trace = SimpleNamespace(evidence_reviews=[])

    diagnostic = _retrieval_pipeline_diagnostics(state, trace)

    assert diagnostic["failure_stage"] == "no_candidates_returned"
    assert diagnostic["candidate_count"] == 0
    assert diagnostic["accepted_verified_count"] == 0


def test_retrieval_diagnostics_distinguish_identity_rejection() -> None:
    state = {
        "evidence": {
            "items": [{"evidence_id": "paper-1", "source_type": "paper"}],
            "accepted_ids": [],
        }
    }
    trace = SimpleNamespace(
        evidence_reviews=[
            _review(
                "paper-1",
                identity_verified=False,
                relevance_passed=False,
                accepted=False,
            )
        ]
    )

    diagnostic = _retrieval_pipeline_diagnostics(state, trace)

    assert diagnostic["failure_stage"] == "no_identity_verified_candidates"
    assert diagnostic["identity_rejected_count"] == 1


def test_retrieval_diagnostics_distinguish_state_trace_acceptance_mismatch() -> None:
    state = {
        "evidence": {
            "items": [{"evidence_id": "paper-1", "source_type": "paper"}],
            "accepted_ids": [],
        }
    }
    trace = SimpleNamespace(
        evidence_reviews=[
            _review(
                "paper-1",
                identity_verified=True,
                relevance_passed=True,
                accepted=True,
            )
        ]
    )

    diagnostic = _retrieval_pipeline_diagnostics(state, trace)

    assert diagnostic["failure_stage"] == "state_trace_acceptance_mismatch"
    assert diagnostic["trace_accepted_count"] == 1
    assert diagnostic["state_accepted_count"] == 0


def test_title_only_case_accepts_evidence_bound_inferred_baseline() -> None:
    case = {
        "case_type": "title_only",
        "public_input": {"supplied_materials": []},
        "gold": {
            "baseline_decision": {"canonical": "Hidden Reference Baseline"},
            "expected_assets": [],
        },
    }
    source = {
        "source_type": "paper",
        "title": "A Reproducible Task-Matched Alternative",
        "metadata": {
            "baseline_candidate": "inferred",
            "relation": "baseline_role_query",
        },
    }

    status = _baseline_identity_status(
        case,
        baseline_name="A Reproducible Task-Matched Alternative",
        baseline_source_item=source,
        baseline_targets=["Hidden Reference Baseline"],
        accepted_items=[source],
    )

    assert status == "evidence_bound_alternative"


def test_declared_baseline_still_rejects_a_different_bound_paper() -> None:
    case = {
        "case_type": "baseline_with_condition",
        "public_input": {
            "supplied_materials": [{"title": "Declared Baseline", "declared_role": "baseline"}]
        },
        "gold": {
            "baseline_decision": {"canonical": "Declared Baseline"},
            "expected_assets": [],
        },
    }
    source = {
        "source_type": "paper",
        "title": "Different Paper",
        "metadata": {
            "baseline_candidate": "inferred",
            "relation": "baseline_role_query",
        },
    }

    status = _baseline_identity_status(
        case,
        baseline_name="Different Paper",
        baseline_source_item=source,
        baseline_targets=["Declared Baseline"],
        accepted_items=[source],
    )

    assert status == "mismatch"


def test_title_only_case_accepts_repo_backed_direct_baseline() -> None:
    case = {
        "case_type": "title_only",
        "public_input": {"supplied_materials": []},
        "gold": {
            "baseline_decision": {"canonical": "Reference Baseline"},
            "expected_assets": [],
        },
    }
    source = {
        "evidence_id": "ev-paper-task",
        "source_type": "paper",
        "title": "Verified Task Paper",
        "metadata": {"relation": "direct_query"},
    }
    repository = {
        "evidence_id": "ev-repository-task",
        "source_type": "repository",
        "title": "authors/task-code",
        "metadata": {
            "relation": "author_linked_from_verified_paper",
            "parent_paper_id": "paper-task",
        },
    }

    status = _baseline_identity_status(
        case,
        baseline_name="Verified Task Paper",
        baseline_source_item=source,
        baseline_targets=["Reference Baseline"],
        accepted_items=[source, repository],
    )

    assert status == "evidence_bound_alternative"
