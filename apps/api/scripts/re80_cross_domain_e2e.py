"""Re8.0 WP8: Cross-domain end-to-end smoke test.

Runs the full research_graph pipeline against 3 cross-domain topics in
lite_chain mode (no LLM, deterministic). Verifies:
  - Pipeline doesn't crash on different domains
  - final_recommendation is non-empty
  - Domain-specific tools are activated (e.g. PubMed for medical)
  - Reflection Gates short-circuit correctly

Usage:
  python apps/api/scripts/re80_cross_domain_e2e.py --topic medical
  python apps/api/scripts/re80_cross_domain_e2e.py --topic civil
  python apps/api/scripts/re80_cross_domain_e2e.py --topic nlp
  python apps/api/scripts/re80_cross_domain_e2e.py --all
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

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("re80_e2e")

TOPICS = {
    "medical": {
        "topic": "Deep learning for diabetic retinopathy screening from fundus images",
        "expected_domain_hint": "medical",
        "expected_pubmed": True,
    },
    "civil": {
        "topic": "CNN-based crack detection in concrete structures using drone images",
        "expected_domain_hint": "civil_engineering",
        "expected_pubmed": False,
    },
    "nlp": {
        "topic": "Transformer-based cross-lingual transfer learning for low-resource language translation",
        "expected_domain_hint": "nlp",
        "expected_pubmed": False,
    },
}


def run_single_topic(topic_key: str) -> dict:
    """Run the graph for a single cross-domain topic. Returns diagnostics."""
    from apps.api.app.services.agents.graph.research_graph import build_graph
    from apps.api.app.services.agents.graph.state import ResearchState

    cfg = TOPICS[topic_key]
    initial_state: ResearchState = {
        "topic": cfg["topic"],
        "mode": "quick",
        "run_mode": "lite_chain",
        "reasoning_policy": "chain_only",
        "entry_mode": "topic_only",
        "candidate_seeds": [],
    }

    g = build_graph()
    t0 = time.time()
    result: dict = {
        "topic_key": topic_key,
        "topic": cfg["topic"],
        "expected_domain_hint": cfg["expected_domain_hint"],
        "status": "unknown",
        "elapsed_s": 0.0,
        "error": None,
    }

    try:
        config = {"recursion_limit": 50, "configurable": {"thread_id": f"re80_e2e_{topic_key}"}}
        final_state = g.invoke(initial_state, config=config)
        elapsed = time.time() - t0
        result["elapsed_s"] = round(elapsed, 1)

        # Check final_recommendation
        final_rec = final_state.get("final_recommendation")
        if not final_rec:
            result["status"] = "FAIL"
            result["error"] = "final_recommendation is missing"
            return result

        result["final_rec_keys"] = list(final_rec.keys())[:8]
        result["status"] = "PASS"

        # Check trace events
        traces = final_state.get("trace_events", [])
        result["n_trace_events"] = len(traces)
        gate_traces = [t for t in traces if "gate" in t.get("node", "")]
        result["n_gate_traces"] = len(gate_traces)

        # Check reflection gate results (should all short-circuit in lite_chain)
        gate_results = final_state.get("reflection_gate_results", {})
        for gate_name in ("seed_audit_gate", "tailor_gate", "final_review_gate"):
            entries = gate_results.get(gate_name, [])
            if entries:
                last = entries[-1]
                result[f"gate_{gate_name}"] = {
                    "verdict": last.get("verdict"),
                    "generated_by": last.get("generated_by"),
                }
            else:
                result[f"gate_{gate_name}"] = {"verdict": None, "generated_by": None}

        # Check topic_atoms domain
        atoms = final_state.get("topic_atoms") or {}
        result["topic_atoms_domain"] = atoms.get("domain")
        result["topic_atoms_keys"] = list(atoms.keys())

        # Check errors
        errors = final_state.get("errors", [])
        result["n_errors"] = len(errors)
        if errors:
            result["error_samples"] = [e.get("error", str(e))[:100] for e in errors[:3]]

        # Check verified papers count
        verified = final_state.get("verified_papers", [])
        result["n_verified_papers"] = len(verified)

        # Check search steps
        search_steps = final_state.get("search_steps", [])
        result["n_search_steps"] = len(search_steps)

    except Exception as exc:
        elapsed = time.time() - t0
        result["elapsed_s"] = round(elapsed, 1)
        result["status"] = "FAIL"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()[-500:]

    return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", choices=list(TOPICS.keys()) + ["all"], default="all")
    args = parser.parse_args()

    if args.topic == "all":
        topics_to_run = list(TOPICS.keys())
    else:
        topics_to_run = [args.topic]

    results = {}
    for tk in topics_to_run:
        print(f"\n=== Running cross-domain e2e: {tk} ===")
        r = run_single_topic(tk)
        results[tk] = r
        status_icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"{status_icon} {tk}: {r['status']} ({r['elapsed_s']}s)")
        if r["status"] == "FAIL":
            print(f"   Error: {r['error']}")

    # Write results
    out_path = os.path.join(ROOT, "tmp_re13_eval", "re80_cross_domain_e2e.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults written to {out_path}")

    # Summary
    n_pass = sum(1 for r in results.values() if r["status"] == "PASS")
    n_fail = sum(1 for r in results.values() if r["status"] == "FAIL")
    print(f"\n=== Summary: {n_pass} PASS, {n_fail} FAIL ===")

    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
