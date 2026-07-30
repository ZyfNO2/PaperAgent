from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperagent.academic.acceptance import load_tailoring_acceptance_package, main

SCENARIOS = Path("evals/academic_rag_h3/scenarios.v1.json")


def test_frozen_scenarios_are_explicitly_blocked_by_human_review() -> None:
    package = load_tailoring_acceptance_package(SCENARIOS)
    assert package.status == "blocked_by_human_review"
    assert len(package.scenarios) == 2
    assert len(package.missing_human_fields) == 6
    assert all(scenario.expected_decision is None for scenario in package.scenarios)


def test_runner_writes_bounded_evidence_package(tmp_path: Path) -> None:
    output = tmp_path / "package.json"
    assert main([str(SCENARIOS), "--output", str(output)]) == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "academic-h3-acceptance.v1"
    assert payload["status"] == "blocked_by_human_review"
    assert "source_digest" in payload


def test_runner_rejects_non_two_scenario_input(tmp_path: Path) -> None:
    payload = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    payload["scenarios"] = payload["scenarios"][:1]
    candidate = tmp_path / "one.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly two"):
        load_tailoring_acceptance_package(candidate)
