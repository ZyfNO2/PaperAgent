"""Re8.1 WP3 — Tailor output quality gate tests.

Tests for Task 11 (semantic field validation) and Task 12 (assembly_plan
structure validation) implemented in ``llm_output_validator.py``.

Coverage:
- Task 11.1: 7-field non-empty check
- Task 11.2: semantic traceability (default text / title expansion / length)
- Task 11.3: generic substitute detection
- Task 12.1: assembly_plan baseline check
- Task 12.2: modules list check (name + role)
- Task 12.3: connections / integration_point check
- Task 12.4: ablation count >= 4
- Task 12.5: module details (source / io_semantics / failure_mode)

All validation is non-blocking by design — these tests exercise the pure
validation functions directly.
"""
from __future__ import annotations

from apps.api.app.services.agents.graph.validators.llm_output_validator import (
    _detect_generic_substitute,
    _validate_ablation_count,
    _validate_assembly_plan_baseline,
    _validate_assembly_plan_connections,
    _validate_assembly_plan_modules,
    _validate_module_details,
    _validate_semantic_traceability,
    _validate_tailor_fields_non_empty,
    validate_tailor_output,
)
from apps.api.app.services.agents.graph.nodes.tailor_skill_adapter import (
    _extend_tailor_with_seed_fields,
)


# ---------------------------------------------------------------------------
# Task 11.1: 7-field non-empty check
# ---------------------------------------------------------------------------

class TestTailorFieldsNonEmpty:
    def test_non_empty_all_fields_present(self):
        """All 7 required fields populated → pass."""
        tailored = {
            "task_definition": "detect small objects in aerial imagery scenes",
            "method_summary": (
                "use feature pyramid network with multi-scale attention "
                "for robust small object detection across resolutions"
            ),
            "dataset_and_metrics": {"datasets": [{"name": "DOTA"}]},
            "reproduction_environment": {"framework": "PyTorch"},
            "limitations": ["fails on very dense scenes", "high memory cost"],
            "assembly_plan": {"description": "attach FPN to RetinaNet backbone"},
            "core_method": "FPN + RetinaNet for small object detection",
        }
        passed, missing = _validate_tailor_fields_non_empty(tailored)
        assert passed is True
        assert missing == []

    def test_non_empty_missing_field(self):
        """Missing core_method → fail and report it."""
        tailored = {
            "task_definition": "detect small objects in aerial imagery scenes",
            "method_summary": (
                "use feature pyramid network with multi-scale attention "
                "for robust small object detection across resolutions"
            ),
            "dataset_and_metrics": {"datasets": [{"name": "DOTA"}]},
            "reproduction_environment": {"framework": "PyTorch"},
            "limitations": ["fails on very dense scenes"],
            "assembly_plan": {"description": "attach FPN to RetinaNet backbone"},
            # core_method intentionally omitted
        }
        passed, missing = _validate_tailor_fields_non_empty(tailored)
        assert passed is False
        assert "core_method" in missing


# ---------------------------------------------------------------------------
# Task 11.2: semantic traceability
# ---------------------------------------------------------------------------

class TestSemanticTraceability:
    def test_traceability_not_default_text(self):
        """task_definition="TBD" → fail on default text."""
        tailored = {
            "task_definition": "TBD",
            "method_summary": (
                "use feature pyramid network with multi-scale attention "
                "for robust small object detection across resolutions"
            ),
        }
        seed_papers = [{"resolved_title": "Feature Pyramid Networks"}]
        passed, issues = _validate_semantic_traceability(tailored, seed_papers)
        assert passed is False
        assert any("default text" in i for i in issues)

    def test_traceability_not_title_expansion(self):
        """method_summary Jaccard ~1.0 with title → fail (title expansion)."""
        title = "Feature Pyramid Networks for Object Detection"
        tailored = {
            "method_summary": (
                "Feature Pyramid Networks for Object Detection "
                "Feature Pyramid Networks for Object Detection"
            ),
        }
        seed_papers = [{"resolved_title": title}]
        passed, issues = _validate_semantic_traceability(tailored, seed_papers)
        assert passed is False
        assert any("Jaccard" in i and "title" in i for i in issues)

    def test_traceability_reasonable_length(self):
        """method_summary only 10 chars → fail on length."""
        tailored = {
            "method_summary": "short text",  # 10 chars < 50
        }
        seed_papers = [{"resolved_title": "Some Long Title About Methods"}]
        passed, issues = _validate_semantic_traceability(tailored, seed_papers)
        assert passed is False
        assert any("length" in i and "50" in i for i in issues)


# ---------------------------------------------------------------------------
# Task 11.3: generic substitute detection
# ---------------------------------------------------------------------------

class TestGenericSubstitute:
    def test_generic_substitute_detected(self):
        """Chinese generic phrase "添加注意力" → True."""
        assert _detect_generic_substitute("添加注意力到特征图上") is True

    def test_generic_substitute_not_detected(self):
        """Specific technical description → False."""
        assert _detect_generic_substitute(
            "使用 multi-head self-attention with 8 heads"
        ) is False


# ---------------------------------------------------------------------------
# Task 12.1: assembly_plan baseline check
# ---------------------------------------------------------------------------

class TestAssemblyPlanBaseline:
    def test_baseline_valid(self):
        """baseline="ResNet-50" → pass."""
        assembly_plan = {"baseline": "ResNet-50"}
        passed, issue = _validate_assembly_plan_baseline(assembly_plan)
        assert passed is True
        assert issue == ""

    def test_baseline_generic(self):
        """baseline="standard model" → fail."""
        assembly_plan = {"baseline": "standard model"}
        passed, issue = _validate_assembly_plan_baseline(assembly_plan)
        assert passed is False
        assert "generic" in issue


# ---------------------------------------------------------------------------
# Task 12.2: modules list check
# ---------------------------------------------------------------------------

class TestAssemblyPlanModules:
    def test_modules_valid(self):
        """modules=[{name, role}, ...] → pass."""
        assembly_plan = {
            "modules": [
                {"name": "FPN", "role": "feature pyramid"},
                {"name": "Attention", "role": "channel focus"},
            ]
        }
        passed, issues = _validate_assembly_plan_modules(assembly_plan)
        assert passed is True
        assert issues == []

    def test_modules_missing_role(self):
        """modules=[{name}] → fail on missing role."""
        assembly_plan = {"modules": [{"name": "FPN"}]}
        passed, issues = _validate_assembly_plan_modules(assembly_plan)
        assert passed is False
        assert any("role" in i for i in issues)


# ---------------------------------------------------------------------------
# Task 12.3: connections / integration_point check
# ---------------------------------------------------------------------------

class TestAssemblyPlanConnections:
    def test_connections_valid(self):
        """Each module has 'connection' → pass."""
        assembly_plan = {
            "modules": [
                {"name": "FPN", "connection": "after backbone"},
                {"name": "Attention", "integration_point": "on FPN output"},
            ]
        }
        passed, issues = _validate_assembly_plan_connections(assembly_plan)
        assert passed is True
        assert issues == []


# ---------------------------------------------------------------------------
# Task 12.4: ablation count >= 4
# ---------------------------------------------------------------------------

class TestAblationCount:
    def test_ablation_count_4(self):
        """4 ablation rows → pass."""
        tailored = {"ablation_matrix": [{"experiment_id": i} for i in range(4)]}
        passed, count = _validate_ablation_count(tailored)
        assert passed is True
        assert count == 4

    def test_ablation_count_3(self):
        """3 ablation rows → fail."""
        tailored = {"ablation_matrix": [{"experiment_id": i} for i in range(3)]}
        passed, count = _validate_ablation_count(tailored)
        assert passed is False
        assert count == 3


# ---------------------------------------------------------------------------
# Task 12.5: module details (source / io_semantics / failure_mode)
# ---------------------------------------------------------------------------

class TestModuleDetails:
    def test_module_details_valid(self):
        """Each module has source/io_semantics/failure_mode → pass."""
        assembly_plan = {
            "modules": [
                {
                    "name": "FPN",
                    "source": "paper X",
                    "io_semantics": "feature map in/out",
                    "failure_mode": "memory overflow on large inputs",
                },
            ]
        }
        passed, issues = _validate_module_details(assembly_plan)
        assert passed is True
        assert issues == []

    def test_module_details_missing_failure_mode(self):
        """Module missing failure_mode → fail."""
        assembly_plan = {
            "modules": [
                {
                    "name": "FPN",
                    "source": "paper X",
                    "io_semantics": "feature map in/out",
                    # failure_mode intentionally omitted
                },
            ]
        }
        passed, issues = _validate_module_details(assembly_plan)
        assert passed is False
        assert any("failure_mode" in i for i in issues)


# ---------------------------------------------------------------------------
# Integration: validate_tailor_output end-to-end report
# ---------------------------------------------------------------------------

class TestValidateTailorOutputReport:
    def test_report_has_all_gates(self):
        """validate_tailor_output returns a report with all gate keys."""
        tailored = {
            "task_definition": "detect small objects",
            "method_summary": "use FPN with attention for multi-scale detection here",
            "assembly_plan": {"description": "attach FPN"},
            "ablation_matrix": [{"experiment_id": i} for i in range(4)],
        }
        report = validate_tailor_output(tailored, seed_papers=[])
        expected_keys = {
            "field_non_empty",
            "semantic_traceability",
            "generic_substitute",
            "assembly_plan_baseline",
            "assembly_plan_modules",
            "assembly_plan_connections",
            "ablation_count",
            "module_details",
            "overall_passed",
        }
        assert expected_keys.issubset(report.keys())


# ---------------------------------------------------------------------------
# Task 13 (WP3 option C): _extend_tailor_with_seed_fields schema extension
# ---------------------------------------------------------------------------

class TestTask13SchemaExtension:
    """Task 13 option C: additive schema extension to unblock WP3 acceptance.

    Copies 5 fields from SeedPaperCard, derives core_method from
    assembly_plan.description, and derives assembly_plan structure fields
    (baseline / modules / connections / ablation) from existing top-level
    fields. No LLM prompt change, no breaking change to downstream consumers.
    """

    @staticmethod
    def _make_seed_card(**overrides):
        """Build a minimal SeedPaperCard with all 5 paper_understanding fields."""
        seed = {
            "seed_id": "s1",
            "resolved_title": "Feature Pyramid Networks for Object Detection",
            "role": "classic_anchor",
            "task_definition": "detect objects at multiple scales",
            "method_summary": (
                "use a feature pyramid network with lateral connections "
                "for multi-scale feature maps"
            ),
            "dataset_and_metrics": {
                "datasets": [{"name": "COCO"}],
                "metrics": [{"name": "mAP"}],
            },
            "reproduction_environment": {
                "framework": "PyTorch",
                "hardware": "V100",
            },
            "limitations": [
                "struggles with very small objects",
                "high memory cost",
            ],
        }
        seed.update(overrides)
        return seed

    def test_extend_with_seed_fields_copies_5_fields(self):
        """5 spec-required fields absent in tailored → all copied from seed."""
        tailored = {"primary_baseline": {"title": "RetinaNet"}}
        seed = self._make_seed_card()
        result = _extend_tailor_with_seed_fields(tailored, [seed])
        assert result["task_definition"] == "detect objects at multiple scales"
        assert result["method_summary"].startswith("use a feature pyramid")
        assert result["dataset_and_metrics"]["datasets"][0]["name"] == "COCO"
        assert result["reproduction_environment"]["framework"] == "PyTorch"
        assert result["limitations"] == [
            "struggles with very small objects",
            "high memory cost",
        ]

    def test_extend_with_seed_fields_no_seed_cards(self):
        """Empty seed_cards list → no crash, tailored unchanged, no marker."""
        tailored = {"primary_baseline": {"title": "RetinaNet"}}
        result = _extend_tailor_with_seed_fields(tailored, [])
        assert result is tailored
        # no seed fields added, no marker set
        assert "_seed_field_source" not in result
        assert "task_definition" not in result

    def test_extend_with_seed_fields_no_overwrite_existing(self):
        """Pre-existing task_definition must NOT be overwritten by seed."""
        tailored = {"task_definition": "my own task"}
        seed = self._make_seed_card(task_definition="seed task")
        result = _extend_tailor_with_seed_fields(tailored, [seed])
        assert result["task_definition"] == "my own task"

    def test_extend_marks_seed_field_source(self):
        """_seed_field_source set to seed_id for audit traceability."""
        tailored = {}
        seed = self._make_seed_card(seed_id="seed-42")
        result = _extend_tailor_with_seed_fields(tailored, [seed])
        assert result["_seed_field_source"] == "seed-42"

    def test_core_method_derived_from_assembly_plan_description(self):
        """core_method absent → derived from assembly_plan.description
        (consistent with content.py fallback)."""
        tailored = {
            "assembly_plan": {"description": "FPN attached to RetinaNet backbone"},
        }
        seed = self._make_seed_card()
        result = _extend_tailor_with_seed_fields(tailored, [seed])
        assert result["core_method"] == "FPN attached to RetinaNet backbone"

    def test_assembly_plan_baseline_derived_from_primary_baseline(self):
        """assembly_plan.baseline absent → derived from primary_baseline.title."""
        tailored = {
            "primary_baseline": {"title": "Faster R-CNN"},
            "assembly_plan": {"description": "attach FPN"},
        }
        seed = self._make_seed_card()
        result = _extend_tailor_with_seed_fields(tailored, [seed])
        assert result["assembly_plan"]["baseline"] == "Faster R-CNN"

    def test_assembly_plan_modules_derived_from_candidate_modules(self):
        """assembly_plan.modules absent → derived from candidate_modules
        with name + role mapping."""
        tailored = {
            "candidate_modules": [
                {"name": "FPN-lite", "target_failure_mode": "small object recall"},
                {"name": "AttentionHead", "target_failure_mode": "feature focus"},
            ],
            "assembly_plan": {"description": "attach modules"},
        }
        seed = self._make_seed_card()
        result = _extend_tailor_with_seed_fields(tailored, [seed])
        modules = result["assembly_plan"]["modules"]
        assert len(modules) == 2
        assert modules[0] == {"name": "FPN-lite", "role": "small object recall"}
        assert modules[1] == {"name": "AttentionHead", "role": "feature focus"}

    def test_assembly_plan_connections_derived_from_compatibility_analysis(self):
        """assembly_plan.connections absent → derived from
        compatibility_analysis[].interface."""
        tailored = {
            "compatibility_analysis": [
                {"interface": "feature maps after backbone"},
                {"interface": "lateral connections"},
            ],
            "assembly_plan": {"description": "attach"},
        }
        seed = self._make_seed_card()
        result = _extend_tailor_with_seed_fields(tailored, [seed])
        connections = result["assembly_plan"]["connections"]
        assert connections == [
            "feature maps after backbone",
            "lateral connections",
        ]

    def test_assembly_plan_ablation_references_top_level(self):
        """assembly_plan.ablation references top-level ablation_matrix
        (same object, not a copy)."""
        ablation_matrix = [
            {"experiment_id": "baseline"},
            {"experiment_id": "A"},
            {"experiment_id": "B"},
            {"experiment_id": "A+B"},
        ]
        tailored = {
            "ablation_matrix": ablation_matrix,
            "assembly_plan": {"description": "attach"},
        }
        seed = self._make_seed_card()
        result = _extend_tailor_with_seed_fields(tailored, [seed])
        # Same object reference (not a copy) — backward compat preserved
        assert result["assembly_plan"]["ablation"] is ablation_matrix

    def test_extend_does_not_break_existing_fields(self):
        """Additive: existing fields (verdict, generated_by, etc.) preserved
        while new fields are added."""
        tailored = {
            "verdict": "GO",
            "verdict_reason": "modules compatible",
            "generated_by": "llm",
            "primary_baseline": {"title": "RetinaNet"},
            "candidate_modules": [
                {"name": "FPN", "target_failure_mode": "recall"},
            ],
            "assembly_plan": {"description": "FPN + RetinaNet"},
            "ablation_matrix": [{"experiment_id": "baseline"}],
        }
        seed = self._make_seed_card()
        result = _extend_tailor_with_seed_fields(tailored, [seed])
        # existing fields unchanged
        assert result["verdict"] == "GO"
        assert result["verdict_reason"] == "modules compatible"
        assert result["generated_by"] == "llm"
        assert result["primary_baseline"]["title"] == "RetinaNet"
        # new fields added
        assert "task_definition" in result
        assert "core_method" in result
        assert result["assembly_plan"]["baseline"] == "RetinaNet"
        assert len(result["assembly_plan"]["modules"]) == 1
