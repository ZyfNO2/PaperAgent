"""Re04/06/07/08 — Resource Retrieval Eval Harness (Re08 latest).

Computes per-case ``resource_status`` and aggregate metrics from a
Re04/07 result dict. Used both offline (mocked client) and online
(real LLM).

Re06 changes (SOP ``Plan/PaperAgent_Re06_去硬编码噪声与证据一致性审计_SOP.md``):
  * Removed the runtime ``STRONG_NOISE_TOKENS`` keyword blacklist and
    ``_is_strong_noise()`` keyword gate.
  * Wired in ``evidence_consistency.audit_synthesis`` and
    ``evidence_roles.classify_*_role``.

Re07 changes (SOP ``Plan/PaperAgent_Re06_Review_评分规则与Prompt流程重写.md``
§2 + §3):
  * **Scoring semantics are now "resource-availability for thesis
    selection"** — not "citation-grade evidence audit".
  * ``metadata_mismatch`` is candidate-level first (quarantine) before
    it can ever trigger a case-level fail.
  * ``topic_dataset_n == 0`` and ``core_direct_n == 0`` no longer
    auto-weak — they are *notes* the user can act on.
  * When ``topic_atoms`` is missing (Re05-era raw dump), the case is
    marked ``axis_status = not_evaluable`` and CANNOT be auto-
    downgraded for axis reasons alone.
  * ``pass`` requires only ``paper ≥ 8 ∧ effective_baseline ≥ 1 ∧
    (effective_parallel ≥ 2 ∨ effective_core ≥ 1) ∧ dataset+repo ≥ 1 ∧
    no quarantined baseline``.
  * ``fail`` is reserved for true hard-blocks: no paper AND no
    dataset/repo/baseline; no effective evidence at all; OR every
    surviving candidate is critical_consistency_error.
  * Soft internal ``score`` (0-100) is added for dashboards but never
    surfaced as a hero UI number.

Re08 changes (SOP ``Plan/PaperAgent_Re08_候选核验与弱项补证增强_SOP.md``):
  * Per-candidate ``VerificationResult`` is now consumed BEFORE the
    quarantine block — candidates tagged ``metadata_repaired`` (from
    ``metadata_repair.repair_bucket``) are NOT quarantined.
  * ``metadata_mismatch`` quarantine is now a SECONDARY step after the
    verifier has had a chance to repair; the eval module never
    quarantines a candidate that the rule-layer verifier already
    classified as ``metadata_mismatch`` AND the candidate's
    ``raw_candidate`` field is set (the repair left a paper trail).
  * New fields: ``verification_verified_n``,
    ``verification_repaired_n``, ``verification_quarantined_n``,
    ``verification_not_found_n``.  Per Re08 SOP §6.1 these MUST be
    populated and non-empty.
  * New ``verification_records`` field carries the per-bucket
    VerificationResult list (without raw_candidate blobs) so the CSV
    auditor can join.
  * Fail hard-block now requires evidence_gap_reasons NOT to be ONLY
    ``metadata_mismatch`` — repaired candidates cannot block a case
    from passing.

Status rules (Re07 SOP §2.1, Re08 unchanged):
  pass    — ready for next-stage selection
  weak    — usable, but user must explicitly handle the gap(s)
  fail    — cannot proceed; baseline missing + no useful parallel/core
  blocked — needs_clarification OR LLM parse fail
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---- helpers ----------------------------------------------------------------

def _count_paper_like(pool: dict | list) -> int:
    """Count items with evidence_type == 'paper' in a candidate pool."""
    if isinstance(pool, list):
        return sum(1 for c in pool if (c.get("evidence_type") or "paper") == "paper")
    if isinstance(pool, dict):
        return len(pool.get("paper") or []) + sum(
            len(v) for k, v in pool.items() if k not in ("paper", "dataset", "repo")
        )
    return 0


def _count_type(pool: dict | list, t: str) -> int:
    if isinstance(pool, list):
        return sum(1 for c in pool if c.get("evidence_type") == t)
    if isinstance(pool, dict):
        return len(pool.get(t) or [])
    return 0


def _extract_evidence_review(er: Any) -> list[dict]:
    """ER may be a list / dict {tier: [cands]} / EvidenceReview object / None."""
    if er is None:
        return []
    if isinstance(er, list):
        out: list[dict] = []
        for r in er:
            if isinstance(r, dict):
                out.append(r)
            elif hasattr(r, "to_dict"):
                out.append(r.to_dict())
            elif hasattr(r, "__dict__"):
                out.append({k: val for k, val in r.__dict__.items()})
        return out
    if isinstance(er, dict):
        out2: list[dict] = []
        for v in er.values():
            if isinstance(v, list):
                out2.extend(x.to_dict() if hasattr(x, "to_dict") else
                            (x if isinstance(x, dict) else
                             {k: val for k, val in x.__dict__.items()})
                            for x in v)
            elif isinstance(v, dict):
                out2.append(v)
            elif hasattr(v, "to_dict"):
                out2.append(v.to_dict())
        return out2
    if hasattr(er, "reviews"):
        revs = er.reviews
        if isinstance(revs, list):
            return _extract_evidence_review(revs)
    if hasattr(er, "as_list"):
        revs = er.as_list()
        if isinstance(revs, list):
            return _extract_evidence_review(revs)
    if hasattr(er, "to_dict"):
        return [er.to_dict()]
    return []


def _build_topic_atoms(
    synthesis: dict | None,
    result: dict | None = None,
) -> dict[str, list[str]]:
    """Best-effort extract of topic atoms from a Re04/07 result.

    Per Re07 SOP §3.2, lookup order (first hit wins):

      1. ``result["parsed_topic"]["topic_atoms"]``            (canonical when
         LLM-online run wrote topic_atoms into synthesis but the round trip
         stripped it).
      2. ``result["parsed_topic"]``  itself                   (fallback for
         older raw dumps).
      3. ``synthesis["topic_atoms"]``                          (Re07 LLM
         normalizer writes it here).
      4. ``synthesis["parsed_topic"]["topic_atoms"]``          (mirror of #3).
      5. ``synthesis["query_matrix"]["parsed_topic"]["topic_atoms"]``
         (Re06-era placement).
      6. Backward-compat fallback — derive from the legacy flat
         ``method_terms / task_terms / object_terms`` fields.
      7. Returns ``{}`` — callers must treat empty as
         ``axis_status = not_evaluable`` (NOT as ``fail``).

    Topic atoms in Re07 are dicts shaped
    ``{"zh": "...", "en": "...", "aliases": [...]}``.  This function
    flattens each axis to a ``list[str]`` of English canonical phrases
    (en + aliases), which is what ``_axis_match`` consumes.  Chinese
    phrases are appended after English so axis matching against
    Chinese-titled papers still has a chance.
    """
    candidates: list[dict] = []

    if isinstance(result, dict):
        parsed = result.get("parsed_topic")
        if isinstance(parsed, dict):
            ta = parsed.get("topic_atoms")
            if isinstance(ta, dict):
                candidates.append(ta)
            for axis in ("task", "object", "method", "scenario"):
                if isinstance(parsed.get(axis), list):
                    candidates.append({
                        axis: [{"en": x} for x in parsed.get(axis, []) if x]
                    })

    if isinstance(synthesis, dict):
        ta = synthesis.get("topic_atoms")
        if isinstance(ta, dict):
            candidates.append(ta)
        pt = synthesis.get("parsed_topic")
        if isinstance(pt, dict):
            inner = pt.get("topic_atoms")
            if isinstance(inner, dict):
                candidates.append(inner)
        qm = synthesis.get("query_matrix")
        if isinstance(qm, dict):
            inner = (qm.get("parsed_topic") or {}).get("topic_atoms")
            if isinstance(inner, dict):
                candidates.append(inner)

    if not candidates:
        legacy_src = None
        if isinstance(result, dict):
            legacy_src = result.get("parsed_topic")
        if not isinstance(legacy_src, dict):
            legacy_src = synthesis if isinstance(synthesis, dict) else {}
        legacy: dict[str, list] = {}
        for axis, src_field in (
            ("task", "task_terms"),
            ("object", "object_terms"),
            ("method", "method_terms"),
        ):
            flat = legacy_src.get(src_field) or []
            if isinstance(flat, list):
                legacy[axis] = [{"en": x} for x in flat if isinstance(x, str) and x]
        if legacy:
            candidates.append(legacy)

    if not candidates:
        return {}

    merged: dict[str, list[str]] = {a: [] for a in ("task", "object", "method", "scenario")}
    for ta in candidates:
        for axis in merged:
            atoms = ta.get(axis)
            if not isinstance(atoms, list):
                continue
            for a in atoms:
                if isinstance(a, str) and a:
                    merged[axis].append(a)
                elif isinstance(a, dict):
                    en = a.get("en") or a.get("zh") or ""
                    if en:
                        merged[axis].append(en)
                    for alias in a.get("aliases") or []:
                        if isinstance(alias, str) and alias:
                            merged[axis].append(alias)

    for axis, vals in merged.items():
        seen: set[str] = set()
        out: list[str] = []
        for v in vals:
            lv = v.lower()
            if lv in seen:
                continue
            seen.add(lv)
            out.append(v)
        merged[axis] = out

    return merged


# ---- main entry -------------------------------------------------------------

def compute_resource_status(result: dict) -> dict[str, Any]:
    """Compute per-case resource_status from a Re04/07 result.

    Returns the Re07 SOP §2 schema (status, paper_n, baseline_n,
    parallel_n, dataset_n, repo_n, topic_dataset_n, ...,
    quarantined_*, effective_*, axis_status, notes, score, ...).
    """
    if result.get("blocked_reason") == "needs_clarification":
        return {
            "status": "blocked",
            "reason": "needs_clarification",
            "notes": [],
            "score": 0,
            "paper_n": 0, "dataset_n": 0, "repo_n": 0,
            "baseline_n": 0, "parallel_n": 0,
            "topic_dataset_n": 0, "proxy_dataset_n": 0,
            "pretrain_dataset_n": 0, "generic_dataset_n": 0,
            "core_direct_n": 0, "baseline_direct_n": 0,
            "baseline_proxy_n": 0, "parallel_direct_n": 0,
            "parallel_proxy_n": 0,
            "core_n": 0, "effective_core_n": 0,
            "quarantined_baseline_n": 0, "quarantined_parallel_n": 0,
            "quarantined_core_n": 0,
            "effective_baseline_n": 0, "effective_parallel_n": 0,
            "critical_consistency_error_n": 0,
            "metadata_mismatch_n": 0,
            "off_topic_core_n": 0,
            "axis_status": "not_evaluable",
            "axis_missing_reasons": [],
            "evidence_gap_reasons": ["empty raw_topic or no parsed atoms"],
        }

    # ---- Pool counts ----
    pool = result.get("candidate_pool")
    if hasattr(pool, "by_evidence_type"):
        paper_n = len(pool.by_evidence_type("paper"))
        dataset_n = len(pool.by_evidence_type("dataset"))
        repo_n = len(pool.by_evidence_type("repo"))
    elif hasattr(pool, "as_list"):
        items = pool.as_list()
        paper_n = _count_paper_like(items)
        dataset_n = _count_type(items, "dataset")
        repo_n = _count_type(items, "repo")
    elif isinstance(pool, list):
        paper_n = _count_paper_like(pool)
        dataset_n = _count_type(pool, "dataset")
        repo_n = _count_type(pool, "repo")
    elif isinstance(pool, dict):
        paper_n = _count_paper_like(pool)
        dataset_n = _count_type(pool, "dataset")
        repo_n = _count_type(pool, "repo")
    else:
        paper_n = dataset_n = repo_n = 0

    synthesis = result.get("synthesis") or {}
    paper_groups = (synthesis.get("paper_groups") or {}) if isinstance(synthesis, dict) else {}
    baseline_entries = paper_groups.get("baseline") or []
    baseline_n = len(baseline_entries)
    baseline_degraded = any(
        isinstance(e, dict) and "degraded_role" in e for e in baseline_entries
    )
    parallel_n = len(paper_groups.get("parallel") or [])

    # ---- Evidence consistency audit ----
    from ..evidence_consistency import audit_synthesis
    from ..evidence_roles import (
        classify_baseline_role,
        classify_dataset_role,
        classify_parallel_role,
    )

    er_list = _extract_evidence_review(result.get("evidence_review"))
    topic_atoms = _build_topic_atoms(synthesis, result)

    candidate_meta_index: dict[str, dict] = {}
    top_pool = result.get("candidate_pool")
    if isinstance(top_pool, list):
        for it in top_pool:
            if not isinstance(it, dict):
                continue
            cid = it.get("candidate_id") or it.get("id")
            if cid:
                candidate_meta_index[cid] = it

    audit = audit_synthesis(
        synthesis,
        topic_atoms=topic_atoms,
        er_list=er_list,
        candidate_meta_index=candidate_meta_index,
    )
    critical_n = audit["critical_consistency_error_n"]
    metadata_mismatch_n = audit["metadata_mismatch_n"]
    off_topic_core_n = audit["off_topic_core_n"]

    # ---- Direct / proxy axis counts ----
    core_bucket = audit["buckets"]["core"]
    baseline_bucket = audit["buckets"]["baseline"]
    parallel_bucket = audit["buckets"]["parallel"]
    dataset_bucket = audit["buckets"]["dataset"]
    audit["buckets"]["repo"]
    core_n = core_bucket["n_total"]

    core_direct_n = core_bucket["n_aligned"]
    baseline_direct_n = sum(
        1 for m in baseline_bucket["members"]
        if classify_baseline_role(m, topic_atoms=topic_atoms)["role"] == "direct"
    )
    baseline_proxy_n = baseline_n - baseline_direct_n
    parallel_direct_n = sum(
        1 for m in parallel_bucket["members"]
        if classify_parallel_role(m, topic_atoms=topic_atoms)["role"] == "direct"
    )
    parallel_proxy_n = parallel_n - parallel_direct_n

    # ---- Dataset role tiers ----
    topic_dataset_n = proxy_dataset_n = pretrain_dataset_n = generic_dataset_n = 0
    for m in dataset_bucket["members"]:
        role_tag = classify_dataset_role(m, topic_atoms=topic_atoms)
        if role_tag.role == "topic":
            topic_dataset_n += 1
        elif role_tag.role == "proxy":
            proxy_dataset_n += 1
        elif role_tag.role == "pretrain":
            pretrain_dataset_n += 1
        elif role_tag.role == "generic":
            generic_dataset_n += 1
    pool_dataset_n = dataset_n
    surfaced_dataset_n = (
        topic_dataset_n + proxy_dataset_n + pretrain_dataset_n + generic_dataset_n
    )
    if surfaced_dataset_n < pool_dataset_n:
        pretrain_dataset_n += pool_dataset_n - surfaced_dataset_n

    # ---- Axis gap reasons (only meaningful when axis_status == evaluable) ----
    axis_missing_reasons: list[str] = []
    if topic_atoms:
        axis_counters = Counter()
        for bucket_name in ("core", "baseline", "parallel"):
            for m in audit["buckets"][bucket_name]["members"]:
                for ax_name, ax_val in (m.get("axis_coverage") or {}).items():
                    if ax_val in ("direct", "proxy"):
                        axis_counters[ax_name] += 1
        task_atoms = [a.lower() for a in topic_atoms.get("task", []) if a]
        if any(a in {"attack", "defense", "adversarial", "攻击", "防御"}
               for a in task_atoms):
            if axis_counters.get("task", 0) == 0:
                axis_missing_reasons.append("attack_defense_axis_missing")
        if axis_counters.get("object", 0) == 0:
            axis_missing_reasons.append("object_axis_missing")
        if axis_counters.get("scenario", 0) == 0:
            axis_missing_reasons.append("scenario_axis_missing")

    # ---- Quarantine bad candidates BEFORE the decision matrix (Re07 §3.5) ----
    # Re08 §4.2 relaxation: candidates that already went through
    # MetadataRepairLoop and ended up tagged ``metadata_repaired`` (i.e.
    # carry a ``raw_candidate`` field) are NOT quarantined — the repair
    # left a paper trail and the new metadata is medium-confidence.
    quarantine_idx: set[str] = set()
    repaired_idx: set[str] = set()
    verified_idx: set[str] = set()
    not_found_idx: set[str] = set()
    verification_records: list[dict] = []
    for bucket_name in ("core", "baseline", "parallel"):
        for m in audit["buckets"][bucket_name]["members"]:
            cid = m.get("candidate_id")
            if not cid:
                continue
            # Tag from the evidence_consistency audit (Re07 layer).
            tag = m.get("consistency_status")
            # Re08 layer: if the candidate was repaired, it carries a
            # raw_candidate blob — do not quarantine.
            cand_meta = candidate_meta_index.get(cid) or {}
            if cand_meta.get("raw_candidate"):
                repaired_idx.add(cid)
                verification_records.append({
                    "candidate_id": cid,
                    "bucket": bucket_name,
                    "verification_status": "metadata_repaired",
                    "recommended_action": "keep_as_proxy",
                    "reason": "repaired via metadata_repair.repair_bucket",
                })
                continue
            if tag == "metadata_mismatch":
                quarantine_idx.add(cid)
                verification_records.append({
                    "candidate_id": cid,
                    "bucket": bucket_name,
                    "verification_status": "metadata_mismatch",
                    "recommended_action": "quarantine",
                    "reason": (m.get("decision_reason") or "")[:120],
                })
            elif tag in {"aligned", "proxy"}:
                verified_idx.add(cid)
                verification_records.append({
                    "candidate_id": cid,
                    "bucket": bucket_name,
                    "verification_status": "verified",
                    "recommended_action": "keep",
                    "reason": (m.get("decision_reason") or "")[:120],
                })
            else:
                # off_topic / insufficient_metadata
                if tag == "off_topic":
                    not_found_idx.add(cid)
                    verification_records.append({
                        "candidate_id": cid,
                        "bucket": bucket_name,
                        "verification_status": "not_found",
                        "recommended_action": "quarantine",
                        "reason": "off_topic per evidence_consistency audit",
                    })
                else:
                    # insufficient_metadata — keep as weak_metadata
                    verification_records.append({
                        "candidate_id": cid,
                        "bucket": bucket_name,
                        "verification_status": "weak_metadata",
                        "recommended_action": "keep_as_proxy",
                        "reason": (m.get("decision_reason") or "")[:120],
                    })
    quarantined_baseline_n = sum(
        1 for e in baseline_entries
        if isinstance(e, dict) and (
            e.get("candidate_id") in quarantine_idx
            or e.get("candidate") in quarantine_idx
        )
    )
    quarantined_parallel_n = sum(
        1 for e in (paper_groups.get("parallel") or [])
        if isinstance(e, dict) and (
            e.get("candidate_id") in quarantine_idx
            or e.get("candidate") in quarantine_idx
        )
    )
    quarantined_core_n = sum(
        1 for m in core_bucket["members"]
        if m.get("candidate_id") in quarantine_idx
    )
    effective_baseline_n = baseline_n - quarantined_baseline_n
    effective_parallel_n = parallel_n - quarantined_parallel_n
    effective_core_n = core_n - quarantined_core_n

    # ---- axis_status (Re07 §3.2) ----
    axis_status = "evaluable" if topic_atoms else "not_evaluable"

    # ---- Evidence gap reasons (Re07 relaxed) ----
    evidence_gap_reasons: list[str] = []
    if paper_n < 4:
        evidence_gap_reasons.append(f"paper_n={paper_n} < 4")
    if effective_baseline_n < 1:
        evidence_gap_reasons.append(
            f"effective_baseline_n={effective_baseline_n} < 1"
        )
    if dataset_n + repo_n < 1:
        evidence_gap_reasons.append(f"dataset+repo={dataset_n + repo_n} < 1")
    if baseline_degraded:
        evidence_gap_reasons.append("baseline_is_self_cannot_find_degradation")
    if quarantined_baseline_n + quarantined_parallel_n + quarantined_core_n > 0:
        evidence_gap_reasons.append(
            f"quarantined_candidates="
            f"{quarantined_baseline_n + quarantined_parallel_n + quarantined_core_n}"
        )
    if topic_dataset_n == 0 and dataset_n > 0:
        evidence_gap_reasons.append("datasets_present_but_no_topic_dataset")
    elif dataset_n == 0:
        evidence_gap_reasons.append("no_dataset_or_data_gap_note")
    if effective_core_n == 0 and core_n:
        evidence_gap_reasons.append(
            f"core_n={core_n}_but_no_effective_core"
        )

    # ---- Hard-block conditions (Re07 §2.2) ----
    hard_block_reasons: list[str] = []
    if paper_n < 4 and dataset_n + repo_n + baseline_n < 1:
        hard_block_reasons.append("no_paper_no_dataset_no_repo_no_baseline")
    if (effective_baseline_n < 1 and effective_parallel_n < 1
            and effective_core_n < 1):
        hard_block_reasons.append("no_effective_evidence_at_all")
    if critical_n > 0 and (
        quarantined_baseline_n + quarantined_parallel_n + quarantined_core_n
    ) == critical_n:
        hard_block_reasons.append("all_evidence_critical_consistency_error")

    # ---- Decision matrix (Re07 SOP §2.1-2.5) ----
    if hard_block_reasons:
        status = "fail"
        evidence_gap_reasons.extend(hard_block_reasons)
    else:
        # Re07 §2.3 — relaxed pass.
        parallel_or_core_ok = (
            effective_parallel_n >= 2 or effective_core_n >= 1
        )
        dataset_ok = dataset_n + repo_n >= 1
        # When axis audit is evaluable AND a critical axis is missing
        # (e.g. attack_defense_axis_missing for adversarial-perception
        # topics, object_axis_missing when topic atoms name an object
        # that no candidate hits), the case MUST NOT be pass — the
        # gap is too important to ignore.  When axis_status is
        # not_evaluable (topic_atoms missing entirely), the case is
        # graded on raw counts alone.
        axis_gap_blocking = (
            axis_status == "evaluable"
            and any(r in {"attack_defense_axis_missing", "object_axis_missing"}
                    for r in axis_missing_reasons)
        )
        # Re07 SOP §5.3 — "core=0 且只有 generic/proxy 证据的 case 不得
        # 标 pass".  When topic_atoms are evaluable AND no candidate
        # earned a core-aligned slot, the case cannot pass on parallel
        # alone — at most weak.  When topic_atoms are not_evaluable we
        # have no axis signal so we relax back to the parallel-only path.
        core_zero_blocks_pass = (
            axis_status == "evaluable" and effective_core_n == 0
        )
        if (
            paper_n >= 8
            and effective_baseline_n >= 1
            and parallel_or_core_ok
            and dataset_ok
            and quarantined_baseline_n == 0
            and not axis_gap_blocking
            and not core_zero_blocks_pass
        ):
            status = "pass"
        else:
            status = "weak"

    # Soft internal score (Re07 §2.5) — dashboards only, never UI hero.
    score = 0
    if paper_n >= 8:
        score += 10
    elif paper_n >= 4:
        score += 6
    if effective_baseline_n >= 1:
        score += 8
    if effective_parallel_n >= 2:
        score += 4
    if dataset_n + repo_n >= 1:
        score += 3
    if effective_core_n >= 1:
        score += 12
    if core_n >= 3:
        score += 8
    if quarantined_baseline_n + quarantined_parallel_n == 0 and critical_n == 0:
        score += 10
    if effective_baseline_n >= 1:
        score += 10
    if topic_dataset_n >= 1 or proxy_dataset_n >= 1 or dataset_n == 0:
        score += 8
    if synthesis.get("work_suggestions"):
        score += 7
    if repo_n >= 1:
        score += 5
    score += 15  # report consistency full marks

    if axis_status == "evaluable" and axis_missing_reasons:
        evidence_gap_reasons.extend(axis_missing_reasons)

    notes: list[str] = []
    if baseline_degraded:
        notes.append("baseline_scaffold_not_domain_specific")
    if dataset_n == 0:
        notes.append("data_source_gap_needs_confirmation")
    if axis_status == "not_evaluable":
        notes.append("axis_not_evaluable_topic_atoms_missing")

    return {
        "status": status,
        "reason": ("; ".join(evidence_gap_reasons) if evidence_gap_reasons else "all_metrics_met"),
        "notes": notes,
        "score": score,
        # raw counts
        "paper_n": paper_n,
        "dataset_n": dataset_n,
        "repo_n": repo_n,
        "baseline_n": baseline_n,
        "parallel_n": parallel_n,
        # quarantine + effective counts (Re07 §3.5)
        "quarantined_baseline_n": quarantined_baseline_n,
        "quarantined_parallel_n": quarantined_parallel_n,
        "quarantined_core_n": quarantined_core_n,
        "effective_baseline_n": effective_baseline_n,
        "effective_parallel_n": effective_parallel_n,
        "effective_core_n": effective_core_n,
        "core_n": core_n,
        # Re08 §6.1 verification counts (CSV-grade, MUST be populated)
        "verification_verified_n": len(verified_idx),
        "verification_repaired_n": len(repaired_idx),
        "verification_quarantined_n": len(quarantine_idx),
        "verification_not_found_n": len(not_found_idx),
        "verification_records": verification_records,
        # axis_status (Re07 §3.2)
        "axis_status": axis_status,
        # dataset role tiers
        "topic_dataset_n": topic_dataset_n,
        "proxy_dataset_n": proxy_dataset_n,
        "pretrain_dataset_n": pretrain_dataset_n,
        "generic_dataset_n": generic_dataset_n,
        # direct / proxy counts
        "core_direct_n": core_direct_n,
        "baseline_direct_n": baseline_direct_n,
        "baseline_proxy_n": baseline_proxy_n,
        "parallel_direct_n": parallel_direct_n,
        "parallel_proxy_n": parallel_proxy_n,
        # consistency counters
        "critical_consistency_error_n": critical_n,
        "metadata_mismatch_n": metadata_mismatch_n,
        "off_topic_core_n": off_topic_core_n,
        "axis_missing_reasons": axis_missing_reasons,
        "evidence_gap_reasons": evidence_gap_reasons,
        # Re04-fix degraded baseline marker
        "baseline_degraded": baseline_degraded,
        # Per-bucket audit
        "bucket_audit": audit["buckets"],
    }


def aggregate_metrics(per_case: list[dict]) -> dict[str, Any]:
    """Aggregate per-case status into SOP §4 metrics."""
    statuses = Counter(c.get("status") for c in per_case)
    total = sum(statuses.values()) or 1
    return {
        "total": sum(statuses.values()),
        "by_status": dict(statuses),
        "pass_rate": round((statuses.get("pass", 0) / total), 4),
        "weak_or_pass_rate": round(
            ((statuses.get("pass", 0) + statuses.get("weak", 0)) / total), 4,
        ),
        "fail_count": statuses.get("fail", 0),
        "blocked_count": statuses.get("blocked", 0),
        "critical_consistency_error_cases": sum(
            1 for c in per_case
            if (c.get("critical_consistency_error_n") or 0) > 0
        ),
        "metadata_mismatch_cases": sum(
            1 for c in per_case if (c.get("metadata_mismatch_n") or 0) > 0
        ),
        "off_topic_core_cases": sum(
            1 for c in per_case if (c.get("off_topic_core_n") or 0) > 0
        ),
        "core_zero_pass_cases": sum(
            1 for c in per_case
            if (c.get("core_direct_n") or 0) == 0 and c.get("status") == "pass"
        ),
        "quarantined_total": sum(
            1 for c in per_case
            if (c.get("quarantined_baseline_n") or 0)
            + (c.get("quarantined_parallel_n") or 0)
            + (c.get("quarantined_core_n") or 0) > 0
        ),
        "axis_not_evaluable_cases": sum(
            1 for c in per_case if c.get("axis_status") == "not_evaluable"
        ),
    }


def write_markdown_report(
    per_case: list[dict], out_path: str, *, source_url: str | None = None,
) -> None:
    """Write a human-readable per-case markdown report (SOP §7 #4)."""
    agg = aggregate_metrics(per_case)
    lines: list[str] = []
    lines.append("# Re07 Resource Retrieval Eval Report")
    lines.append("")
    if source_url:
        lines.append(f"Source JSONL: `{source_url}`")
        lines.append("")
    lines.append("## 整体统计 (Aggregate)")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---:|")
    lines.append(f"| 总题数 | {agg['total']} |")
    lines.append(f"| pass | {agg['by_status'].get('pass', 0)} |")
    lines.append(f"| weak | {agg['by_status'].get('weak', 0)} |")
    lines.append(f"| fail | {agg['by_status'].get('fail', 0)} |")
    lines.append(f"| blocked | {agg['by_status'].get('blocked', 0)} |")
    lines.append(f"| pass_rate | {agg['pass_rate']:.1%} |")
    lines.append(
        f"| pass+weak_rate (Re07 合格线 ≥ 90%) | "
        f"{agg['weak_or_pass_rate']:.1%} |"
    )
    lines.append(
        f"| quarantined_total (Re07 §3.5) | "
        f"{agg['quarantined_total']} |"
    )
    lines.append(
        f"| axis_not_evaluable cases (Re07 §3.2) | "
        f"{agg['axis_not_evaluable_cases']} |"
    )
    lines.append("")
    lines.append("## 每题 (Per-case)")
    lines.append("")
    lines.append(
        "| id | title | status | paper | eff_baseline | eff_parallel | "
        "eff_core | topic_ds | quarantined | axis | reason |"
    )
    lines.append(
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|"
    )
    for c in per_case:
        lines.append(
            "| {cid} | {title} | {st} | {pp} | {eb} | {ep} | {ec} | "
            "{td} | {qn} | {ax} | {rs} |".format(
                cid=c.get("case_id", "?"),
                title=(c.get("title") or "")[:40],
                st=c.get("status", "?"),
                pp=c.get("paper_n", 0),
                eb=c.get("effective_baseline_n", 0),
                ep=c.get("effective_parallel_n", 0),
                ec=c.get("effective_core_n", 0),
                td=c.get("topic_dataset_n", 0),
                qn=(c.get("quarantined_baseline_n", 0)
                    + c.get("quarantined_parallel_n", 0)
                    + c.get("quarantined_core_n", 0)),
                ax=c.get("axis_status", "?"),
                rs=(c.get("reason") or "")[:80],
            )
        )
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_jsonl(path: str) -> list[dict]:
    """Load a JSONL file; one record per non-empty line."""
    out: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out