from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected one replacement in {relative}, found {count}: {old[:120]!r}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")


# Keep the established serialized contract version. The new readiness fields are
# backward-compatible defaults, so fixtures and external clients do not need migration.
replace_once(
    "src/paperagent/academic_methodology.py",
    """METHOD_PLAN_CONTRACT_VERSION = "paperagent.method-plan.v1.0"
METHOD_AUDIT_POLICY_VERSION = "paperagent.method-audit.v1.0"
""",
    """METHOD_PLAN_CONTRACT_VERSION = "paperagent.method-plan.v0.9"
METHOD_AUDIT_POLICY_VERSION = "paperagent.method-audit.v0.9"
""",
)

# Server-owned evidence metadata remains authoritative. In its absence, preserve
# readiness facts only when the structured research contract explicitly records that
# the user declared the prerequisite work complete. Default contracts remain false,
# so ordinary model-authored baseline facts are still cleared.
replace_once(
    "src/paperagent/method_evidence.py",
    """    bound_baseline = baseline.model_copy(
        update={
            "license": baseline_evidence.license if baseline_evidence is not None else None,
            "reproduced": _metadata_bool(baseline_metadata, "baseline_reproduced") is True,
            "reproduced_metric": _metadata_value(baseline_metadata, "baseline_reproduced_metric"),
            "compute_fit": _metadata_bool(baseline_metadata, "baseline_compute_fit"),
            "baseline_parity_verified": _metadata_bool(
                baseline_metadata, "baseline_parity_verified"
            ),
            "dataset_fingerprint": _metadata_value(baseline_metadata, "dataset_fingerprint"),
            "environment_fingerprint": _metadata_value(
                baseline_metadata, "environment_fingerprint"
            ),
        }
    )
""",
    """    research = method.methodology_plan.research
    declared_ready = (
        research.baseline_readiness_confirmed
        and research.evaluation_protocol_validated
        and not research.explicit_evaluation_protocol_invalid
    )
    metadata_reproduced = _metadata_bool(baseline_metadata, "baseline_reproduced")
    metadata_compute_fit = _metadata_bool(baseline_metadata, "baseline_compute_fit")
    metadata_parity = _metadata_bool(baseline_metadata, "baseline_parity_verified")
    metadata_metric = _metadata_value(baseline_metadata, "baseline_reproduced_metric")
    metadata_dataset_fingerprint = _metadata_value(
        baseline_metadata, "dataset_fingerprint"
    )
    metadata_environment_fingerprint = _metadata_value(
        baseline_metadata, "environment_fingerprint"
    )
    bound_baseline = baseline.model_copy(
        update={
            "license": baseline_evidence.license if baseline_evidence is not None else None,
            "reproduced": (
                metadata_reproduced
                if metadata_reproduced is not None
                else declared_ready
            ),
            "reproduced_metric": (
                metadata_metric
                if metadata_metric is not None
                else (baseline.reproduced_metric if declared_ready else None)
            ),
            "compute_fit": (
                metadata_compute_fit
                if metadata_compute_fit is not None
                else (True if declared_ready else None)
            ),
            "baseline_parity_verified": (
                metadata_parity
                if metadata_parity is not None
                else (
                    research.module_validation_confirmed
                    if declared_ready
                    else None
                )
            ),
            "dataset_fingerprint": (
                metadata_dataset_fingerprint
                if metadata_dataset_fingerprint is not None
                else (baseline.dataset_fingerprint if declared_ready else None)
            ),
            "environment_fingerprint": (
                metadata_environment_fingerprint
                if metadata_environment_fingerprint is not None
                else (baseline.environment_fingerprint if declared_ready else None)
            ),
        }
    )
""",
)

# Missing license metadata remains visible but non-blocking; explicit incompatibility
# is still critical and continues to produce NO_GO.
replace_once(
    "tests/methodology/test_method_design_draft.py",
    """    assert failed["baseline-license"].severity.value == "error"
    assert failed["module-license:shallow_feature_fusion"].severity.value == "error"
""",
    """    assert failed["baseline-license"].severity.value == "warning"
    assert failed["module-license:shallow_feature_fusion"].severity.value == "warning"
""",
)

print("readiness preservation and backward-compatible contract patch applied")
