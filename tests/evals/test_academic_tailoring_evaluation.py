from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperagent.academic_tailoring import ResultStatus, TailoringDecision
from paperagent.academic_tailoring_evaluation import (
    evaluate_corpus,
    grade_proposal,
    load_case_specs,
)
from paperagent.academic_tailoring_fixtures import load_tailoring_task_bundle
from paperagent.academic_tailoring_guard import compose_tailored_research_proposal
from paperagent.plugins import (
    AcademicMethodTailoringPlugin,
    PluginError,
    PluginErrorCode,
    PluginRequest,
)

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_ROOT = _ROOT / "evals" / "academic_tailoring" / "npc"
_CASES = _ROOT / "evals" / "academic_tailoring" / "cases.json"
_SNAPSHOTS = _ROOT / "evals" / "academic_tailoring" / "snapshots"


def _main_snapshot(proposal: object) -> dict[str, object]:
    value = proposal.model_dump(mode="json")  # type: ignore[attr-defined]
    return {
        "academic_story": value["academic_story"],
        "baseline": {
            "method_name": value["baseline"]["method_name"],
            "paper_id": value["baseline"]["paper_id"],
            "reproduced": value["baseline"]["reproduced"],
            "reproduced_metrics": value["baseline"]["reproduced_metrics"],
        },
        "blockers": value["blockers"],
        "decision": value["decision"],
        "expected_results": value["expected_results"],
        "experiment_arm_types": [item["arm_type"] for item in value["experiment_matrix"]],
        "idea_id": value["idea_id"],
        "innovation": value["innovation_points"][0],
        "modules": [
            {
                key: item[key]
                for key in (
                    "compatibility_status",
                    "failure_mode",
                    "insertion_point",
                    "method_used",
                    "predicted_effect",
                    "proposed_role",
                    "source_paper_id",
                )
            }
            for item in value["modules"]
        ],
        "references": [
            {
                key: item[key]
                for key in (
                    "borrowed_component",
                    "method_used",
                    "paper_id",
                    "title",
                    "use_in_proposal",
                )
            }
            for item in value["references"]
        ],
        "risks": value["risks"],
        "strongest_reason": value["strongest_reason"],
    }


def test_local_proposal_contains_references_methods_innovation_story_and_targets() -> None:
    task = load_tailoring_task_bundle(_FIXTURE_ROOT)

    proposal = compose_tailored_research_proposal(task)

    assert proposal.decision is TailoringDecision.GO
    assert {reference.paper_id for reference in proposal.references} == {
        "SYN-A",
        "SYN-B",
        "SYN-C",
        "SYN-D",
    }
    assert {reference.method_used for reference in proposal.references} == {
        "Behavior Cloning Policy",
        "Semantic Action Mask",
        "Uncertainty-Gated Residual Policy",
        "Shift-Robust Ensemble Policy",
    }
    assert {module.source_paper_id for module in proposal.modules} == {"SYN-B", "SYN-C"}
    assert proposal.innovation_points[0].why_not_simple_splice
    assert proposal.academic_story.problem
    assert proposal.academic_story.gap
    assert proposal.academic_story.mechanism
    assert proposal.academic_story.intervention
    assert all(result.status is ResultStatus.PROPOSED for result in proposal.expected_results)
    assert {arm.arm_type for arm in proposal.experiment_matrix} == {
        "baseline",
        "single_module",
        "full",
        "leave_one_out",
        "strong_comparison",
        "interaction",
    }


def test_plugin_propose_uses_the_same_local_generation_path() -> None:
    task = load_tailoring_task_bundle(_FIXTURE_ROOT)
    plugin = AcademicMethodTailoringPlugin()

    result = plugin.invoke(
        PluginRequest(
            request_id="proposal-1",
            operation="propose",
            payload=task.model_dump(mode="json"),
        )
    )

    assert "propose" in plugin.manifest.operations
    assert result.output["decision"] == "GO"
    assert len(result.output["references"]) == 4
    assert len(result.output["modules"]) == 2
    assert result.evidence["llm_used"] is False
    assert result.evidence["result_status"] == "simulated_or_proposed"


def test_plugin_propose_wraps_generation_failure_in_plugin_error() -> None:
    task = load_tailoring_task_bundle(_FIXTURE_ROOT)
    payload = task.model_dump(mode="json")
    payload["reproduction"]["baseline_paper_id"] = "SYN-MISSING"
    plugin = AcademicMethodTailoringPlugin()

    with pytest.raises(PluginError) as caught:
        plugin.invoke(
            PluginRequest(
                request_id="proposal-missing-baseline",
                operation="propose",
                payload=payload,
            )
        )

    assert caught.value.code is PluginErrorCode.INVOCATION_FAILED
    assert caught.value.plugin_name == "academic-method-tailoring"


def test_committed_corpus_generates_and_passes_all_expected_decisions() -> None:
    base = load_tailoring_task_bundle(_FIXTURE_ROOT)
    specs = load_case_specs(_CASES)

    report, tasks, proposals = evaluate_corpus(base, specs)

    assert report.total == 8
    assert report.passed == 8
    assert report.failed == 0
    assert len(tasks) == len(proposals) == 8
    assert {grade.observed_decision for grade in report.grades} == {
        TailoringDecision.GO,
        TailoringDecision.REVISE,
        TailoringDecision.NO_GO,
    }


def test_main_case_output_matches_committed_snapshot() -> None:
    task = load_tailoring_task_bundle(_FIXTURE_ROOT)
    proposal = compose_tailored_research_proposal(task)
    expected = json.loads((_SNAPSHOTS / "main-case-expected.json").read_text(encoding="utf-8"))

    assert _main_snapshot(proposal) == expected


def test_report_summary_matches_committed_snapshot() -> None:
    base = load_tailoring_task_bundle(_FIXTURE_ROOT)
    specs = load_case_specs(_CASES)
    report, _, _ = evaluate_corpus(base, specs)
    expected = json.loads((_SNAPSHOTS / "report-summary.json").read_text(encoding="utf-8"))
    observed = {
        "cases": [
            {
                "case_id": grade.case_id,
                "category": grade.category,
                "expected_decision": grade.expected_decision.value,
                "observed_decision": grade.observed_decision.value,
                "passed": grade.passed,
                "score": grade.score,
            }
            for grade in report.grades
        ],
        "corpus_digest": report.corpus_digest,
        "failed": report.failed,
        "passed": report.passed,
        "total": report.total,
    }

    assert observed == expected


def test_evaluator_rejects_unverified_result_presented_as_observed() -> None:
    base = load_tailoring_task_bundle(_FIXTURE_ROOT)
    spec = load_case_specs(_CASES)[0]
    proposal = compose_tailored_research_proposal(base)
    first = proposal.expected_results[0].model_copy(
        update={"status": ResultStatus.OBSERVED, "evidence_id": None}
    )
    dishonest = proposal.model_copy(
        update={"expected_results": (first, *proposal.expected_results[1:])}
    )

    grade = grade_proposal(spec, base, dishonest)

    assert not grade.passed
    assert any("unverified result" in item for item in grade.hard_blockers)


def test_evaluator_rejects_go_output_with_missing_method_attribution() -> None:
    base = load_tailoring_task_bundle(_FIXTURE_ROOT)
    spec = load_case_specs(_CASES)[0]
    proposal = compose_tailored_research_proposal(base)
    incomplete = proposal.model_copy(update={"references": proposal.references[:-1]})

    grade = grade_proposal(spec, base, incomplete)

    assert not grade.passed
    assert any("missing attribution" in item for item in grade.hard_blockers)
