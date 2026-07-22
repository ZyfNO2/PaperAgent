from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "project_academic_tailoring_retrieval_v1.py"
AUTHORING_COMMIT = "a" * 40


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("project_academic_tailoring_retrieval_v1", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dataset() -> dict[str, object]:
    case_types = [
        "title_only",
        "title_only",
        "title_only",
        "title_only",
        "baseline_with_condition",
        "baseline_with_condition",
        "baseline_with_condition",
        "baseline_plus_parallel_paper",
        "baseline_plus_parallel_paper",
        "baseline_plus_parallel_paper",
    ]
    cases = []
    for index, case_type in enumerate(case_types, start=1):
        materials = []
        if case_type != "title_only":
            materials.append({"title": f"Baseline {index}", "declared_role": "baseline"})
        if case_type == "baseline_plus_parallel_paper":
            materials.append({"title": f"Parallel {index}", "declared_role": "parallel"})
        cases.append(
            {
                "case_id": f"atr-v1-{index:03d}-fixture",
                "case_type": case_type,
                "domain": f"domain-{index}",
                "public_input": {
                    "user_input": f"Public request {index}",
                    "supplied_materials": materials,
                    "declared_constraints": [f"constraint-{index}"],
                },
                "gold": {
                    "expected_assets": [{"kind": "paper", "title": f"Secret paper {index}"}],
                    "baseline_decision": {"canonical": f"Secret baseline {index}"},
                    "reference_hypothesis": (
                        f"Secret hypothesis {index} that must not cross the execution boundary"
                    ),
                    "compatibility_judgment": {"verdict": "secret"},
                    "experiments": ["secret experiment"],
                    "hard_failures": ["secret failure"],
                },
            }
        )
    return {
        "schema": "paperagent.academic-tailoring-retrieval.authoring.v1",
        "dataset_id": "academic_tailoring_retrieval_v1",
        "rubric": {
            "weights": {
                "paper_identity_and_citation_truth": 15,
                "baseline_selection": 15,
                "dataset_truth_and_task_fit": 10,
                "repository_truth_and_relation": 10,
                "gap_analysis": 10,
                "module_provenance_and_role": 10,
                "semantic_and_interface_compatibility": 15,
                "falsifiable_hypothesis": 5,
                "experiment_and_ablation_design": 10,
            }
        },
        "cases": cases,
    }


def test_projection_contains_only_public_contract() -> None:
    module = _load_script()
    public = module.project_public_dataset(_dataset(), authoring_commit=AUTHORING_COMMIT)
    serialized = json.dumps(public, ensure_ascii=False)
    assert '"gold"' not in serialized
    assert "Secret paper" not in serialized
    assert "Secret baseline" not in serialized
    assert public["cases"][4]["benchmark_input"]["supplied_material_titles"] == ["Baseline 5"]
    assert public["cases"][4]["benchmark_input"]["declared_constraints"] == ["constraint-5"]
    assert len(public["public_sha256"]) == 64


def test_projection_is_invariant_to_all_gold_string_mutations() -> None:
    module = _load_script()
    canary_range = module.verify_gold_mutation_invariance(
        _dataset(), authoring_commit=AUTHORING_COMMIT
    )
    assert canary_range.startswith("LEAK_CANARY_00001..")


def test_forbidden_public_key_is_rejected() -> None:
    module = _load_script()
    public = module.project_public_dataset(_dataset(), authoring_commit=AUTHORING_COMMIT)
    public["cases"][0]["benchmark_input"]["gold"] = {"answer": "leak"}
    with pytest.raises(ValueError, match="forbidden key"):
        module._assert_no_forbidden_keys(public)
