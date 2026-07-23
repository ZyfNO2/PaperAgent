from __future__ import annotations

from pathlib import Path

METHOD_TESTS = Path("tests/methodology/test_method_design_draft.py")


def apply_test_repairs() -> None:
    old = '''        coverage_by_gap={baseline_gap.gap_id: 1, mechanism_gap.gap_id: 1},
'''
    new = '''        coverage_by_gap={baseline_gap.gap_id: 2, mechanism_gap.gap_id: 1},
'''
    text = METHOD_TESTS.read_text(encoding="utf-8")
    if new in text and old not in text:
        return
    count = text.count(old)
    if count != 2:
        raise RuntimeError(f"method test derived coverage: expected two matches, found {count}")
    METHOD_TESTS.write_text(text.replace(old, new), encoding="utf-8")


if __name__ == "__main__":
    apply_test_repairs()
