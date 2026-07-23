from __future__ import annotations

from pathlib import Path

from evidence_bound_module_prepatch import replace_exact

METHOD_TESTS = Path("tests/methodology/test_method_design_draft.py")


def apply_test_repairs() -> None:
    replace_exact(
        METHOD_TESTS,
        '''        coverage_by_gap={baseline_gap.gap_id: 1, mechanism_gap.gap_id: 1},
''',
        '''        coverage_by_gap={baseline_gap.gap_id: 2, mechanism_gap.gap_id: 1},
''',
        "method test derived coverage",
    )


if __name__ == "__main__":
    apply_test_repairs()
