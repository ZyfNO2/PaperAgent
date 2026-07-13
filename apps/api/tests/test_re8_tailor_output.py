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
