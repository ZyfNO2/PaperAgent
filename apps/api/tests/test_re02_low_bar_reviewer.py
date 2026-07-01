"""Re02 Low-bar Reviewer tests (apps/api/app/services/agents/low_bar_reviewer).

Covers deterministic-fallback path:
1. chat_json_strict raising LLMUnavailable triggers _deterministic_verdict
2. empty baseline -> 'needs_revision'
3. baseline>=1 AND core>=1 AND weak_points<=1 -> 'pass'
4. summary is a short string
5. LLMUnavailable is importable from app.services.llm
"""

from __future__ import annotations

import pytest

from app.services.agents.low_bar_reviewer import LowBarVerdict, run_low_bar_review
from app.services.llm import LLMUnavailable


pytestmark = pytest.mark.re02


def _raise_unavailable(*_a, **_kw):
    raise LLMUnavailable("test: LLM forced unavailable")


def _synthesize_with_baseline(n_baseline: int) -> dict:
    baseline = [{"title": f"Baseline-{i}"} for i in range(n_baseline)]
    return {
        "direction_recommendation": "heuristic test",
        "baseline_options": baseline,
        "paper_groups": {
            "baseline": baseline,
            "parallel": [],
            "reference": [],
            "long_tail_candidates": [],
        },
        "evidence_gaps": [],
        "work_suggestions": [],
        "manual_questions": [],
    }


def test_llm_unavailable_is_importable_from_llm():
    assert LLMUnavailable is not None


def test_deterministic_needs_revision_when_baseline_empty():
    out = run_low_bar_review(
        parsed_topic={"raw_topic": "x"},
        synthesize_output=_synthesize_with_baseline(0),
        evidence_review_stats={"core": 1, "candidate": 0, "needs_manual": 0, "rejected": 0},
        candidate_pool_stats={"paper": 1, "dataset": 0, "repo": 0},
        chat_json_strict=_raise_unavailable,
    )
    assert isinstance(out, LowBarVerdict)
    assert out.review_verdict == "needs_revision"


def test_deterministic_pass_when_baseline_and_core_and_few_weak_points():
    er_stats = {"core": 2, "candidate": 1, "needs_manual": 0, "rejected": 0}
    out = run_low_bar_review(
        parsed_topic={"raw_topic": "x"},
        synthesize_output=_synthesize_with_baseline(2),
        evidence_review_stats=er_stats,
        candidate_pool_stats={"paper": 3, "dataset": 1, "repo": 1},
        chat_json_strict=_raise_unavailable,
    )
    assert out.review_verdict == "pass"
    assert out.can_continue_to_opening_report is True


def test_deterministic_summary_is_short_string():
    out = run_low_bar_review(
        parsed_topic={"raw_topic": "x"},
        synthesize_output=_synthesize_with_baseline(0),
        evidence_review_stats={"core": 0, "candidate": 0, "needs_manual": 0, "rejected": 0},
        candidate_pool_stats={"paper": 0},
        chat_json_strict=_raise_unavailable,
    )
    assert isinstance(out.summary, str)
    assert 0 < len(out.summary) < 400


def test_deterministic_more_than_one_weak_point_blocks_pass():
    """When baseline is empty, weak_points grows > 1, so verdict must be needs_revision."""
    out = run_low_bar_review(
        parsed_topic={"raw_topic": "x"},
        synthesize_output=_synthesize_with_baseline(0),
        evidence_review_stats={"core": 0, "candidate": 0, "needs_manual": 0, "rejected": 5},
        candidate_pool_stats={"paper": 0},
        chat_json_strict=_raise_unavailable,
    )
    assert out.review_verdict == "needs_revision"
    assert len(out.weak_points) > 1
