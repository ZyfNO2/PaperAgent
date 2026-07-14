"""WP1 smoke: run vit_dr and verify gate re-entry fix."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "artifacts", "re8_2", "wp1_smoke")
os.makedirs(OUT, exist_ok=True)

from apps.api.app.services.agents.graph.research_graph import build_graph
from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.scripts.re80_seeded_demo import CASES

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
    "configurable": {"thread_id": "re82_wp1_smoke_vit_dr"},
}
print("=== WP1 Smoke: Running vit_dr ===")
final_state = g.invoke(initial_state, config=config)
elapsed = time.time() - t0
print(f"=== vit_dr completed in {elapsed:.1f}s ===")

# Extract gate results
gate_results = final_state.get("reflection_gate_results", {})
traces = final_state.get("trace_events", [])

print("\n=== Gate Round Analysis ===")
all_ok = True
for gate_name in ("seed_audit_gate", "tailor_gate", "final_review_gate"):
    entries = gate_results.get(gate_name, [])
    verdicts = [f"[{e.get('round_idx')}] {e.get('verdict')}({e.get('generated_by')},cycle={e.get('cycle_id',0)})" for e in entries]
    print(f"{gate_name}: {', '.join(verdicts)}")
    if entries and entries[-1].get("verdict") == "unresolved":
        last = entries[-1]
        # It's OK to be unresolved for CAP if the cap was reached via content reasons,
        # not via re-entry. Check if the last entry's rationale contains "cap reached"
        if "cap reached" in (last.get("rationale") or ""):
            all_ok = False

# Check for reused-pass traces
reuse_traces = [t for t in traces if t.get("input_summary", {}).get("reused_previous_pass")]
print(f"\nReused-pass traces: {len(reuse_traces)}")
for t in reuse_traces:
    ins = t.get("input_summary", {})
    outs = t.get("output_summary", {})
    print(f"  node={t.get('node')} round={ins.get('round_idx')} verdict={outs.get('verdict')} by={outs.get('generated_by')}")

# Check fused verdict
fused = final_state.get("fused_verdict")
rationale = final_state.get("fused_verdict_rationale", "")
print(f"\nfused_verdict={fused}")
print(f"fused_verdict_rationale={rationale}")

# Check last_gate_pass
last_pass = final_state.get("last_gate_pass", {})
print(f"\nlast_gate_pass keys: {list(last_pass.keys())}")
if "tailor_gate" in last_pass:
    tgp = last_pass["tailor_gate"]
    print(f"  tailor_gate: round={tgp.get('round_idx')}, cycle={tgp.get('cycle_id')}")
    print(f"  fingerprint: {tgp.get('input_fingerprint', '')[:32]}...")

# Check gate_cycle_id
gate_cycle = final_state.get("gate_cycle_id", {})
print(f"\ngate_cycle_id: {gate_cycle}")

# Save results
result = {
    "elapsed_s": round(elapsed, 1),
    "fused_verdict": fused,
    "fused_verdict_rationale": rationale,
    "gate_cycles": {k: len(v) for k, v in gate_results.items()},
    "last_entry_per_gate": {
        gn: {"verdict": entries[-1]["verdict"], "generated_by": entries[-1]["generated_by"],
             "round_idx": entries[-1]["round_idx"], "cycle_id": entries[-1].get("cycle_id", 0)}
        for gn, entries in gate_results.items() if entries
    },
    "n_reuse_traces": len(reuse_traces),
    "last_gate_pass": last_pass,
    "gate_cycle_id": gate_cycle,
}

result_path = os.path.join(OUT, "vit_dr_smoke.json")
with open(result_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
print(f"\nResults saved to {result_path}")

# Acceptance criteria
print("\n=== Acceptance Check ===")
if len(reuse_traces) > 0:
    print("PASS: Reused-pass traces found (fingerprint mechanism working)")
else:
    print("INFO: No reused-pass traces (may be due to input changing each cycle)")

if gate_cycle.get("tailor_gate", 0) > 0:
    print(f"PASS: gate_cycle_id[tailor_gate]={gate_cycle['tailor_gate']} (cycle tracking active)")
else:
    print(f"INFO: gate_cycle_id[tailor_gate]=0 (single cycle)")

tg_entries = gate_results.get("tailor_gate", [])
if tg_entries and tg_entries[-1].get("verdict") == "pass":
    print("PASS: tailor_gate final verdict = pass (re-entry no longer causes cap)")
elif tg_entries and tg_entries[-1].get("verdict") == "revise":
    print("INFO: tailor_gate final verdict = revise (legit content issue, not cap)")
elif tg_entries and tg_entries[-1].get("verdict") == "unresolved":
    last = tg_entries[-1]
    rationale = last.get("rationale", "")
    if "cap reached" in rationale:
        print(f"ISSUE: tailor_gate still hitting cap ({rationale}) — need investigation")
    else:
        print(f"INFO: tailor_gate unresolved for content reasons: {rationale[:100]}")
