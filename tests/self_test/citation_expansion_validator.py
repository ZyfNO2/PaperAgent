"""Self-test validator: citation expansion — verifies expansion results."""
from __future__ import annotations

from typing import Any


def validate_citation_expansion(state: dict[str, Any]) -> dict[str, Any]:
    """Validate citation expansion: traceability, identifiers, concurrency."""
    report: dict[str, Any] = {
        "expansion_exists": False,
        "n_expanded": 0,
        "n_surveys": 0,
        "n_repos": 0,
        "source_traceable": True,
        "concurrent_execution": True,
        "s2_api_failures": 0,
        "failures": [],
    }

    expanded = state.get("expanded_papers", [])
    surveys = state.get("surveys_found", [])
    repos = state.get("repos_found", [])
    traces = state.get("trace_events", [])

    report["n_expanded"] = len(expanded)
    report["n_surveys"] = len(surveys)
    report["n_repos"] = len(repos)
    report["expansion_exists"] = len(expanded) > 0

    for i, p in enumerate(expanded):
        source_seed = p.get("expanded_from_seed", "")
        if not source_seed:
            report["source_traceable"] = False
            report["failures"].append({
                "check": "source_traceable",
                "issue": f"expanded paper #{i} has no expanded_from_seed"
            })
        has_id = bool(p.get("paper_id") or p.get("doi") or p.get("arxiv_id"))
        if not has_id:
            report["failures"].append({
                "check": "has_identifier",
                "issue": f"expanded paper #{i} '{p.get('title','')[:50]}' has no paperId/DOI/arXiv"
            })

    for t in traces:
        if t.get("node") == "citation_expander":
            elapsed = t.get("elapsed_s", 0)
            n_seeds = len(state.get("seed_papers") or [])
            if n_seeds > 1 and elapsed > n_seeds * 10:
                report["concurrent_execution"] = False
                report["failures"].append({
                    "check": "concurrent_execution",
                    "issue": f"citation_expander elapsed={elapsed}s for {n_seeds} seeds"
                })
            errors = t.get("errors", [])
            report["s2_api_failures"] = len(errors)

    return report
