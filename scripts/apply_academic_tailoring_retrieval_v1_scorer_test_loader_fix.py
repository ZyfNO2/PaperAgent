from __future__ import annotations

from pathlib import Path


TEST_PATH = Path("tests/evals/test_academic_tailoring_retrieval_v1_scorer.py")


def main() -> int:
    source = TEST_PATH.read_text(encoding="utf-8")
    old = '''from types import SimpleNamespace

from scripts.score_academic_tailoring_retrieval_v1 import (
    _accepted_verified_items,
    _baseline_target_titles,
    _titles_related,
)
'''
    new = '''import importlib.util
from pathlib import Path
from types import SimpleNamespace

_SCORER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "score_academic_tailoring_retrieval_v1.py"
_SPEC = importlib.util.spec_from_file_location("academic_tailoring_retrieval_v1_scorer", _SCORER_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_SCORER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SCORER)

_accepted_verified_items = _SCORER._accepted_verified_items
_baseline_target_titles = _SCORER._baseline_target_titles
_titles_related = _SCORER._titles_related
'''
    if old in source:
        source = source.replace(old, new, 1)
    elif "spec_from_file_location" not in source:
        raise RuntimeError("scorer test import block not found")
    TEST_PATH.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
