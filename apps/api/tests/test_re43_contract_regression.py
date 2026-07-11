"""Re4.3: Offline contract regression for historical cases.

Validates that schema upgrades don't break existing case data.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.api.app.services.agents.graph.schemas.evidence_schema import (
    BindingValidationResult,
    InnovationPoint,
    WorkPackage,
)
from apps.api.app.services.agents.graph.validators.binding_validator import run_full_validation
from apps.api.app.services.agents.graph.validators.dependency_dag import build_dag

EVAL_DIR = Path("tmp_re13_eval")

HISTORICAL_CASES = [
    "re41-verify-001",
    "04d365f121bc",
    "re43-verify-001",
]


def _load_state(case_id: str) -> dict:
    path = EVAL_DIR / case_id / "state.json"
    if not path.exists():
        pytest.skip(f"Case {case_id} not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


class TestContractRegression:
    @pytest.mark.parametrize("case_id", HISTORICAL_CASES)
    def test_state_json_loads(self, case_id: str) -> None:
        """state.json must be loadable."""
        state = _load_state(case_id)
        assert isinstance(state, dict)

    @pytest.mark.parametrize("case_id", HISTORICAL_CASES)
    def test_innovation_points_backward_compatible(self, case_id: str) -> None:
        """Old innovation_points dicts must be accepted by InnovationPoint schema."""
        state = _load_state(case_id)
        innovations = state.get("innovation_points") or []
        for raw in innovations:
            ip = InnovationPoint(**{k: v for k, v in raw.items() if k in InnovationPoint.model_fields})
            assert ip.description

    @pytest.mark.parametrize("case_id", HISTORICAL_CASES)
    def test_work_packages_backward_compatible(self, case_id: str) -> None:
        """Old work_packages dicts must be accepted by WorkPackage schema."""
        state = _load_state(case_id)
        packages = state.get("work_packages") or []
        for raw in packages:
            wp = WorkPackage(**{k: v for k, v in raw.items() if k in WorkPackage.model_fields})
            assert wp.title

    @pytest.mark.parametrize("case_id", HISTORICAL_CASES)
    def test_binding_validator_runs_on_old_data(self, case_id: str) -> None:
        """Binding validator must not crash on old case data."""
        state = _load_state(case_id)
        result = run_full_validation(state)
        assert isinstance(result, BindingValidationResult)

    @pytest.mark.parametrize("case_id", HISTORICAL_CASES)
    def test_dag_builder_runs_on_old_data(self, case_id: str) -> None:
        """DAG builder must not crash on old case data."""
        state = _load_state(case_id)
        packages = state.get("work_packages") or []
        dag = build_dag(packages)
        assert "nodes" in dag
        assert "edges" in dag
        assert "topo_order" in dag
        assert "milestones" in dag
