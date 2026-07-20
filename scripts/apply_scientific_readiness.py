from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"expected one replacement in {relative}: {old[:100]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "src/paperagent/method_design_draft.py",
    "from paperagent.schemas.method import (\n",
    "from paperagent.scientific_readiness import derive_scientific_readiness\n"
    "from paperagent.schemas.method import (\n",
)
replace_once(
    "src/paperagent/method_design_draft.py",
    '''    if request is None or plan is None or evidence_bundle is None:
        raise ValueError("request, research plan, and evidence are required")

    accepted = tuple(evidence_bundle.accepted_items())
''',
    '''    if request is None or plan is None or evidence_bundle is None:
        raise ValueError("request, research plan, and evidence are required")

    explicit = derive_scientific_readiness(request.question)
    invalid_protocol = (
        draft.explicit_evaluation_protocol_invalid
        or explicit.explicit_evaluation_protocol_invalid
    )
    draft = draft.model_copy(
        update={
            "baseline_readiness_confirmed": (
                draft.baseline_readiness_confirmed
                or explicit.baseline_readiness_confirmed
            ),
            "evaluation_protocol_validated": (
                (
                    draft.evaluation_protocol_validated
                    or explicit.evaluation_protocol_validated
                )
                and not invalid_protocol
            ),
            "comparison_readiness_confirmed": (
                draft.comparison_readiness_confirmed
                or explicit.comparison_readiness_confirmed
            ),
            "module_validation_confirmed": (
                draft.module_validation_confirmed
                or explicit.module_validation_confirmed
            ),
            "failure_policy_confirmed": (
                draft.failure_policy_confirmed
                or explicit.failure_policy_confirmed
            ),
            "explicit_evaluation_protocol_invalid": invalid_protocol,
        }
    )

    accepted = tuple(evidence_bundle.accepted_items())
''',
)

print("scientific readiness integration applied")
