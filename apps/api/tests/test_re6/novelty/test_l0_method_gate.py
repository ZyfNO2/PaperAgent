"""Re6.4.1 Method Tailoring Gate — L0 schema tests."""
from __future__ import annotations

import pytest


class TestBaselineCard:
    def test_valid_baseline(self):
        from apps.api.app.services.agents.graph.schemas.method_gate import BaselineCard
        b = BaselineCard(
            paper_id="p1", doi="10.1234/x", repo_url="https://gh.com/x",
            commit_hash="abc123", license_type="MIT",
            dataset="coco", data_split="train/val",
            environment="Python 3.12, PyTorch 2.0",
            reported_metric="mAP", reported_value="45.2",
            status="not_attempted",
        )
        assert b.status == "not_attempted"

    def test_reproduced_baseline_needs_value(self):
        from apps.api.app.services.agents.graph.schemas.method_gate import BaselineCard
        with pytest.raises(ValueError, match="reproduced_value"):
            BaselineCard(
                paper_id="p1", doi="x", repo_url="r",
                commit_hash="h", license_type="MIT",
                dataset="d", data_split="s", environment="e",
                reported_metric="m", reported_value="1",
                status="reproduced",
            )


class TestModuleCard:
    def test_valid_module(self):
        from apps.api.app.services.agents.graph.schemas.method_gate import ModuleCard
        m = ModuleCard(
            source="paper X", license_type="MIT",
            original_role="backbone", new_role="feature extractor",
            input_spec="BCHW, [0,1] normalized", output_spec="Bx512",
            dtype="float32", failure_mode="NaN on edge cases",
        )
        assert m.dtype == "float32"


class TestCompatibilityMatrix:
    def test_valid_matrix(self):
        from apps.api.app.services.agents.graph.schemas.method_gate import CompatibilityMatrix
        cm = CompatibilityMatrix(
            producer_id="A", consumer_id="B",
            semantic_unit="feature vector (512D)",
            shape_compat="A.out=B.in", normalization_compat="A.BatchNorm, B.LayerNorm",
            status="shape_only",
        )
        assert not cm.is_semantically_safe()
        cm2 = CompatibilityMatrix(
            producer_id="A", consumer_id="B",
            semantic_unit="f", shape_compat="ok", normalization_compat="ok",
            status="validated",
        )
        assert cm2.is_semantically_safe()


class TestMethodHypothesis:
    def test_valid_hypothesis(self):
        from apps.api.app.services.agents.graph.schemas.method_gate import MethodHypothesis
        h = MethodHypothesis(
            condition_c="dataset has >=1000 samples per class",
            limitation_l="fails with <100 samples",
            mechanism_m="attention heads align to category prototypes",
            intervention_b="add prototype-guided attention layer",
            observable_y="accuracy on long-tail classes increases",
            guardrail_g="accuracy on head classes must not drop >2%",
            falsifier="if ablation removes prototype guidance and accuracy doesn't change, mechanism is invalid",
        )
        assert h.guardrail_g

    def test_rejects_missing_guardrail(self):
        from apps.api.app.services.agents.graph.schemas.method_gate import MethodHypothesis
        with pytest.raises(ValueError, match="guardrail"):
            MethodHypothesis(
                condition_c="c", limitation_l="l", mechanism_m="m",
                intervention_b="b", observable_y="y",
                guardrail_g="", falsifier="f",
            )


class TestExperimentMatrix:
    def test_valid_experiment(self):
        from apps.api.app.services.agents.graph.schemas.method_gate import ExperimentMatrix
        e = ExperimentMatrix(
            frozen_baseline="commit abc123",
            fixed_split="80/10/10 stratified",
            fixed_seeds=[42, 123, 99],
            compute_budget="24h on A100 x1",
            stop_condition="if null hypothesis not rejected after 3 rounds, stop",
        )
        assert e.frozen_baseline == "commit abc123"


class TestMethodDecision:
    def test_go_without_missing_evidence(self):
        from apps.api.app.services.agents.graph.schemas.method_gate import MethodDecision
        d = MethodDecision(
            verdict="GO",
            gates_passed=["G0", "G1", "G2", "G3", "G4", "G5"],
            rationale="all gates passed",
        )
        assert d.verdict == "GO"

    def test_cannot_go_with_missing_evidence(self):
        from apps.api.app.services.agents.graph.schemas.method_gate import MethodDecision
        with pytest.raises(ValueError, match="missing evidence"):
            MethodDecision(
                verdict="GO",
                evidence_missing=["baseline reproduction"],
                rationale="should not pass",
            )

    def test_no_go_needs_stop_condition(self):
        from apps.api.app.services.agents.graph.schemas.method_gate import MethodDecision
        with pytest.raises(ValueError, match="stop_condition"):
            MethodDecision(
                verdict="NO_GO",
                evidence_missing=["data unavailable"],
                rationale="cannot proceed",
            )

    def test_revise_allowed_with_missing(self):
        from apps.api.app.services.agents.graph.schemas.method_gate import MethodDecision
        d = MethodDecision(
            verdict="REVISE",
            evidence_missing=["baseline repro needed"],
            rationale="reproduce baseline first",
        )
        assert d.verdict == "REVISE"
