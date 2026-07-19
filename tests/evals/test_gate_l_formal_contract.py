from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_script(name: str, path: str) -> ModuleType:
    script_path = Path(path).resolve()
    sys.path.insert(0, str(script_path.parent))
    spec = importlib.util.spec_from_file_location(name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FORMAL = _load_script("gate_l_formal_contract", "scripts/gate_l_formal_contract.py")
CATEGORIES = ("in_domain", "ood", "insufficient_evidence", "adversarial")
RUBRIC = [
    {
        "criterion": "scientific_correctness",
        "weight": 25,
        "full_credit": "correct",
        "zero_credit": "incorrect",
    },
    {
        "criterion": "claim_evidence_alignment",
        "weight": 25,
        "full_credit": "aligned",
        "zero_credit": "unsupported",
    },
    {
        "criterion": "methodological_rigor",
        "weight": 20,
        "full_credit": "rigorous",
        "zero_credit": "confounded",
    },
    {
        "criterion": "calibration_and_limits",
        "weight": 15,
        "full_credit": "calibrated",
        "zero_credit": "overclaimed",
    },
    {
        "criterion": "actionability",
        "weight": 15,
        "full_credit": "actionable",
        "zero_credit": "generic",
    },
]


def _case(case_id: str, category: str) -> dict[str, Any]:
    terminal = (
        "blocked"
        if category in {"insufficient_evidence", "adversarial"}
        else "succeeded"
    )
    return {
        "case_id": case_id,
        "version": "v3-formal-test",
        "category": category,
        "title": f"Formal {category} case",
        "task_input": "Produce an evidence-grounded research design.",
        "expected_terminals": [terminal],
        "allowed_constraints": ["Use verified evidence."],
        "acceptance_tags": [category],
        "required_evidence_properties": ["verified_sources"],
        "forbidden_evidence_properties": ["fabricated_result"],
        "budget": {
            "max_calls": 8,
            "max_total_tokens": 16000,
            "max_wall_seconds": 180,
            "max_cost_usd": 2.0,
        },
        "deterministic_checks": [
            {
                "check_id": "terminal",
                "kind": "terminal",
                "target": "terminal",
                "expected": "one_of_expected_terminals",
            },
            {
                "check_id": "budget",
                "kind": "budget",
                "target": "calls_tokens_time_cost",
                "expected": "within_limits",
            },
        ],
        "human_scoring_rubric": RUBRIC,
        "reference_evidence": [],
        "reference_provenance_note": "Agent retrieves evidence independently.",
    }


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    cases = tmp_path / "cases.jsonl"
    case_rows = [
        _case(f"formal-{category}-{index}", category)
        for category in CATEGORIES
        for index in range(4)
    ]
    cases.write_text(
        "".join(json.dumps(row) + "\n" for row in case_rows), encoding="utf-8"
    )
    digest = FORMAL._sha256(cases)
    attestation = tmp_path / "attestation.json"
    attestation.write_text(
        json.dumps(
            {
                "author_or_owner": "independent-owner",
                "role": "external holdout author",
                "authored_at_utc": "2026-07-19T00:00:00Z",
                "independent_from_remediation": True,
                "not_used_for_tuning": True,
                "no_access_to_previous_holdout_outputs": True,
                "case_file_sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    behavior = tmp_path / "behavior.py"
    behavior.write_text("POLICY = 'frozen'\n", encoding="utf-8")
    prompt = tmp_path / "planning.md"
    prompt.write_text("Frozen planning prompt\n", encoding="utf-8")
    registry = tmp_path / "registry.py"
    registry.write_text("VERSION = 'planning.test'\n", encoding="utf-8")
    price = tmp_path / "price.json"
    price.write_text("{}\n", encoding="utf-8")
    strategy = tmp_path / "strategy.json"
    strategy.write_text(
        json.dumps(
            {
                "strategy_id": "test",
                "provider": "mistral",
                "model": "test-model",
                "base_url": "https://example.invalid",
                "price_table": "price.json",
            }
        ),
        encoding="utf-8",
    )
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "holdout_version": "v3-formal-test",
                "cases": "cases.jsonl",
                "attestation": "attestation.json",
                "behavior_files": ["behavior.py"],
                "strategy_profiles": ["strategy.json"],
                "price_tables": ["price.json"],
                "required_provider_environment": ["PAPERAGENT_LLM_API_KEY"],
            }
        ),
        encoding="utf-8",
    )

    def prompt_snapshot(root: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
        return (
            {"planning": "planning.test"},
            [
                FORMAL._artifact_record(root, "planning.md", kind="prompt"),
                FORMAL._artifact_record(root, "registry.py", kind="prompt_registry"),
            ],
        )

    monkeypatch.setattr(FORMAL, "REQUIRED_BEHAVIOR_FILES", ("behavior.py",))
    monkeypatch.setattr(FORMAL, "_runtime_prompt_snapshot", prompt_snapshot)
    monkeypatch.setattr(
        FORMAL,
        "_runtime_policy_snapshot",
        lambda: {
            "method_plan_contract_version": "test",
            "method_audit_policy_version": "test",
        },
    )
    return spec, tmp_path / "manifest.json"


def test_freeze_and_verify_binds_full_artifact_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, manifest_path = _fixture(tmp_path, monkeypatch)
    manifest = FORMAL.freeze_contract(
        spec,
        manifest_path,
        source_sha="a" * 40,
        repo_root=tmp_path,
        prompt_snapshot=FORMAL._runtime_prompt_snapshot,
        policy_snapshot=FORMAL._runtime_policy_snapshot,
    )
    assert manifest["formal_contract_version"] == "gate-l.formal.v1"
    assert manifest["scientific_behavior_cutoff_sha"] == "a" * 40
    assert len(manifest["frozen_artifacts"]) == 8
    verified = FORMAL.verify_contract(
        manifest_path,
        repo_root=tmp_path,
        runtime_sha="a" * 40,
        strategy_path=Path("strategy.json"),
        price_table_path=Path("price.json"),
        prompt_snapshot=FORMAL._runtime_prompt_snapshot,
        policy_snapshot=FORMAL._runtime_policy_snapshot,
    )
    assert (
        verified["frozen_artifact_bundle_sha256"]
        == manifest["frozen_artifact_bundle_sha256"]
    )


def test_verify_rejects_changed_behavior_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, manifest_path = _fixture(tmp_path, monkeypatch)
    FORMAL.freeze_contract(
        spec,
        manifest_path,
        source_sha="a" * 40,
        repo_root=tmp_path,
        prompt_snapshot=FORMAL._runtime_prompt_snapshot,
        policy_snapshot=FORMAL._runtime_policy_snapshot,
    )
    (tmp_path / "behavior.py").write_text("POLICY = 'changed'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="frozen artifact digest mismatch"):
        FORMAL.verify_contract(
            manifest_path,
            repo_root=tmp_path,
            prompt_snapshot=FORMAL._runtime_prompt_snapshot,
            policy_snapshot=FORMAL._runtime_policy_snapshot,
        )


def test_verify_rejects_runtime_sha_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, manifest_path = _fixture(tmp_path, monkeypatch)
    FORMAL.freeze_contract(
        spec,
        manifest_path,
        source_sha="a" * 40,
        repo_root=tmp_path,
        prompt_snapshot=FORMAL._runtime_prompt_snapshot,
        policy_snapshot=FORMAL._runtime_policy_snapshot,
    )
    with pytest.raises(ValueError, match="does not match frozen"):
        FORMAL.verify_contract(
            manifest_path,
            repo_root=tmp_path,
            runtime_sha="b" * 40,
            prompt_snapshot=FORMAL._runtime_prompt_snapshot,
            policy_snapshot=FORMAL._runtime_policy_snapshot,
        )


def test_verify_rejects_unfrozen_strategy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, manifest_path = _fixture(tmp_path, monkeypatch)
    FORMAL.freeze_contract(
        spec,
        manifest_path,
        source_sha="a" * 40,
        repo_root=tmp_path,
        prompt_snapshot=FORMAL._runtime_prompt_snapshot,
        policy_snapshot=FORMAL._runtime_policy_snapshot,
    )
    with pytest.raises(ValueError, match="strategy profile is not frozen"):
        FORMAL.verify_contract(
            manifest_path,
            repo_root=tmp_path,
            strategy_path=Path("other.json"),
            prompt_snapshot=FORMAL._runtime_prompt_snapshot,
            policy_snapshot=FORMAL._runtime_policy_snapshot,
        )


def test_freeze_rejects_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, manifest_path = _fixture(tmp_path, monkeypatch)
    value = json.loads(spec.read_text(encoding="utf-8"))
    value["behavior_files"] = ["../behavior.py"]
    spec.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="safe repository-relative"):
        FORMAL.freeze_contract(
            spec,
            manifest_path,
            source_sha="a" * 40,
            repo_root=tmp_path,
            prompt_snapshot=FORMAL._runtime_prompt_snapshot,
            policy_snapshot=FORMAL._runtime_policy_snapshot,
        )


def test_freeze_requires_all_mandatory_behavior_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, manifest_path = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        FORMAL,
        "REQUIRED_BEHAVIOR_FILES",
        ("behavior.py", "required.py"),
    )
    with pytest.raises(ValueError, match="missing mandatory formal inputs"):
        FORMAL.freeze_contract(
            spec,
            manifest_path,
            source_sha="a" * 40,
            repo_root=tmp_path,
            prompt_snapshot=FORMAL._runtime_prompt_snapshot,
            policy_snapshot=FORMAL._runtime_policy_snapshot,
        )


def test_verify_rejects_manifest_field_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, manifest_path = _fixture(tmp_path, monkeypatch)
    FORMAL.freeze_contract(
        spec,
        manifest_path,
        source_sha="a" * 40,
        repo_root=tmp_path,
        prompt_snapshot=FORMAL._runtime_prompt_snapshot,
        policy_snapshot=FORMAL._runtime_policy_snapshot,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["strategy_profiles"] = ["other.json"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="strategy_profiles do not match"):
        FORMAL.verify_contract(
            manifest_path,
            repo_root=tmp_path,
            prompt_snapshot=FORMAL._runtime_prompt_snapshot,
            policy_snapshot=FORMAL._runtime_policy_snapshot,
        )


def test_verify_rejects_threshold_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, manifest_path = _fixture(tmp_path, monkeypatch)
    FORMAL.freeze_contract(
        spec,
        manifest_path,
        source_sha="a" * 40,
        repo_root=tmp_path,
        prompt_snapshot=FORMAL._runtime_prompt_snapshot,
        policy_snapshot=FORMAL._runtime_policy_snapshot,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["acceptance_thresholds"]["maximum_false_go"] = 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="acceptance thresholds"):
        FORMAL.verify_contract(
            manifest_path,
            repo_root=tmp_path,
            prompt_snapshot=FORMAL._runtime_prompt_snapshot,
            policy_snapshot=FORMAL._runtime_policy_snapshot,
        )
