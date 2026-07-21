from __future__ import annotations

from pathlib import Path

METHOD = Path("src/paperagent/method_design_draft.py")


def replace_once(old: str, new: str, label: str) -> None:
    source = METHOD.read_text(encoding="utf-8")
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise RuntimeError(f"missing {label}")
    METHOD.write_text(source, encoding="utf-8")


def main() -> int:
    replace_once(
        '''    baseline_inferred = baseline_evidence is not None and not declared_baseline_titles
    comparator = grounded_comparator if comparator_evidence_id is not None else None
''',
        '''    baseline_inferred = baseline_evidence is not None and not declared_baseline_titles
    baseline_stable_identifier = (
        baseline_evidence.stable_identifier if baseline_evidence is not None else "unresolved"
    )
    comparator = grounded_comparator if comparator_evidence_id is not None else None
''',
        "baseline stable identifier",
    )
    source = METHOD.read_text(encoding="utf-8")
    source = source.replace(
        "f\"{baseline_evidence.stable_identifier}; reproduce and freeze an \"",
        "f\"{baseline_stable_identifier}; reproduce and freeze an \"",
    )
    source = source.replace(
        "f\"published source {baseline_evidence.stable_identifier}; \"",
        "f\"published source {baseline_stable_identifier}; \"",
    )
    METHOD.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
