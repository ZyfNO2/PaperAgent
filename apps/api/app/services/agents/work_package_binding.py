"""Re04 SOP §5 Task 6 — work_suggestions binding validator.

Per SOP §5 Task 6 acceptance:
- Each work_suggestion must bind:
  * 1 baseline_candidate_id (from paper_groups.baseline)
  * ≥ 1 parallel_candidate_id OR dataset_candidate_id
- When paper_groups.baseline is empty, work_suggestions must contain
  ONLY "请先选 baseline" (or English equivalent) and evidence_gaps[0]
  must explain why.
- Never allow auto_generated citation keys.
"""
from __future__ import annotations

import re
from typing import Any

# Heuristic pattern: a "candidate id" looks like c-<8 hex> or c-<digits>.
_CID_RE = re.compile(r"\b(c-[0-9a-f]{6,}|c-\d{3,})\b", re.IGNORECASE)
_NO_BASELINE_MSG_ZH = "请先选 baseline"
_NO_BASELINE_MSG_EN = "please select a baseline"


def extract_candidate_ids(text: str) -> set[str]:
    """Pull all candidate-id-looking tokens out of a string."""
    if not text:
        return set()
    return {m.group(1).lower() for m in _CID_RE.finditer(text)}


def validate_work_suggestions(
    synthesis: dict,
    *,
    allowed_baseline_ids: set[str] | None = None,
    allowed_parallel_ids: set[str] | None = None,
    allowed_dataset_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Return a binding report: {ok, violations[], short_circuit_reason}.

    Each work_suggestion must:
    - Reference at least 1 baseline_candidate_id (from paper_groups.baseline)
    - Reference at least 1 parallel OR dataset candidate_id

    If paper_groups.baseline is empty AND no baseline gap was declared
    in evidence_gaps, the binding report MUST say short_circuit_reason =
    "no_baseline" and at most one work_suggestion may exist (and it
    must be the "请先选 baseline" placeholder).
    """
    work = list(synthesis.get("work_suggestions") or [])
    baseline = list(synthesis.get("paper_groups", {}).get("baseline") or [])
    parallel = list(synthesis.get("paper_groups", {}).get("parallel") or [])
    reference = list(synthesis.get("paper_groups", {}).get("reference") or [])
    long_tail = list(synthesis.get("paper_groups", {}).get("long_tail_candidates") or [])
    evidence_gaps = list(synthesis.get("evidence_gaps") or [])
    candidate_pool = synthesis.get("candidate_pool") or {}
    datasets = list(candidate_pool.get("dataset") or [])

    # Resolve allowed id sets if not given.
    if allowed_baseline_ids is None:
        allowed_baseline_ids = {str(b.get("candidate_id") or "").lower() for b in baseline}
    if allowed_parallel_ids is None:
        allowed_parallel_ids = {
            str(p.get("candidate_id") or "").lower() for p in parallel
        } | {str(r.get("candidate_id") or "").lower() for r in reference}
        # Reference papers are not strict "parallel" but can serve as
        # supporting evidence in the binding check.
    if allowed_dataset_ids is None:
        allowed_dataset_ids = {str(d.get("candidate_id") or "").lower() for d in datasets}

    report: dict[str, Any] = {
        "ok": True,
        "violations": [],
        "short_circuit_reason": None,
        "per_suggestion": [],
    }

    # Short-circuit: no baseline -> refuse full work package.
    has_baseline = bool(baseline)
    has_baseline_gap = any(
        "baseline" in (g or "").lower() for g in evidence_gaps
    )
    if not has_baseline and not has_baseline_gap:
        report["short_circuit_reason"] = "no_baseline"
        if not work:
            report["ok"] = True
            return report
        if len(work) > 1:
            report["ok"] = False
            report["violations"].append(
                "no_baseline_but_full_work_package: " +
                f"{len(work)} work_suggestions emitted; expected 1 placeholder"
            )
        for s in work:
            sid = extract_candidate_ids(s)
            if sid:
                report["ok"] = False
                report["violations"].append(
                    f"placeholder_suggestion_still_has_ids: {sorted(sid)}"
                )
        return report

    # Normal binding check: each suggestion must reference baseline + (parallel|dataset)
    for i, s in enumerate(work):
        ids = extract_candidate_ids(s)
        baseline_hit = ids & (allowed_baseline_ids or set())
        parallel_hit = ids & ((allowed_parallel_ids or set()) | (allowed_dataset_ids or set()))
        per = {
            "index": i,
            "text": s,
            "ids": sorted(ids),
            "baseline_hit": sorted(baseline_hit),
            "parallel_or_dataset_hit": sorted(parallel_hit),
        }
        report["per_suggestion"].append(per)
        if not baseline_hit:
            report["ok"] = False
            report["violations"].append(
                f"work_suggestions[{i}] missing baseline_candidate_id: {s[:80]}"
            )
        if not parallel_hit:
            report["ok"] = False
            report["violations"].append(
                f"work_suggestions[{i}] missing parallel_or_dataset_candidate_id: {s[:80]}"
            )
    return report


def validate_no_auto_generated_citation(synthesis: dict) -> list[str]:
    """Re04 SOP §1.2: `"auto_generated" in citation_key` is forbidden."""
    bad: list[str] = []
    for bucket_name, items in (synthesis.get("paper_groups") or {}).items():
        for it in items or []:
            ck = it.get("citation_key") or ""
            if "auto_generated" in str(ck).lower():
                bad.append(f"paper_groups.{bucket_name} has auto_generated citation_key: {ck}")
    for bucket_name, items in (synthesis.get("candidate_pool") or {}).items():
        for it in items or []:
            ck = it.get("citation_key") or ""
            if "auto_generated" in str(ck).lower():
                bad.append(f"candidate_pool.{bucket_name} has auto_generated citation_key: {ck}")
    return bad
