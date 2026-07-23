from __future__ import annotations

from pathlib import Path

PATH = Path("tests/evals/test_academic_tailoring_retrieval_v1_scorer.py")
TEST = '''


def test_module_review_requires_parallel_role_and_explicit_compatibility() -> None:
    review = SimpleNamespace(
        evidence_id="ev-module",
        accepted=True,
        identity_verified=True,
        relevance_passed=True,
        role="parallel_method",
        role_compatible=True,
    )
    assert review.role == "parallel_method"
    assert review.role_compatible is True
'''


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if "def test_module_review_requires_parallel_role_and_explicit_compatibility" not in text:
        PATH.write_text(text.rstrip() + TEST + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
