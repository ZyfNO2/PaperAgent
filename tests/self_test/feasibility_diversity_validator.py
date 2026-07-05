"""Self-test validator: feasibility diversity — checks batch feasibility differentiation.

Validates that across multiple cases, the feasibility assessor produces
≥2 different verdicts and score spread ≥20.
"""
from __future__ import annotations

from typing import Any


def validate_batch(states: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate feasibility diversity across multiple case states.

    Args:
        states: list of state dicts (each from a different case)

    Returns:
        dict with keys: pass (bool), n_cases, unique_verdicts, score_min,
        score_max, score_spread, details
    """
    verdicts = []
    scores = []

    for s in states:
        fe = s.get("feasibility_report") or {}
        verdict = fe.get("verdict", "")
        score = fe.get("score", None)
        if verdict:
            verdicts.append(verdict)
        if score is not None:
            try:
                scores.append(float(score))
            except (ValueError, TypeError):
                pass

    unique_verdicts = list(set(verdicts))
    n_unique = len(unique_verdicts)

    if scores:
        score_min = min(scores)
        score_max = max(scores)
        score_spread = round(score_max - score_min, 1)
    else:
        score_min = None
        score_max = None
        score_spread = 0

    passed = n_unique >= 2 and score_spread >= 20

    return {
        "pass": passed,
        "n_cases": len(states),
        "unique_verdicts": unique_verdicts,
        "n_unique_verdicts": n_unique,
        "score_min": score_min,
        "score_max": score_max,
        "score_spread": score_spread,
        "all_verdicts": verdicts,
        "details": (
            f"{n_unique} unique verdicts, score spread {score_spread}"
            if scores
            else f"{n_unique} unique verdicts, no scores"
        ),
    }
