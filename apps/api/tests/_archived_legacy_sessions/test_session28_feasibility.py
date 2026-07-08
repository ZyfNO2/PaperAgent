"""Session 28: 可行性风险裁决测试 (SOP §6, 8 tests).

覆盖：
1. 无数据集 -> PIVOT/STOP（不得 GO）
2. 有数据集无 baseline -> CONDITIONAL/PIVOT
3. 证据齐全 -> GO
4. URL 未验证 -> 不得 GO
5. fatal 维度覆盖总分
6. PIVOT 至少三条路线
7. 每条建议绑定 evidence_refs 或 missing_evidence
8. S26 EvidenceRef 不回退
"""

from __future__ import annotations


from app.schemas_feasibility import (
    FeasibilityInput,
    assess_feasibility,
)
from app.schemas_evidence_promotion import (
    PromotionGateInput,
    promote_to_evidence,
)


# ---------- S28-B-1: 无数据集 -> PIVOT/STOP ---------- #


class TestNoDataset:
    def test_no_dataset_blocks_go(self):
        inp = FeasibilityInput(
            topic_title="Steel Defect Detection",
            has_dataset=False,
            has_baseline=True,
            has_metrics=True,
            has_experiment_plan=True,
            has_verified_urls=True,
            evidence_count=5,
        )
        result = assess_feasibility(inp)
        assert result.verdict != "GO", "Without dataset, verdict must not be GO"
        # Should trigger no_dataset veto
        veto_rules = [v.rule for v in result.hard_vetoes if v.triggered]
        assert "no_dataset" in veto_rules

    def test_no_dataset_no_metrics_no_baseline_is_stop(self):
        inp = FeasibilityInput(
            topic_title="Vague Topic",
            has_dataset=False,
            has_baseline=False,
            has_metrics=False,
            has_experiment_plan=False,
            has_verified_urls=False,
            evidence_count=0,
        )
        result = assess_feasibility(inp)
        assert result.verdict in ("STOP", "PIVOT"), f"Expected STOP or PIVOT, got {result.verdict}"
        assert result.overall_score < 30


# ---------- S28-B-2: 有数据集无 baseline -> CONDITIONAL/PIVOT ---------- #


class TestDatasetNoBaseline:
    def test_dataset_no_baseline_not_go(self):
        inp = FeasibilityInput(
            topic_title="Steel Defect Detection",
            has_dataset=True,
            has_baseline=False,
            has_metrics=True,
            has_experiment_plan=True,
            has_verified_urls=True,
            evidence_count=4,
        )
        result = assess_feasibility(inp)
        assert result.verdict != "GO", "Without baseline, verdict must not be GO"
        veto_rules = [v.rule for v in result.hard_vetoes if v.triggered]
        assert "no_baseline" in veto_rules

    def test_dataset_no_baseline_has_pivot_routes(self):
        inp = FeasibilityInput(
            topic_title="Steel Defect Detection",
            has_dataset=True,
            has_baseline=False,
            has_metrics=False,
            has_experiment_plan=True,
            has_verified_urls=True,
            evidence_count=3,
        )
        result = assess_feasibility(inp)
        assert result.verdict in ("CONDITIONAL", "PIVOT")
        if result.verdict == "PIVOT":
            assert len(result.pivot_routes) >= 3


# ---------- S28-B-3: 证据齐全 -> GO ---------- #


class TestFullEvidenceGo:
    def test_all_conditions_met_is_go(self):
        inp = FeasibilityInput(
            topic_title="Steel Defect Detection with YOLOv8",
            has_dataset=True,
            has_baseline=True,
            has_metrics=True,
            has_experiment_plan=True,
            has_verified_urls=True,
            evidence_count=5,
            evidence_refs=[
                {"evidence_id": "ev_1", "title": "Dataset"},
                {"evidence_id": "ev_2", "title": "Baseline Paper"},
                {"evidence_id": "ev_3", "title": "Method Paper"},
                {"evidence_id": "ev_4", "title": "Evaluation Protocol"},
                {"evidence_id": "ev_5", "title": "Code Repository"},
            ],
        )
        result = assess_feasibility(inp)
        assert result.verdict == "GO", f"Expected GO, got {result.verdict}"
        assert result.overall_score >= 70
        assert len(result.bound_evidence) == 5


# ---------- S28-B-4: URL 未验证 -> 不得 GO ---------- #


class TestURLNotVerified:
    def test_no_verified_urls_blocks_go(self):
        inp = FeasibilityInput(
            topic_title="Steel Defect Detection",
            has_dataset=True,
            has_baseline=True,
            has_metrics=True,
            has_experiment_plan=True,
            has_verified_urls=False,
            evidence_count=5,
        )
        result = assess_feasibility(inp)
        assert result.verdict != "GO"
        veto_rules = [v.rule for v in result.hard_vetoes if v.triggered]
        assert "no_verified_urls" in veto_rules


# ---------- S28-B-5: fatal 维度覆盖总分 ---------- #


class TestFatalDimension:
    def test_fatal_dimension_forces_non_go(self):
        """EvidenceSupport < 20 = fatal -> not GO."""
        inp = FeasibilityInput(
            topic_title="Steel Defect Detection",
            has_dataset=True,
            has_baseline=True,
            has_metrics=True,
            has_experiment_plan=True,
            has_verified_urls=True,
            evidence_count=0,  # 0 EvidenceRef -> EvidenceSupport = 0 (fatal)
        )
        result = assess_feasibility(inp)
        ev_dim = next(d for d in result.dimensions if d.dimension == "EvidenceSupport")
        assert ev_dim.level == "fatal"
        assert result.verdict != "GO"


# ---------- S28-B-6: PIVOT 至少三条路线 ---------- #


class TestPivotRoutes:
    def test_pivot_has_three_routes(self):
        inp = FeasibilityInput(
            topic_title="Steel Defect Detection",
            has_dataset=False,
            has_baseline=False,
            has_metrics=False,
            has_experiment_plan=False,
            has_verified_urls=False,
            evidence_count=0,
        )
        result = assess_feasibility(inp)
        if result.verdict in ("PIVOT", "PARK", "STOP"):
            assert len(result.pivot_routes) >= 3, "Should have at least 3 pivot routes"
            types = [r.route_type for r in result.pivot_routes]
            assert "conservative" in types
            assert "balanced" in types
            assert "aggressive" in types

    def test_go_has_no_pivot_routes(self):
        inp = FeasibilityInput(
            topic_title="Steel Defect Detection with YOLOv8",
            has_dataset=True,
            has_baseline=True,
            has_metrics=True,
            has_experiment_plan=True,
            has_verified_urls=True,
            evidence_count=5,
            evidence_refs=[{"evidence_id": f"ev_{i}"} for i in range(5)],
        )
        result = assess_feasibility(inp)
        if result.verdict == "GO":
            assert len(result.pivot_routes) == 0


# ---------- S28-B-7: 每条建议绑定 evidence_refs 或 missing ---------- #


class TestEvidenceBinding:
    def test_dimensions_have_evidence_or_missing(self):
        inp = FeasibilityInput(
            topic_title="Steel Defect Detection",
            has_dataset=True,
            has_baseline=False,
            has_metrics=True,
            has_experiment_plan=False,
            has_verified_urls=True,
            evidence_count=2,
            evidence_refs=[
                {"evidence_id": "ev_1", "title": "Dataset"},
                {"evidence_id": "ev_2", "title": "Method"},
            ],
        )
        result = assess_feasibility(inp)
        for dim in result.dimensions:
            # Each dimension should have either evidence_refs or missing_evidence or suggestion
            has_content = (
                len(dim.evidence_refs) > 0
                or len(dim.missing_evidence) > 0
                or len(dim.suggestion) > 0
            )
            assert has_content, f"Dimension {dim.dimension} has no evidence refs, missing, or suggestion"

    def test_pivot_routes_have_required_evidence(self):
        inp = FeasibilityInput(
            topic_title="Steel Defect Detection",
            has_dataset=False,
            has_baseline=False,
            has_metrics=False,
            has_experiment_plan=False,
            has_verified_urls=False,
            evidence_count=0,
        )
        result = assess_feasibility(inp)
        if result.pivot_routes:
            for route in result.pivot_routes:
                assert len(route.required_evidence) > 0, f"{route.route_type} route should list required evidence"


# ---------- S28-B-8: S26 EvidenceRef 不回退 ---------- #


class TestS26NoRegression:
    def test_s26_promotion_still_works(self):
        """S26 promote_to_evidence 不受影响."""
        inp = PromotionGateInput(
            candidate_id="cand_001",
            candidate_title="Test Paper",
            is_selected=True,
            selected_id="sel_001",
            url_verification_status="verified",
            user_confirmed=True,
        )
        result = promote_to_evidence(inp)
        assert result.status == "promoted"
        assert result.evidence_ref is not None
        assert result.evidence_ref.review_status == "pending"


# ---------- Extra: 7 dimensions always present ---------- #


class TestSevenDimensions:
    def test_always_seven_dimensions(self):
        """无论输入如何，始终返回 7 个维度."""
        inp = FeasibilityInput(
            topic_title="Any Topic",
            has_dataset=False,
            has_baseline=False,
            has_metrics=False,
            has_experiment_plan=False,
            has_verified_urls=False,
            evidence_count=0,
        )
        result = assess_feasibility(inp)
        assert len(result.dimensions) == 7
        dim_names = [d.dimension for d in result.dimensions]
        expected = [
            "EvidenceSupport", "DataAvailability", "BaselineReadiness",
            "ExperimentalClarity", "ScopeControl", "ResourceFit", "NoveltyDifferentiation",
        ]
        assert dim_names == expected
