"""Re4.3: Binding validator — ensures logical consistency across evidence chain.

Checks:
  1. Innovation points reference real candidate IDs
  2. Work packages reference real baseline/parallel/dataset
  3. No orphan work packages (prerequisite_ids must resolve)
  4. Narrative references existing innovation points
  5. Stale marking: upstream evidence changed → derived items marked stale

Inspired by:
  - academic-research-skills claim_verification_protocol.md (claim→source binding)
  - Draftpaper stale_sync.py (artifact drift → stale marking)
"""
from __future__ import annotations

from typing import Any

from apps.api.app.services.agents.graph.schemas.evidence_schema import (
    BindingValidationResult,
    InnovationPoint,
    WorkPackage,
)


def _build_evidence_index(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build an index of all evidence by ID/title for quick lookup."""
    index: dict[str, dict[str, Any]] = {}
    for key in (
        "verified_papers", "baseline_candidates", "parallel_candidates",
        "dataset_candidates", "repo_candidates",
    ):
        for item in (state.get(key) or []):
            for id_key in ("paper_id", "doi", "arxiv_id", "full_name", "name", "title"):
                val = item.get(id_key)
                if val:
                    index[str(val).lower()] = item
    return index


def validate_innovations(
    innovations: list[dict[str, Any]],
    evidence_index: dict[str, dict[str, Any]],
) -> tuple[list[InnovationPoint], list[dict[str, Any]]]:
    """Validate that each innovation point references real evidence."""
    issues: list[dict[str, Any]] = []
    validated: list[InnovationPoint] = []

    for i, raw in enumerate(innovations):
        ip = InnovationPoint(**{k: v for k, v in raw.items() if k in InnovationPoint.model_fields})

        if not ip.candidate_ids:
            ref = (ip.evidence_ref or "").lower()
            if ref and ref in evidence_index:
                ip.candidate_ids = [ref]
            else:
                baseline = (ip.baseline_used or "").lower()
                if baseline and baseline in evidence_index:
                    ip.candidate_ids = [baseline]

        if not ip.has_evidence():
            ip.status = "needs_evidence"
            issues.append({
                "type": "innovation_no_evidence",
                "item_index": i,
                "description": ip.description[:100],
                "message": f"Innovation point #{i + 1} has no candidate_id binding",
            })

        for cid in ip.candidate_ids:
            if cid.lower() not in evidence_index:
                ip.status = "needs_evidence"
                issues.append({
                    "type": "innovation_dangling_ref",
                    "item_index": i,
                    "candidate_id": cid,
                    "message": f"Innovation point #{i + 1} references unknown candidate: {cid}",
                })

        validated.append(ip)

    return validated, issues


def validate_work_packages(
    packages: list[dict[str, Any]],
    evidence_index: dict[str, dict[str, Any]],
    package_ids: set[str] | None = None,
) -> tuple[list[WorkPackage], list[dict[str, Any]], list[str]]:
    """Validate work packages: evidence binding + prerequisite resolution."""
    issues: list[dict[str, Any]] = []
    validated: list[WorkPackage] = []
    orphan_ids: list[str] = []

    all_package_ids: set[str] = set()
    for raw in packages:
        wp = WorkPackage(**{k: v for k, v in raw.items() if k in WorkPackage.model_fields})
        all_package_ids.add(wp.package_id)

    for i, raw in enumerate(packages):
        wp = WorkPackage(**{k: v for k, v in raw.items() if k in WorkPackage.model_fields})

        for ref_key in ("baseline", "improved_module_source", "data_source"):
            ref_val = getattr(wp, ref_key, None)
            if ref_val and ref_val.lower() not in evidence_index:
                issues.append({
                    "type": "work_package_dangling_ref",
                    "item_index": i,
                    "field": ref_key,
                    "value": ref_val,
                    "message": f"Work package #{i + 1} {ref_key} not in evidence: {ref_val}",
                })

        for prereq_id in wp.prerequisite_ids:
            if prereq_id not in all_package_ids:
                orphan_ids.append(prereq_id)
                issues.append({
                    "type": "work_package_orphan_prerequisite",
                    "item_index": i,
                    "prerequisite_id": prereq_id,
                    "message": f"Work package #{i + 1} prerequisite not found: {prereq_id}",
                })

        validated.append(wp)

    return validated, issues, orphan_ids


def validate_narrative(
    narrative: dict[str, Any],
    innovations: list[InnovationPoint],
) -> list[dict[str, Any]]:
    """Validate that narrative references existing innovation points."""
    issues: list[dict[str, Any]] = []
    three_problems = narrative.get("three_problems") or []

    for i, problem in enumerate(three_problems):
        from_paper = (problem.get("from_paper") or "").lower()
        if from_paper:
            found = False
            for ip in innovations:
                if from_paper in [c.lower() for c in ip.candidate_ids]:
                    found = True
                    break
            if not found:
                issues.append({
                    "type": "narrative_dangling_ref",
                    "problem_index": i,
                    "from_paper": from_paper,
                    "message": f"Narrative problem #{i + 1} references unknown paper: {from_paper}",
                })

    return issues


def mark_stale_derived_items(
    state: dict[str, Any],
    changed_evidence_ids: set[str],
) -> list[str]:
    """Mark derived items as stale when upstream evidence changes."""
    stale_items: list[str] = []

    innovations = state.get("innovation_points") or []
    for i, ip in enumerate(innovations):
        candidate_ids = ip.get("candidate_ids") or []
        if any(cid.lower() in changed_evidence_ids for cid in candidate_ids):
            ip["status"] = "stale"
            stale_items.append(f"innovation_{i}")

    packages = state.get("work_packages") or []
    for i, wp in enumerate(packages):
        bound_ids = wp.get("bound_candidate_ids") or []
        if any(cid.lower() in changed_evidence_ids for cid in bound_ids):
            wp["status"] = "stale"
            stale_items.append(f"work_package_{i}")

    return stale_items


def run_full_validation(state: dict[str, Any]) -> BindingValidationResult:
    """Run all binding validations and return aggregated result."""
    evidence_index = _build_evidence_index(state)

    innovations, inn_issues = validate_innovations(
        state.get("innovation_points") or [], evidence_index,
    )
    packages, wp_issues, orphan_ids = validate_work_packages(
        state.get("work_packages") or [], evidence_index,
    )
    nar_issues = validate_narrative(
        state.get("research_narrative") or state.get("research_narrative") or {},
        innovations,
    )

    all_issues = inn_issues + wp_issues + nar_issues
    needs_evidence = [
        f"innovation_{i['item_index']}"
        for i in inn_issues
        if i["type"] == "innovation_no_evidence"
    ]

    return BindingValidationResult(
        valid=len(all_issues) == 0,
        issues=all_issues,
        orphan_packages=orphan_ids,
        needs_evidence_items=needs_evidence,
        stale_items=[],
    )
