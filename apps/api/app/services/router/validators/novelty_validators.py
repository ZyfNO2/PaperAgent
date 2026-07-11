"""Re6.4 Novelty semantic validators for router contracts.

Validates NoveltyCandidate, DifferentiationMatrix, FalsifiableProposition,
and ReviewerPressurePoint at the semantic level.
"""
from __future__ import annotations

from typing import Any


def validate_novelty_candidate(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Semantic validation for novelty-candidate/v1 contract.

    Rules:
    - Problem, Method, Insight all required
    - Evidence IDs must be present (at least 3)
    - Insight must not be pure performance statement
    - First claims must be marked needs_literature_verification
    """
    problem = data.get("problem", "")
    method = data.get("method", "")
    insight = data.get("insight", "")
    evidence_ids = data.get("evidence_ids", [])

    if not problem or not method or not insight:
        return False, "Problem, Method, Insight are all required"

    if len(evidence_ids) < 3:
        cand_id = data.get("candidate_id", "unknown")
        return False, f"candidate {cand_id}: need >=3 evidence_ids, got {len(evidence_ids)}"

    # Insight-only check
    perf_keywords = ("提高了", "提升了", "outperforms", "achieves", "SOTA",
                     "state-of-the-art", "F1 score increased", "精度达到")
    if any(k in insight for k in perf_keywords) and len(insight) < 100:
        return False, (
            "insight appears to be a performance statement rather than a "
            "conditional finding. Elaborate on WHY the improvement occurs, "
            "not just the metric gain."
        )

    # First claim check
    first_markers = ("first", "首次", "最先", "从未", "开创性", "no prior")
    if any(m in (problem + method + insight) for m in first_markers):
        status = data.get("status", "")
        if status not in ("needs_literature_verification", "needs_evidence", "rejected"):
            return False, (
                "first claim detected but status is not "
                "needs_literature_verification"
            )

    return True, None


def validate_novelty_review(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Semantic validation for novelty-review/v1 contract.

    Rules:
    - Must have verdict (accepted/weak_reject/reject)
    - Must have at least one pressure point for each risk dimension
    - Each pressure point must have evidence_ids or 'unknown'
    """
    verdict = data.get("verdict", "")
    if verdict not in ("accepted", "weak_reject", "reject"):
        return False, f"verdict must be accepted/weak_reject/reject, got {verdict!r}"

    pressure_points = data.get("pressure_points", [])
    if not isinstance(pressure_points, list):
        return False, "pressure_points must be a list"

    # Check all 5 risk dimensions are covered
    risks_found = set()
    for pp in pressure_points:
        risk = pp.get("risk", "")
        if risk not in ("repetition", "motivation", "falsifiability", "differentiation", "story"):
            continue
        risks_found.add(risk)
        ev_ids = pp.get("evidence_ids", [])
        if not ev_ids:
            pp["evidence_ids"] = ["unknown"]

    required_risks = {"repetition", "motivation", "falsifiability", "differentiation", "story"}
    missing = required_risks - risks_found
    if missing:
        return False, f"review missing risk dimensions: {sorted(missing)}"

    return True, None


def validate_falsifiable_proposition(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate a single falsifiable proposition.

    Required: support_condition, refute_condition, required_test
    """
    support = data.get("support_condition", "")
    refute = data.get("refute_condition", "")
    required_test = data.get("required_test", "")

    missing = []
    if not support.strip():
        missing.append("support_condition")
    if not refute.strip():
        missing.append("refute_condition")
    if not required_test.strip():
        missing.append("required_test")

    if missing:
        return False, f"missing: {missing}"

    # Status check: if verified, must have evidence
    status = data.get("status", "planned_not_verified")
    evidence_ids = data.get("evidence_ids", [])
    if status == "verified" and not evidence_ids:
        return False, "status=verified but no evidence_ids"

    return True, None


def validate_falsifiability_batch(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate a batch of falsifiable propositions."""
    propositions = data.get("propositions", [])
    if not isinstance(propositions, list) or len(propositions) == 0:
        return False, "propositions must be a non-empty list"

    for i, prop in enumerate(propositions):
        ok, err = validate_falsifiable_proposition(prop)
        if not ok:
            pid = prop.get("proposition_id", f"index-{i}")
            return False, f"proposition {pid}: {err}"

    return True, None


def validate_differentiation_matrix(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate that all 5 differentiation dimensions are non-empty."""
    dims = ["problem_diff", "method_diff", "detail_diff", "evidence_diff", "insight_diff"]
    missing = [d for d in dims if not data.get(d, "").strip()]
    if missing:
        return False, f"differentiation matrix missing: {missing}"
    return True, None


def validate_claim_judge(data: dict[str, Any]) -> tuple[bool, str | None]:
    """Semantic validation for claim-judge/v1 contract.

    Rules:
    - overall_verdict must be one of ACCEPT / REVISE / REJECT
    - judgements must exist and be a list
    - each judgement must have verdict ∈ {ACCEPT, REVISE, REJECT}
    """
    overall_verdict = data.get("overall_verdict", "")
    allowed = {"ACCEPT", "REVISE", "REJECT"}
    if overall_verdict not in allowed:
        return False, f"overall_verdict must be one of {allowed}, got {overall_verdict!r}"

    judgements = data.get("judgements", [])
    if not isinstance(judgements, list):
        return False, "judgements must be a list"

    for i, j in enumerate(judgements):
        if not isinstance(j, dict):
            return False, f"judgements[{i}] must be a dict"
        verdict = j.get("verdict", "")
        if verdict not in allowed:
            return False, f"judgements[{i}].verdict must be one of {allowed}, got {verdict!r}"

    return True, None
