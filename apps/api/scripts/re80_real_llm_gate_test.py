"""Re8.0 WP6 Real LLM Reflection Gate Test.

Runs the actual Reflection Gate nodes against realistic state using the
configured provider. This validates that the LLM path (not short-circuit,
not rule fallback) produces well-formed gate results.

Usage:
    python apps/api/scripts/re80_real_llm_gate_test.py
    python apps/api/scripts/re80_real_llm_gate_test.py --gate seed_audit
    python apps/api/scripts/re80_real_llm_gate_test.py --gate tailor
    python apps/api/scripts/re80_real_llm_gate_test.py --gate final_review
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("re80_gate_test")

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"), override=True)
except ImportError:
    pass


def _build_full_agent_state() -> dict:
    """Build a realistic Full Agent state for Reflection Gate testing."""
    return {
        "run_mode": "full_agent",
        "reasoning_policy": "react_reflection",
        "entry_mode": "seeded_research",
        "topic": "Vision Transformer for steel surface defect detection",
        "topic_atoms": {
            "method": ["vision transformer", "ViT"],
            "object": ["steel surface"],
            "task": ["defect detection"],
            "domain": "computer_vision",
        },
        "seed_cards": [
            {
                "seed_id": "S1",
                "input_form": "arxiv",
                "resolved_title": "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale",
                "authors": ["Dosovitskiy", "Beyer"],
                "year": 2021,
                "doi": None,
                "canonical_url": "https://arxiv.org/abs/2010.11929",
                "existence_status": "verified",
                "fulltext_status": "metadata_only",
                "role": "classic_anchor",
                "task_definition": "Image classification using pure Transformer architecture",
                "method_summary": "Splits image into patches, linearly embeds, applies Transformer encoder",
                "dataset_and_metrics": {"datasets": ["ImageNet"], "metrics": ["top-1 accuracy"]},
                "reproduction_environment": {"framework": "JAX", "repo": "google-research/vision_transformer"},
                "limitations": ["Requires large datasets for good performance", "Quadratic attention cost"],
                "evidence_ids": ["E1"],
            },
        ],
        "evidence_gaps": [
            {
                "gap_id": "G1",
                "question": "What are current SOTA methods for steel surface defect detection?",
                "gap_type": "current_baseline",
                "why_needed": "Need competitive baselines for fair comparison",
                "related_claim_ids": [],
                "success_condition": "find 2+ competing baseline papers",
                "budget": {},
                "status": "open",
            },
        ],
        "method_families": [
            {
                "family_id": "F1",
                "name": "CNN-based detection",
                "task_type": "detection",
                "relation_to_seed": "alternative_formulation",
                "applicability_conditions": ["grid-like defect patterns"],
                "interface_requirements": ["image input", "bounding box output"],
                "expected_strengths": ["mature", "efficient"],
                "expected_weaknesses": ["limited global context"],
                "search_queries": ["YOLO steel defect", "Faster R-CNN surface inspection"],
            },
        ],
        "tailored_method": {
            "baseline": {"name": "ViT-Base", "source": "seed paper S1"},
            "candidate_modules": [
                {"name": "Feature Pyramid Network", "source": "FPN paper",
                 "interface": "multi-scale feature maps", "training_compatibility": "compatible"},
            ],
            "compatibility_matrix": {
                "module_interface": "compatible",
                "training_objective": "compatible",
                "data_requirement": "needs labeled detection data",
            },
            "ablation_matrix": [
                {"experiment": "ViT + FPN vs ViT only", "metric": "mAP", "expected_delta": "+5%"},
            ],
            "verdict": "GO",
            "gaps_identified": ["Need steel defect dataset", "Need detection head implementation"],
        },
        "novelty_review_verdict": "accepted",
        "falsifiable_hypothesis": "Adding FPN to ViT improves small defect detection by 5% mAP on NEU-DET",
        "contribution_type": "methodological",
        "pressure_points": [
            "FPN may not help if defects are large",
            "ViT may overfit on small steel defect datasets",
        ],
        "reflection_gate_results": {},
    }


def _run_gate_test(gate_name: str) -> dict:
    """Run a single Reflection Gate with real LLM. Returns diagnostics."""
    from apps.api.app.services.agents.graph.nodes.reflection_gates import (
        seed_audit_gate_node,
        tailor_gate_node,
        final_review_gate_node,
    )

    state = _build_full_agent_state()

    gate_map = {
        "seed_audit": ("seed_audit_gate", seed_audit_gate_node),
        "tailor": ("tailor_gate", tailor_gate_node),
        "final_review": ("final_review_gate", final_review_gate_node),
    }

    if gate_name not in gate_map:
        raise ValueError(f"Unknown gate: {gate_name}. Choose from {list(gate_map.keys())}")

    formal_name, node_fn = gate_map[gate_name]

    logger.info("=== Running %s with real LLM ===", formal_name)
    logger.info("run_mode=full_agent, reasoning_policy=react_reflection (LLM path should activate)")
    t0 = time.time()

    try:
        result = node_fn(state)
        elapsed = time.time() - t0

        gate_results = result.get("reflection_gate_results", {})
        gate_log = gate_results.get(formal_name, [])
        last_entry = gate_log[-1] if gate_log else {}

        trace_events = result.get("trace_events", [])
        trace = trace_events[0] if trace_events else {}

        diagnostics = {
            "gate": formal_name,
            "elapsed_s": round(elapsed, 2),
            "verdict": last_entry.get("verdict", "UNKNOWN"),
            "generated_by": last_entry.get("generated_by", "UNKNOWN"),
            "round_idx": last_entry.get("round_idx", -1),
            "rationale": (last_entry.get("rationale") or "")[:200],
            "re_search_requests": last_entry.get("re_search_requests", []),
            "unresolved_gaps": last_entry.get("unresolved_gaps", []),
            "trace_provider": trace.get("provider", "unknown"),
            "trace_activated": trace.get("input_summary", {}).get("activated", False),
            "ledger_count": len(result.get("reasoning_ledger", [])),
            "success": True,
            "error": None,
        }

        logger.info("--- Results ---")
        logger.info("  verdict:       %s", diagnostics["verdict"])
        logger.info("  generated_by:  %s", diagnostics["generated_by"])
        logger.info("  round_idx:     %s", diagnostics["round_idx"])
        logger.info("  rationale:     %s", diagnostics["rationale"])
        logger.info("  re_search:     %s", diagnostics["re_search_requests"])
        logger.info("  elapsed:       %.2fs", elapsed)
        logger.info("  trace activated: %s", diagnostics["trace_activated"])

        if diagnostics["generated_by"] == "skip":
            logger.warning("  *** WARNING: Gate short-circuited! LLM was NOT called. ***")
            logger.warning("  Check run_mode/reasoning_policy in state.")
        elif diagnostics["generated_by"] == "fallback":
            logger.warning("  *** WARNING: LLM failed, rule fallback used. ***")
            logger.warning("  Check LLM provider configuration.")
        else:
            logger.info("  *** LLM path activated successfully. ***")

        return diagnostics

    except Exception as exc:
        elapsed = time.time() - t0
        logger.exception("Gate %s failed with exception:", formal_name)
        return {
            "gate": formal_name,
            "elapsed_s": round(elapsed, 2),
            "success": False,
            "error": str(exc),
            "verdict": "ERROR",
            "generated_by": "exception",
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Re8.0 Real LLM Reflection Gate Test")
    parser.add_argument("--gate", choices=["seed_audit", "tailor", "final_review", "all"],
                        default="all", help="Which gate to test")
    args = parser.parse_args()

    gates_to_test = ["seed_audit", "tailor", "final_review"] if args.gate == "all" else [args.gate]

    results = []
    for gate in gates_to_test:
        result = _run_gate_test(gate)
        results.append(result)
        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        status = "PASS" if r.get("success") else "FAIL"
        llm_path = "LLM" if r.get("generated_by") == "llm" else r.get("generated_by", "?")
        print(f"  {r['gate']:25s} | {status:4s} | verdict={r.get('verdict', '?'):12s} | by={llm_path:8s} | {r.get('elapsed_s', 0):.1f}s")

    # Check if all gates used LLM path
    all_llm = all(r.get("generated_by") == "llm" for r in results)
    if all_llm:
        print("\n*** ALL GATES USED LLM PATH — Reflection Gate LLM validation PASSED ***")
    else:
        non_llm = [r["gate"] for r in results if r.get("generated_by") != "llm"]
        print(f"\n*** WARNING: Gates {non_llm} did not use LLM path ***")

    # Write results to file
    output_path = os.path.join(ROOT, "tmp_re13_eval", "re80_gate_llm_test.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults written to: {output_path}")


if __name__ == "__main__":
    main()
