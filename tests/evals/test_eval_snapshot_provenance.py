from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from paperagent.eval_runtime_reporting import validate_public_dataset_digest

ROOT = Path(__file__).parents[2]
PROJECT_SCRIPT = ROOT / "scripts" / "project_academic_tailoring_retrieval_v1.py"
BUILD_SCRIPT = ROOT / "scripts" / "build_eval_snapshot.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate_eval_snapshot.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _authoring() -> dict[str, object]:
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
        materials: list[dict[str, str]] = []
        if case_type != "title_only":
            materials.append({"title": f"Baseline {index}", "declared_role": "baseline"})
        if case_type == "baseline_plus_parallel_paper":
            materials.append({"title": f"Parallel {index}", "declared_role": "parallel_method"})
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
                "gold": {"expected_assets": [{"title": f"Secret {index}"}]},
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


def test_projection_preserves_constraints_and_closes_digest_chain() -> None:
    project = _load("project_eval", PROJECT_SCRIPT)
    authoring = _authoring()
    public = project.project_public_dataset(authoring, authoring_commit="a" * 40)

    assert public["cases"][0]["benchmark_input"]["declared_constraints"] == ["constraint-1"]
    assert public["generated_from"]["authoring_commit"] == "a" * 40
    assert len(public["generated_from"]["authoring_sha256"]) == 64
    assert validate_public_dataset_digest(public) == public["public_sha256"]


def test_projection_rejects_invalid_material_and_duplicate_case_id() -> None:
    project = _load("project_eval_invalid", PROJECT_SCRIPT)
    authoring = _authoring()
    authoring["cases"][4]["public_input"]["supplied_materials"][0]["title"] = ""
    with pytest.raises(ValueError, match="supplied title"):
        project.project_public_dataset(authoring, authoring_commit="a" * 40)

    duplicate = _authoring()
    duplicate["cases"][1]["case_id"] = duplicate["cases"][0]["case_id"]
    with pytest.raises(ValueError, match="case IDs must be unique"):
        project.project_public_dataset(duplicate, authoring_commit="a" * 40)


def test_snapshot_builder_and_validator_round_trip(tmp_path: Path) -> None:
    project = _load("project_eval_snapshot", PROJECT_SCRIPT)
    build = _load("build_eval_snapshot", BUILD_SCRIPT)
    validate = _load("validate_eval_snapshot", VALIDATE_SCRIPT)

    authoring = _authoring()
    public = project.project_public_dataset(authoring, authoring_commit="a" * 40)
    authoring_path = tmp_path / "dataset-authoring.json"
    public_path = tmp_path / "public-dataset.json"
    authoring_path.write_text(json.dumps(authoring), encoding="utf-8")
    public_path.write_text(json.dumps(public), encoding="utf-8")

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for name in ("states.jsonl", "run-traces.jsonl", "prompt-log.jsonl"):
        (run_dir / name).write_text("{}\n", encoding="utf-8")
    selected_ids = [str(case["case_id"]) for case in public["cases"]]
    summary = {
        "schema": "paperagent.academic-tailoring-retrieval.runtime-summary.v1",
        "source_sha": "b" * 40,
        "public_dataset_sha256": public["public_sha256"],
        "selected_case_count": 10,
        "selected_case_ids": selected_ids,
        "attempted_case_ids": selected_ids,
        "completed": 10,
        "runtime_errors": 0,
        "errors": [],
        "started_at": "2026-07-23T00:00:00+00:00",
        "completed_at": "2026-07-23T00:02:00+00:00",
        "duration_seconds": 120.0,
    }
    (run_dir / "execution-summary.json").write_text(json.dumps(summary), encoding="utf-8")
    diagnostic_path = tmp_path / "diagnostic.json"
    diagnostic_path.write_text(json.dumps({"passed": True}), encoding="utf-8")

    snapshot = build.build_snapshot(
        run_id="run-20260723-test",
        run_dir=run_dir,
        public_dataset_path=public_path,
        authoring_dataset_path=authoring_path,
        diagnostic_report_path=diagnostic_path,
        output_root=tmp_path / "snapshots",
        run_source_commit="b" * 40,
        snapshot_commit="c" * 40,
        source_branch="fixture",
        scorer_version="v2",
    )
    result = validate.validate_snapshot(
        snapshot_dir=snapshot,
        authoring_path=authoring_path,
    )

    assert snapshot.name == "run-20260723-test-completed"
    assert result["passed"] is True


def test_public_dataset_tamper_is_rejected() -> None:
    project = _load("project_eval_tamper", PROJECT_SCRIPT)
    public = project.project_public_dataset(_authoring(), authoring_commit="a" * 40)
    public["cases"][0]["benchmark_input"]["user_input"] = "tampered"
    with pytest.raises(ValueError, match="digest"):
        validate_public_dataset_digest(public)
