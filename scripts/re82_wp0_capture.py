"""WP0: capture full vit_dr baseline run + trace.
Not a production code change — baseline data collection only.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "artifacts", "re8_2", "baseline")
os.makedirs(OUT, exist_ok=True)

# 1. Run vit_dr via the demo script internals but capture full raw state
from apps.api.app.services.agents.graph.research_graph import build_graph
from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.scripts.re80_seeded_demo import (
    CASES,
    _compute_contract_pass,
    _compute_quality_pass,
)

import time
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

cfg = CASES["vit_dr"]
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
config = {
    "recursion_limit": 100,
    "configurable": {"thread_id": "re82_wp0_vit_dr"},
}
print("=== WP0: Running vit_dr baseline (this takes ~400s) ===")
final_state = g.invoke(initial_state, config=config)
elapsed = time.time() - t0
print(f"=== vit_dr completed in {elapsed:.1f}s ===")

# 2. Build diagnostics (same as re80_seeded_demo.run_seeded_demo)
result = {
    "case_key": "vit_dr",
    "topic": cfg["topic"],
    "description": cfg["description"],
    "n_seeds_input": len(cfg["seeds"]),
    "mode": "seeded_research + full_agent + react_reflection",
    "status": "unknown",
    "elapsed_s": round(elapsed, 1),
    "error": None,
}
contract_passed, contract_reasons = _compute_contract_pass(final_state)
quality_passed, quality_reasons = _compute_quality_pass(final_state)
result["contract_pass"] = contract_passed
result["contract_pass_reasons"] = contract_reasons
result["quality_pass"] = quality_passed
result["quality_pass_reasons"] = quality_reasons

final_rec = final_state.get("final_recommendation") or {}
result["status"] = "PASS"
result["runtime_pass"] = True
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
traces = final_state.get("trace_events", [])
result["n_trace_events"] = len(traces)
gate_traces = [t for t in traces if "gate" in t.get("node", "")]
result["n_gate_traces"] = len(gate_traces)
providers = {}
for t in traces:
    prov = t.get("provider") or t.get("provider_summary", {}).get("provider", "unknown")
    providers[prov] = providers.get(prov, 0) + 1
result["providers_used"] = providers

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

result["n_ledger_entries"] = len(final_state.get("reasoning_ledger") or [])
result["n_react_actions"] = len(final_state.get("react_actions") or [])
errors = final_state.get("errors", [])
result["n_errors"] = len(errors)
if errors:
    result["error_samples"] = [str(e.get("error", e))[:120] for e in errors[:3]]
result["n_verified_papers"] = len(final_state.get("verified_papers") or [])
search_steps = final_state.get("search_steps", [])
result["n_search_steps"] = len(search_steps)
tailored = final_state.get("tailored_method") or {}
result["tailored_verdict"] = tailored.get("verdict")
result["tailored_ablation_rows"] = len(tailored.get("ablation_matrix") or [])
result["novelty_review_verdict"] = final_state.get("novelty_review_verdict")
hypothesis = final_state.get("falsifiable_hypothesis") or ""
result["has_falsifiable_hypothesis"] = bool(hypothesis and hypothesis != "unspecified")
gaps = final_state.get("evidence_gaps") or []
result["n_evidence_gaps"] = len(gaps)
result["gap_statuses"] = {}
for g in gaps:
    status = g.get("status", "unknown")
    result["gap_statuses"][status] = result["gap_statuses"].get(status, 0) + 1
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
result["fused_verdict"] = final_state.get("fused_verdict")
result["fused_verdict_rationale"] = (final_state.get("fused_verdict_rationale") or "")[:300]
research_package = final_state.get("final_research_package") or {}
result["final_research_package_sections"] = sorted(research_package.keys())
result["final_research_package_section_count"] = len(research_package)
result["final_rec_fused_verdict"] = final_rec.get("fused_verdict")
result["final_rec_has_research_package"] = "research_package" in final_rec
node_seq = [t.get("node", "") for t in traces]
repair_cycles_detected = []
gate_to_upstream = {
    "seed_audit_gate": "seed_resolver",
    "tailor_gate": "search_planner",
    "final_review_gate": "evidence_context",
}
for i, node in enumerate(node_seq):
    upstream = gate_to_upstream.get(node)
    if not upstream:
        continue
    window = node_seq[i + 1: i + 7]
    if upstream in window and node in window:
        repair_cycles_detected.append(f"{node}→{upstream}→{node}")
gate_results_state = final_state.get("reflection_gate_results") or {}
explicit_cycle_gates = {c.split("→")[0] for c in repair_cycles_detected}
for gate_name, entries in gate_results_state.items():
    if not entries or gate_name in explicit_cycle_gates:
        continue
    max_round = max((int(e.get("round_idx", 0)) for e in entries), default=0)
    if max_round > 0:
        repair_cycles_detected.append(f"{gate_name}:round_idx={max_round}(cap-reached,implicit)")
result["repair_cycles_detected"] = repair_cycles_detected
result["n_repair_cycles"] = len(repair_cycles_detected)

# 3. Save vit_dr_before.json
vit_dr_path = os.path.join(OUT, "vit_dr_before.json")
with open(vit_dr_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
print(f"Saved: {vit_dr_path}")

# 4. Save trace_events as JSONL
trace_path = os.path.join(OUT, "vit_dr_trace_before.jsonl")
with open(trace_path, "w", encoding="utf-8") as f:
    for t in traces:
        f.write(json.dumps(t, ensure_ascii=False, default=str) + "\n")
print(f"Saved: {trace_path} ({len(traces)} events)")

# 5. Also save full gate_results state
gate_cycles_path = os.path.join(OUT, "vit_dr_gate_cycles.json")
with open(gate_cycles_path, "w", encoding="utf-8") as f:
    json.dump(gate_results, f, ensure_ascii=False, indent=2, default=str)
print(f"Saved: {gate_cycles_path}")
