"""Re5.X: Coverage Gate — role-based stopping logic.

Replaces the old "n_papers >= 5 + n_repos >= 1" heuristic with
configurable required/optional evidence roles + budget tracking.

The gate is purely code-based; LLM can only suggest stop, not enforce it.
"""
from __future__ import annotations

from typing import Any

from apps.api.app.services.agents.graph.schemas.search_models import CoverageGate


def _default_role_policy(domain: str = "") -> dict[str, dict[str, int]]:
    """Return required/optional role policy based on domain.

    repo and dataset are optional by default; upgraded to required only
    for domains where code reproducibility is expected (e.g. CV, NLP).
    """
    domain_lower = (domain or "").lower()
    is_cv = any(kw in domain_lower for kw in ("vision", "detection", "image", "yolo", "segmentation"))
    is_nlp = any(kw in domain_lower for kw in ("nlp", "language", "text", "bert", "transformer"))

    if is_cv or is_nlp:
        return {
            "required": {"core": 2, "baseline": 1},
            "optional": {"parallel": 1, "dataset": 1, "repo": 1},
        }
    # Medical/other: repo is truly optional
    return {
        "required": {"core": 2, "baseline": 1},
        "optional": {"parallel": 1, "dataset": 1, "repo": 0},
    }


def _count_roles(state: dict[str, Any]) -> dict[str, int]:
    """Count current evidence by role from state."""
    verified = state.get("verified_papers") or []
    baseline = state.get("baseline_candidates") or []
    parallel = state.get("parallel_candidates") or []
    datasets = state.get("dataset_candidates") or []
    repos = state.get("repo_candidates") or []

    # core = verified papers with accept verdict
    core = sum(1 for p in verified if (p.get("verification_verdict") or p.get("verdict")) == "accept")
    if core == 0 and verified:
        core = len(verified)  # fallback: all verified count as core

    return {
        "core": core,
        "baseline": len(baseline),
        "parallel": len(parallel),
        "dataset": len(datasets),
        "repo": len(repos),
    }


def check_coverage(
    state: dict[str, Any],
    budget_remaining: int = 0,
    last_two_card_gains: list[int] | None = None,
) -> CoverageGate:
    """Check if evidence coverage is sufficient to proceed downstream.

    Args:
        state: Current ResearchState
        budget_remaining: How many more search cards can be executed
        last_two_card_gains: Verified paper count gained from last 2 cards

    Returns:
        CoverageGate with decision: pass | reflect | stop_with_gap
    """
    domain = str(state.get("topic_atoms", {}).get("domain", ""))
    if isinstance(state.get("topic_atoms"), dict):
        domain_val = state.get("topic_atoms", {}).get("domain", "")
        if isinstance(domain_val, list) and domain_val:
            domain = str(domain_val[0])
        else:
            domain = str(domain_val)

    policy = _default_role_policy(domain)
    required = policy["required"]
    optional = policy["optional"]

    current = _count_roles(state)

    # Find gaps in required roles
    gaps: list[str] = []
    for role, needed in required.items():
        if current.get(role, 0) < needed:
            gaps.append(role)

    # Check if all required met + marginal gain is zero
    if not gaps:
        gains = last_two_card_gains or []
        if gains and all(g == 0 for g in gains[-2:]):
            return CoverageGate(
                required_roles=required,
                optional_roles=optional,
                current_coverage=current,
                gaps=[],
                budget_remaining=budget_remaining,
                decision="pass",
            )
        # Required met but we can still try for optional
        if budget_remaining > 0:
            optional_gaps = [
                r for r, needed in optional.items()
                if needed > 0 and current.get(r, 0) < needed
            ]
            if optional_gaps and any(g > 0 for g in (gains or [1])):
                return CoverageGate(
                    required_roles=required,
                    optional_roles=optional,
                    current_coverage=current,
                    gaps=optional_gaps,
                    budget_remaining=budget_remaining,
                    decision="reflect",
                )
        return CoverageGate(
            required_roles=required,
            optional_roles=optional,
            current_coverage=current,
            gaps=[],
            budget_remaining=budget_remaining,
            decision="pass",
        )

    # Required gap exists
    if budget_remaining > 0:
        return CoverageGate(
            required_roles=required,
            optional_roles=optional,
            current_coverage=current,
            gaps=gaps,
            budget_remaining=budget_remaining,
            decision="reflect",
        )

    # Budget exhausted with gaps
    return CoverageGate(
        required_roles=required,
        optional_roles=optional,
        current_coverage=current,
        gaps=gaps,
        budget_remaining=0,
        decision="stop_with_gap",
    )
