"""Re8.0 WP8: Full Agent demo path (real LLM, 3-5 min demonstrable run).

Runs the full research_graph pipeline in full_agent mode with react_reflection
policy, exercising all 3 Reflection Gates with real LLM. This is the WP8
"3-5 min demo path" acceptance criterion.

Usage:
  python apps/api/scripts/re80_full_agent_demo.py --topic medical
  python apps/api/scripts/re80_full_agent_demo.py --topic nlp
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
logger = logging.getLogger("re80_demo")

TOPICS = {
    "medical": "Deep learning for diabetic retinopathy screening from fundus images",
    "nlp": "Transformer-based cross-lingual transfer learning for low-resource language translation",
    "steel": "Vision Transformer for steel surface defect detection",
}


def run_full_agent_demo(topic_key: str) -> dict:
    """Run full_agent mode demo. Returns diagnostics."""
    from apps.api.app.services.agents.graph.research_graph import build_graph
    from apps.api.app.services.agents.graph.state import ResearchState

    topic = TOPICS[topic_key]
    # full_agent + react_reflection activates all 3 Reflection Gates
    initial_state: ResearchState = {
        "topic": topic,
        "mode": "full",
        "run_mode": "full_agent",
        "reasoning_policy": "react_reflection",
        "entry_mode": "topic_only",
        "candidate_seeds": [],
    }

    g = build_graph()
    t0 = time.time()
    result: dict = {
        "topic_key": topic_key,
        "topic": topic,
        "mode": "full_agent",
        "status": "unknown",
        "elapsed_s": 0.0,
        "error": None,
    }

    try:
        config = {
            "recursion_limit": 80,  # full_agent may need more steps
            "configurable": {"thread_id": f"re80_demo_{topic_key}"},
        }
        final_state = g.invoke(initial_state, config=config)
        elapsed = time.time() - t0
        result["elapsed_s"] = round(elapsed, 1)

        final_rec = final_state.get("final_recommendation")
        if not final_rec:
            result["status"] = "FAIL"
            result["error"] = "final_recommendation is missing"
            return result

        result["status"] = "PASS"
        result["final_rec_keys"] = list(final_rec.keys())[:8]
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

        # Trace events
        traces = final_state.get("trace_events", [])
        result["n_trace_events"] = len(traces)
        gate_traces = [t for t in traces if "gate" in t.get("node", "")]
        result["n_gate_traces"] = len(gate_traces)

        # Provider breakdown from traces
        providers = {}
        for t in traces:
            prov = t.get("provider") or t.get("provider_summary", {}).get("provider", "unknown")
            providers[prov] = providers.get(prov, 0) + 1
        result["providers_used"] = providers

        # Reflection Gate results (should be LLM-driven in full_agent mode)
        gate_results = final_state.get("reflection_gate_results", {})
        for gate_name in ("seed_audit_gate", "tailor_gate", "final_review_gate"):
            entries = gate_results.get(gate_name, [])
            if entries:
                last = entries[-1]
                result[f"gate_{gate_name}"] = {
                    "verdict": last.get("verdict"),
                    "generated_by": last.get("generated_by"),
                    "round_idx": last.get("round_idx"),
                    "rationale": (last.get("rationale") or "")[:200],
                    "re_search_requests": last.get("re_search_requests", []),
                    "unresolved_gaps": last.get("unresolved_gaps", []),
                }
            else:
                result[f"gate_{gate_name}"] = None

        # Ledger entries
        ledger = final_state.get("reasoning_ledger") or []
        result["n_ledger_entries"] = len(ledger)

        # react_actions from search_agent
        react_actions = final_state.get("react_actions") or []
        result["n_react_actions"] = len(react_actions)
        if react_actions:
            result["react_action_sample"] = {
                "action_type": react_actions[0].get("action_type"),
                "tool": react_actions[0].get("tool"),
                "whitelist_allowed": react_actions[0].get("whitelist_allowed"),
                "gap_resolved": react_actions[0].get("gap_resolved"),
            }

        # Errors
        errors = final_state.get("errors", [])
        result["n_errors"] = len(errors)
        if errors:
            result["error_samples"] = [str(e.get("error", e))[:100] for e in errors[:3]]

        # Papers and search
        verified = final_state.get("verified_papers", [])
        result["n_verified_papers"] = len(verified)
        search_steps = final_state.get("search_steps", [])
        result["n_search_steps"] = len(search_steps)

        # Tailored method
        tailored = final_state.get("tailored_method") or {}
        result["tailored_verdict"] = tailored.get("verdict")
        result["tailored_ablation_rows"] = len(tailored.get("ablation_matrix") or [])

    except Exception as exc:
        elapsed = time.time() - t0
        result["elapsed_s"] = round(elapsed, 1)
        result["status"] = "FAIL"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()[-800:]

    return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", choices=list(TOPICS.keys()), default="medical")
    args = parser.parse_args()

    print(f"\n=== Re8.0 Full Agent Demo: {args.topic} ===")
    print(f"Topic: {TOPICS[args.topic]}")
    print(f"Mode: full_agent + react_reflection (real LLM, all 3 gates active)")
    print()

    result = run_full_agent_demo(args.topic)

    out_path = os.path.join(ROOT, "tmp_re13_eval", f"re80_demo_{args.topic}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    status_icon = "✅" if result["status"] == "PASS" else "❌"
    print(f"{status_icon} {args.topic}: {result['status']} ({result['elapsed_s']}s)")
    print()

    if result["status"] == "PASS":
        print("--- Final Recommendation ---")
        for k, v in result.get("final_rec", {}).items():
            print(f"  {k}: {v}")
        print()
        print("--- Reflection Gates (LLM-driven) ---")
        for gate in ("seed_audit_gate", "tailor_gate", "final_review_gate"):
            g = result.get(f"gate_{gate}")
            if g:
                print(f"  {gate}: verdict={g['verdict']}, by={g['generated_by']}, "
                      f"round={g['round_idx']}")
                if g.get("re_search_requests"):
                    print(f"    re_search: {g['re_search_requests']}")
            else:
                print(f"  {gate}: (not run)")
        print()
        print(f"--- Audit Trail ---")
        print(f"  trace_events: {result['n_trace_events']}")
        print(f"  gate_traces: {result['n_gate_traces']}")
        print(f"  ledger_entries: {result['n_ledger_entries']}")
        print(f"  react_actions: {result['n_react_actions']}")
        print(f"  providers_used: {result.get('providers_used', {})}")
        print()
        print(f"--- Pipeline Output ---")
        print(f"  verified_papers: {result['n_verified_papers']}")
        print(f"  search_steps: {result['n_search_steps']}")
        print(f"  tailored_verdict: {result.get('tailored_verdict')}")
        print(f"  tailored_ablation_rows: {result.get('tailored_ablation_rows')}")
        if result.get("react_action_sample"):
            print(f"  react_action_sample: {result['react_action_sample']}")
    else:
        print(f"ERROR: {result.get('error')}")
        if result.get("traceback"):
            print(result["traceback"])

    print(f"\nResults written to {out_path}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
