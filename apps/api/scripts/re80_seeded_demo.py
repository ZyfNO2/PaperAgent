"""Re8.0 WP8: Seeded Research demo (real LLM, real seeds, all gates active).

Runs the full research_graph pipeline in seeded_research + full_agent mode
with real seed papers (DOI/arXiv). This exercises the FULL pipeline:
  - SeedResolver verifies seeds via Crossref/arXiv network
  - seed_audit_gate reviews seed cards (LLM)
  - PaperUnderstanding / MethodFamily / EvidenceGap
  - TailorSkillAdapter produces tailored_method
  - tailor_gate reviews it (LLM)
  - NoveltyReview + final_review_gate (LLM)

Usage:
  python apps/api/scripts/re80_seeded_demo.py --case yolo_steel
  python apps/api/scripts/re80_seeded_demo.py --case xlm_r
  python apps/api/scripts/re80_seeded_demo.py --case vit_dr
"""
from __future__ import annotations

import json
import os
import sys
import time
import logging
import traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("re80_seeded")

# ── Test cases designed by Herta-sama ───────────────────────────────────────
# Each case has a topic + 2 real seed papers (DOI/arXiv) with assigned roles.
# Roles: classic_anchor / current_sota_candidate / reproduction_target /
#        parallel_inspiration / survey_reference
#
# Re8.0 P0-1: each seed carries identifier + metadata fields BOTH at the
# top-level (canonical Resolver contract) AND inside ``raw_input`` (audit
# trail / PDF bytes carrier). The Resolver normalises ``raw_input`` onto
# top-level, so either form is accepted — but writing both makes the
# contract explicit and survives any future normalisation regression.
CASES = {
    "yolo_steel": {
        "topic": "YOLOv8 for real-time steel surface defect detection on NEU-DET dataset",
        "description": "CV classic: object detection applied to industrial defect inspection",
        "seeds": [
            {
                "seed_id": "S1",
                "input_form": "url",
                "url": "https://arxiv.org/abs/1506.02640",
                "title": "You Only Look Once: Unified, Real-Time Object Detection",
                "authors": ["Redmon, J.", "Divvala, S.", "Girshick, R.", "Farhadi, A."],
                "year": 2016,
                "role": "classic_anchor",
                "raw_input": {
                    "url": "https://arxiv.org/abs/1506.02640",
                    "title": "You Only Look Once: Unified, Real-Time Object Detection",
                    "authors": ["Redmon, J.", "Divvala, S.", "Girshick, R.", "Farhadi, A."],
                    "year": 2016,
                    "role": "classic_anchor",
                },
            },
            {
                "seed_id": "S2",
                "input_form": "citation",
                "title": "Surface defect detection of hot-rolled steel strip based on deep learning",
                "authors": ["Song, K.", "Yan, Y."],
                "year": 2013,
                "role": "reproduction_target",
                "raw_input": {
                    "title": "Surface defect detection of hot-rolled steel strip based on deep learning",
                    "authors": ["Song, K.", "Yan, Y."],
                    "year": 2013,
                    "role": "reproduction_target",
                },
            },
        ],
    },
    "xlm_r": {
        "topic": "Cross-lingual transfer learning for low-resource African languages with XLM-R",
        "description": "NLP: multilingual transformers for low-resource language NLP",
        "seeds": [
            {
                "seed_id": "S1",
                "input_form": "doi",
                "doi": "10.18653/v1/N19-1423",
                "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                "authors": ["Devlin, J.", "Chang, M.", "Lee, K.", "Toutanova, K."],
                "year": 2019,
                "role": "classic_anchor",
                "raw_input": {
                    "doi": "10.18653/v1/N19-1423",
                    "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                    "authors": ["Devlin, J.", "Chang, M.", "Lee, K.", "Toutanova, K."],
                    "year": 2019,
                    "role": "classic_anchor",
                },
            },
            {
                "seed_id": "S2",
                "input_form": "url",
                "url": "https://arxiv.org/abs/1911.02116",
                "title": "Unsupervised Cross-lingual Representation Learning at Scale (XLM-R)",
                "authors": ["Conneau, A.", "Khandelwal, K.", "Goyal, N."],
                "year": 2020,
                "role": "current_sota_candidate",
                "raw_input": {
                    "url": "https://arxiv.org/abs/1911.02116",
                    "title": "Unsupervised Cross-lingual Representation Learning at Scale (XLM-R)",
                    "authors": ["Conneau, A.", "Khandelwal, K.", "Goyal, N."],
                    "year": 2020,
                    "role": "current_sota_candidate",
                },
            },
        ],
    },
    "vit_dr": {
        "topic": "Vision Transformer for automated diabetic retinopathy grading from fundus images",
        "description": "Medical AI: ViT applied to clinical retinal screening",
        "seeds": [
            {
                "seed_id": "S1",
                "input_form": "url",
                "url": "https://arxiv.org/abs/2010.11929",
                "title": "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale (ViT)",
                "authors": ["Dosovitskiy, A.", "Beyer, L.", "Kolesnikov, A."],
                "year": 2021,
                "role": "classic_anchor",
                "raw_input": {
                    "url": "https://arxiv.org/abs/2010.11929",
                    "title": "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale (ViT)",
                    "authors": ["Dosovitskiy, A.", "Beyer, L.", "Kolesnikov, A."],
                    "year": 2021,
                    "role": "classic_anchor",
                },
            },
            {
                "seed_id": "S2",
                "input_form": "doi",
                "doi": "10.1001/jama.2016.17216",
                "title": "Development and Validation of a Deep Learning Algorithm for Detection of Diabetic Retinopathy in Retinal Fundus Photographs",
                "authors": ["Gulshan, V.", "Peng, L.", "Coram, M."],
                "year": 2016,
                "role": "reproduction_target",
                "raw_input": {
                    "doi": "10.1001/jama.2016.17216",
                    "title": "Development and Validation of a Deep Learning Algorithm for Detection of Diabetic Retinopathy in Retinal Fundus Photographs",
                    "authors": ["Gulshan, V.", "Peng, L.", "Coram, M."],
                    "year": 2016,
                    "role": "reproduction_target",
                },
            },
        ],
    },
}


def _compute_contract_pass(final_state: dict) -> tuple[bool, list[str]]:
    """Check if all contract fields are properly populated.

    Returns (passed, failure_reasons). passed=True if all checks pass.

    Checks:
    1. seed_cards: if entry_mode=seeded_research and n_seeds_input>0,
       at least 1 seed must have resolved_title non-empty
    2. reflection_gate_results: all 3 gates (seed_audit, tailor, final_review)
       must have at least 1 entry each
    3. reasoning_ledger: must have >=1 entry
    4. tailored_method: if entry_mode=seeded_research, must be non-empty dict
    5. final_recommendation: must have n_papers > 0
    """
    reasons: list[str] = []
    entry_mode = final_state.get("entry_mode", "topic_only")
    candidate_seeds = final_state.get("candidate_seeds") or []
    n_seeds_input = len(candidate_seeds)

    # Check 1: seed_cards must have at least 1 resolved_title
    if entry_mode == "seeded_research" and n_seeds_input > 0:
        seed_cards = final_state.get("seed_cards") or []
        has_resolved = any(
            (c.get("resolved_title") or "").strip() for c in seed_cards
        )
        if not has_resolved:
            reasons.append("seed_cards: no seed has resolved_title")

    # Check 2: all 3 reflection gates must have >=1 entry
    gate_results = final_state.get("reflection_gate_results") or {}
    for gate_name in ("seed_audit_gate", "tailor_gate", "final_review_gate"):
        entries = gate_results.get(gate_name) or []
        if not entries:
            reasons.append(f"reflection_gate_results: {gate_name} has no entries")

    # Check 3: reasoning_ledger must have >=1 entry
    ledger = final_state.get("reasoning_ledger") or []
    if len(ledger) < 1:
        reasons.append("reasoning_ledger: empty (expected >=1 entry)")

    # Check 4: tailored_method must be non-empty dict in seeded_research mode
    if entry_mode == "seeded_research":
        tailored = final_state.get("tailored_method")
        if not isinstance(tailored, dict) or not tailored:
            reasons.append("tailored_method: empty or not a dict (seeded_research mode)")

    # Check 5: final_recommendation must have n_papers > 0
    final_rec = final_state.get("final_recommendation") or {}
    if not isinstance(final_rec, dict) or (final_rec.get("n_papers", 0) or 0) <= 0:
        reasons.append("final_recommendation: n_papers is 0 or missing")

    return (len(reasons) == 0, reasons)


def _compute_quality_pass(final_state: dict) -> tuple[bool, list[str]]:
    """Check if quality criteria are met.

    Returns (passed, failure_reasons). passed=True if all checks pass.

    Re8.0 post-audit fix: the previous version reported quality_pass=true
    even when fused_verdict=BLOCKED or a Reflection Gate was unresolved,
    creating a self-contradictory result (yolo_steel/xlm_r reported
    quality_pass=true with fused_verdict=BLOCKED). The new version
    enforces:
      - fused_verdict must NOT be BLOCKED
      - no Reflection Gate may be unresolved
      - at least 1 gap must have traceable evidence_delta (not just a
        status flag set by a fallback)

    Checks:
    1. At least 1 seed with existence_status="verified" (if seeded_research)
    2. tailored_method.core_method (or assembly_plan.description) non-empty
    3. At least 1 evidence_gap with status="satisfied" or "partially_satisfied"
       AND that gap_id has traceable evidence_delta in search_steps
    4. fused_verdict != "BLOCKED" (state top-level field, P0-A)
    5. No Reflection Gate (seed_audit / tailor / final_review) is unresolved
    6. final_recommendation.low_bar_status == "pass"
    7. If novelty_review_verdict exists, it should not be "reject"
    """
    reasons: list[str] = []
    entry_mode = final_state.get("entry_mode", "topic_only")

    # Check 1: at least 1 verified seed (seeded_research only)
    if entry_mode == "seeded_research":
        seed_cards = final_state.get("seed_cards") or []
        has_verified = any(
            c.get("existence_status") == "verified" for c in seed_cards
        )
        if not has_verified:
            reasons.append("no verified seed (all ambiguous or not_found)")

    # Check 2: tailored_method.core_method non-empty (seeded_research only)
    # Re8.0 P1-2: production schema (_normalize_tailor_output) does not
    # produce a top-level ``core_method`` field — the method description
    # lives in ``assembly_plan.description``. Mirror the fallback that
    # ``content._assemble_final_research_package`` already uses so this
    # check does not fail on every production pipeline run.
    if entry_mode == "seeded_research":
        tailored = final_state.get("tailored_method") or {}
        core_method = (tailored.get("core_method") or "").strip()
        if not core_method:
            assembly = tailored.get("assembly_plan") or {}
            core_method = (assembly.get("description") or "").strip()
        if not core_method:
            reasons.append(
                "tailored_method.core_method is empty "
                "(and assembly_plan.description is empty)"
            )

    # Check 3: at least 1 gap with traceable evidence_delta
    # Re8.0 post-audit fix: previously this check only verified that at
    # least 1 gap had status in {satisfied, partially_satisfied}. But the
    # P1-7b fallback marked all open gaps as partially_satisfied whenever
    # any papers/repos were found, without verifying that the search
    # results were actually attributable to those gaps (gap_id=null,
    # evidence_delta=null in search_steps). Now we require that the
    # gap_id appears in at least one search_step with a non-zero
    # evidence_delta (n_new_papers > 0 or n_new_repos > 0).
    gaps = final_state.get("evidence_gaps") or []
    steps = final_state.get("search_steps") or []
    gaps_with_evidence: set[str] = set()
    for s in steps:
        gid = s.get("gap_id")
        if not gid:
            continue
        delta = s.get("evidence_delta") or {}
        if delta.get("n_new_papers", 0) > 0 or delta.get("n_new_repos", 0) > 0:
            gaps_with_evidence.add(gid)
    has_satisfied_with_evidence = any(
        g.get("gap_id") in gaps_with_evidence
        and g.get("status") in ("satisfied", "partially_satisfied")
        for g in gaps
    )
    if gaps and not has_satisfied_with_evidence:
        reasons.append(
            "no evidence gap has traceable evidence_delta "
            "(gaps may be marked partially_satisfied but no step-level "
            "gap_id match with non-zero papers/repos)"
        )

    # Check 4: fused_verdict must NOT be BLOCKED
    # Re8.0 post-audit fix: BLOCKED means the decision fusion determined
    # the pipeline cannot produce a GO. quality_pass=true with
    # fused_verdict=BLOCKED is self-contradictory.
    fused_verdict = (final_state.get("fused_verdict") or "").upper()
    if fused_verdict == "BLOCKED":
        reasons.append(
            "fused_verdict is BLOCKED (quality_pass cannot be true "
            "when the pipeline is blocked)"
        )

    # Check 5: no Reflection Gate may be unresolved
    # Re8.0 post-audit fix: an unresolved gate means the gate hit its
    # round cap without converging. quality_pass=true with an unresolved
    # gate masks the fact that the pipeline did not actually resolve
    # the issue.
    gate_results = final_state.get("reflection_gate_results") or {}
    for gate_name in ("seed_audit_gate", "tailor_gate", "final_review_gate"):
        entries = gate_results.get(gate_name) or []
        if entries:
            last_entry = entries[-1]
            if last_entry.get("verdict") == "unresolved":
                reasons.append(
                    f"reflection_gate {gate_name} is unresolved "
                    f"(round_idx cap reached without convergence)"
                )

    # Check 6: final_recommendation.low_bar_status == "pass"
    final_rec = final_state.get("final_recommendation") or {}
    if final_rec.get("low_bar_status") != "pass":
        reasons.append(
            f"final_recommendation.low_bar_status is not 'pass' "
            f"(got: {final_rec.get('low_bar_status')!r})"
        )

    # Check 7: novelty_review_verdict should not be "reject"
    novelty_verdict = final_state.get("novelty_review_verdict")
    if novelty_verdict and novelty_verdict == "reject":
        reasons.append("novelty_review_verdict is 'reject'")

    return (len(reasons) == 0, reasons)


def run_seeded_demo(case_key: str) -> dict:
    """Run seeded_research demo. Returns diagnostics."""
    from apps.api.app.services.agents.graph.research_graph import build_graph
    from apps.api.app.services.agents.graph.state import ResearchState

    cfg = CASES[case_key]
    initial_state: ResearchState = {
        "topic": cfg["topic"],
        "mode": "full",
        "run_mode": "full_agent",
        "reasoning_policy": "react_reflection",
        "entry_mode": "seeded_research",
        "candidate_seeds": cfg["seeds"],
    }

    g = build_graph()
    t0 = time.time()
    result: dict = {
        "case_key": case_key,
        "topic": cfg["topic"],
        "description": cfg["description"],
        "n_seeds_input": len(cfg["seeds"]),
        "mode": "seeded_research + full_agent + react_reflection",
        "status": "unknown",
        "elapsed_s": 0.0,
        "error": None,
        # Re8.0 Task 4: Three-Tier PASS defaults (populated after invoke)
        "runtime_pass": False,
        "contract_pass": False,
        "contract_pass_reasons": ["pipeline not yet run"],
        "quality_pass": False,
        "quality_pass_reasons": ["pipeline not yet run"],
    }

    try:
        config = {
            "recursion_limit": 100,  # seeded_research may need more steps
            "configurable": {"thread_id": f"re80_seeded_{case_key}"},
        }
        logger.info("Starting seeded demo: %s", case_key)
        final_state = g.invoke(initial_state, config=config)
        elapsed = time.time() - t0
        result["elapsed_s"] = round(elapsed, 1)

        # Re8.0 Task 4: compute contract_pass and quality_pass from
        # final_state (independent of whether final_rec exists).
        contract_passed, contract_reasons = _compute_contract_pass(final_state)
        quality_passed, quality_reasons = _compute_quality_pass(final_state)
        result["contract_pass"] = contract_passed
        result["contract_pass_reasons"] = contract_reasons
        result["quality_pass"] = quality_passed
        result["quality_pass_reasons"] = quality_reasons

        final_rec = final_state.get("final_recommendation")
        if not final_rec:
            result["status"] = "FAIL"
            result["error"] = "final_recommendation is missing"
            result["runtime_pass"] = False
            return result

        result["status"] = "PASS"
        result["runtime_pass"] = True
        # Re8.2 WP4: embed full final_state for downstream artifact extraction
        # (removed by the wrapper before writing the public summary)
        result["_final_state"] = final_state
        result["final_rec"] = {
            "topic": final_rec.get("topic", ""),
            "n_papers": final_rec.get("n_papers", 0),
            "n_baseline": final_rec.get("n_baseline", 0),
            "n_parallel": final_rec.get("n_parallel", 0),
            "n_dataset": final_rec.get("n_dataset", 0),
            "n_repo": final_rec.get("n_repo", 0),
            "n_work_packages": final_rec.get("n_work_packages", 0),
            "low_bar_status": final_rec.get("low_bar_status", ""),
        }

        # Seed cards (after resolver)
        seed_cards = final_state.get("seed_cards", [])
        result["seed_cards"] = [
            {
                "seed_id": c.get("seed_id"),
                "resolved_title": (c.get("resolved_title") or "")[:80],
                "existence_status": c.get("existence_status"),
                "role": c.get("role"),
            }
            for c in seed_cards
        ]

        # Trace events
        traces = final_state.get("trace_events", [])
        result["n_trace_events"] = len(traces)
        gate_traces = [t for t in traces if "gate" in t.get("node", "")]
        result["n_gate_traces"] = len(gate_traces)

        providers = {}
        for t in traces:
            prov = t.get("provider") or t.get("provider_summary", {}).get("provider", "unknown")
            providers[prov] = providers.get(prov, 0) + 1
        result["providers_used"] = providers

        # Reflection Gate results (should be LLM-driven)
        gate_results = final_state.get("reflection_gate_results", {})
        for gate_name in ("seed_audit_gate", "tailor_gate", "final_review_gate"):
            entries = gate_results.get(gate_name, [])
            if entries:
                last = entries[-1]
                result[f"gate_{gate_name}"] = {
                    "verdict": last.get("verdict"),
                    "generated_by": last.get("generated_by"),
                    "round_idx": last.get("round_idx"),
                    "rationale": (last.get("rationale") or "")[:300],
                    "re_search_requests": last.get("re_search_requests", []),
                    "unresolved_gaps": last.get("unresolved_gaps", []),
                    # Re8.0 third batch: export full rounds list for diagnosis
                    "all_rounds": [
                        {
                            "round_idx": e.get("round_idx"),
                            "verdict": e.get("verdict"),
                            "generated_by": e.get("generated_by"),
                            "rationale": (e.get("rationale") or "")[:200],
                        }
                        for e in entries
                    ],
                }
            else:
                result[f"gate_{gate_name}"] = None

        # Ledger
        ledger = final_state.get("reasoning_ledger") or []
        result["n_ledger_entries"] = len(ledger)

        # react_actions
        react_actions = final_state.get("react_actions") or []
        result["n_react_actions"] = len(react_actions)

        # Errors
        errors = final_state.get("errors", [])
        result["n_errors"] = len(errors)
        if errors:
            result["error_samples"] = [str(e.get("error", e))[:120] for e in errors[:3]]

        # Pipeline output
        verified = final_state.get("verified_papers", [])
        result["n_verified_papers"] = len(verified)
        search_steps = final_state.get("search_steps", [])
        result["n_search_steps"] = len(search_steps)

        # Tailored method
        tailored = final_state.get("tailored_method") or {}
        result["tailored_verdict"] = tailored.get("verdict")
        result["tailored_ablation_rows"] = len(tailored.get("ablation_matrix") or [])
        if tailored:
            result["tailored_method_summary"] = {
                "contribution_type": tailored.get("contribution_type"),
                "core_method": (tailored.get("core_method") or "")[:120],
                "baseline_model": tailored.get("baseline_model"),
            }

        # Novelty
        result["novelty_review_verdict"] = final_state.get("novelty_review_verdict")
        hypothesis = final_state.get("falsifiable_hypothesis") or ""
        result["has_falsifiable_hypothesis"] = bool(hypothesis and hypothesis != "unspecified")
        result["hypothesis_preview"] = hypothesis[:150] if hypothesis else ""

        # Evidence gaps
        gaps = final_state.get("evidence_gaps") or []
        result["n_evidence_gaps"] = len(gaps)
        result["gap_statuses"] = {}
        for g in gaps:
            status = g.get("status", "unknown")
            result["gap_statuses"][status] = result["gap_statuses"].get(status, 0) + 1

        # Re8.0 P1-7 debug: gap_id / status / evidence_delta correlation
        result["evidence_gaps_debug"] = [
            {
                "gap_id": g.get("gap_id", ""),
                "status": g.get("status", "unknown"),
                "description": (g.get("description") or g.get("gap_description") or "")[:120],
                "lane_id": g.get("lane_id", ""),
            }
            for g in gaps
        ]
        steps_dbg = final_state.get("search_steps") or []
        result["search_steps_debug"] = [
            {
                "step": s.get("step"),
                "type": s.get("type"),
                "gap_id": s.get("gap_id"),
                "evidence_delta": s.get("evidence_delta"),
                "tool": s.get("tool"),
                "n_results": s.get("n_results"),
            }
            for s in steps_dbg
        ]

        # Re8.0 Task 8 verification: fused_verdict (Task 6) and
        # final_research_package (Task 7) must be present and well-formed.
        result["fused_verdict"] = final_state.get("fused_verdict")
        result["fused_verdict_rationale"] = (
            final_state.get("fused_verdict_rationale") or ""
        )[:300]

        research_package = final_state.get("final_research_package") or {}
        result["final_research_package_sections"] = sorted(research_package.keys())
        result["final_research_package_section_count"] = len(research_package)
        # Expected 7 sections per Task 7.2
        expected_sections = {
            "seed_audit_summary",
            "tailor_summary",
            "gate_results",
            "ledger_entries",
            "evidence_gap_status",
            "falsifiable_hypothesis",
            "fused_verdict",
        }
        present_sections = set(research_package.keys())
        result["final_research_package_missing_sections"] = sorted(
            expected_sections - present_sections
        )
        # Also embed fused_verdict from final_rec (Task 6.3)
        if isinstance(final_rec, dict):
            result["final_rec_fused_verdict"] = final_rec.get("fused_verdict")
            result["final_rec_has_research_package"] = (
                "research_package" in final_rec
            )

        # Re8.0 Task 2 verification: detect conditional repair routing
        # cycles by scanning trace events for the gate→upstream→gate pattern.
        # Re8.0 P1-4: also count gate round_idx > 0 as a repair cycle signal,
        # because cap-reached (unresolved) gates do not produce the
        # gate→upstream→gate trace pattern (they forward immediately after
        # cap), yet they DID undergo repair attempts in previous rounds.
        node_seq = [t.get("node", "") for t in traces]
        repair_cycles_detected = []
        gate_to_upstream = {
            "seed_audit_gate": "seed_resolver",
            "tailor_gate": "search_planner",
            "final_review_gate": "evidence_context",
        }
        # Pattern 1: gate → upstream → same gate (explicit repair cycle in trace)
        for i, node in enumerate(node_seq):
            upstream = gate_to_upstream.get(node)
            if not upstream:
                continue
            # Look ahead: gate → upstream → same gate again within next 6 steps
            window = node_seq[i + 1: i + 7]
            if upstream in window and node in window:
                repair_cycles_detected.append(
                    f"{node}→{upstream}→{node}"
                )
        # Pattern 2 (P1-4): gate with round_idx > 0 but no explicit trace cycle
        # detected above. This covers cap-reached (unresolved) gates that
        # underwent repair in earlier rounds but forwarded after cap.
        gate_results_state = final_state.get("reflection_gate_results") or {}
        explicit_cycle_gates = {
            c.split("→")[0] for c in repair_cycles_detected
        }
        for gate_name, entries in gate_results_state.items():
            if not entries or gate_name in explicit_cycle_gates:
                continue
            max_round = max(
                (int(e.get("round_idx", 0)) for e in entries),
                default=0,
            )
            if max_round > 0:
                repair_cycles_detected.append(
                    f"{gate_name}:round_idx={max_round}(cap-reached,implicit)"
                )
        result["repair_cycles_detected"] = repair_cycles_detected
        result["n_repair_cycles"] = len(repair_cycles_detected)

    except Exception as exc:
        elapsed = time.time() - t0
        result["elapsed_s"] = round(elapsed, 1)
        result["status"] = "FAIL"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()[-1000:]
        # Re8.0 Task 4: pipeline crashed — no final_state to evaluate
        result["runtime_pass"] = False
        result["contract_pass"] = False
        result["contract_pass_reasons"] = [
            "pipeline crashed; no final_state to evaluate"
        ]
        result["quality_pass"] = False
        result["quality_pass_reasons"] = [
            "pipeline crashed; no final_state to evaluate"
        ]

    return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=list(CASES.keys()) + ["all"], default="all")
    args = parser.parse_args()

    if args.case == "all":
        cases_to_run = list(CASES.keys())
    else:
        cases_to_run = [args.case]

    results = {}
    for ck in cases_to_run:
        print(f"\n{'='*70}")
        print(f"=== Seeded Demo: {ck} ===")
        print(f"Topic: {CASES[ck]['topic']}")
        print(f"Seeds: {len(CASES[ck]['seeds'])} papers")
        print(f"{'='*70}")
        r = run_seeded_demo(ck)
        results[ck] = r
        status_icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"\n{status_icon} {ck}: {r['status']} ({r['elapsed_s']}s)")
        if r["status"] == "FAIL":
            print(f"   Error: {r.get('error')}")

    # Write results
    # Re8.0 P1-7: support RE80_DEMO_OUT env var for parallel runs (each
    # case writes to a distinct file to avoid clobbering).
    out_path = os.environ.get("RE80_DEMO_OUT") or os.path.join(
        ROOT, "tmp_re13_eval", "re80_seeded_demo_results.json"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults written to {out_path}")

    # Re8.0 Task 4: Three-Tier PASS summary per case
    print(f"\n{'='*70}")
    print(f"=== Three-Tier PASS Summary ===")
    for ck, r in results.items():
        rt = r.get("runtime_pass", False)
        ct = r.get("contract_pass", False)
        ql = r.get("quality_pass", False)
        rt_icon = "✅" if rt else "❌"
        ct_icon = "✅" if ct else "❌"
        ql_icon = "✅" if ql else "❌"

        print(f"\n=== Summary: {ck} ===")
        print(f"  runtime_pass:  {rt_icon} {str(rt).lower()}")
        if ct:
            print(f"  contract_pass: {ct_icon} {str(ct).lower()}")
        else:
            reasons = "; ".join(r.get("contract_pass_reasons", []))
            print(f"  contract_pass: {ct_icon} {str(ct).lower()} (reasons: {reasons})")
        if ql:
            print(f"  quality_pass:  {ql_icon} {str(ql).lower()}")
        else:
            reasons = "; ".join(r.get("quality_pass_reasons", []))
            print(f"  quality_pass:  {ql_icon} {str(ql).lower()} (reasons: {reasons})")

    # Overall tier totals
    n_total = len(results)
    n_rt = sum(1 for r in results.values() if r.get("runtime_pass"))
    n_ct = sum(1 for r in results.values() if r.get("contract_pass"))
    n_ql = sum(1 for r in results.values() if r.get("quality_pass"))
    print(
        f"\n=== Totals: runtime={n_rt}/{n_total}, "
        f"contract={n_ct}/{n_total}, quality={n_ql}/{n_total} ==="
    )

    # Exit code: only quality_pass=true counts as true success.
    n_fail = sum(1 for r in results.values() if not r.get("quality_pass"))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
