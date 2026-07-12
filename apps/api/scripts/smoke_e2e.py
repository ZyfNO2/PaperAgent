"""End-to-end smoke test: run full graph on specified cases.

Usage:
    python smoke_e2e.py XD-02 XD-03           # run 2 cases
    python smoke_e2e.py XD-02 XD-03 XD-04     # run 3 cases
    python smoke_e2e.py                        # default: XD-01
"""
import os, sys, time, json
sys.stdout.reconfigure(line_buffering=True)
ROOT = os.path.abspath(".")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(".env", override=True)

from apps.api.app.services.agents.graph.research_graph import build_graph
from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.app.services.router.register_graph_contracts import register_graph_contracts
from apps.api.app.services.cross_domain_cases import CROSS_DOMAIN_CASES

register_graph_contracts()

# Parse case IDs from command line
case_ids = sys.argv[1:] if len(sys.argv) > 1 else ["XD-01"]
cases = []
for cid in case_ids:
    found = None
    for c in CROSS_DOMAIN_CASES:
        if c.case_id == cid:
            found = c
            break
    if found:
        cases.append(found)
    else:
        print(f"WARNING: {cid} not found in CROSS_DOMAIN_CASES, skipping", flush=True)

print(f"=== Batch run: {len(cases)} cases: {[c.case_id for c in cases]} ===", flush=True)

results = []
for case in cases:
    print(f"\n--- Running: {case.case_id} - {case.topic} ---", flush=True)
    t0 = time.time()

    state_in = {
        "case_id": case.case_id,
        "topic": case.topic,
        "user_constraints": {"topic_zh": case.topic, "domain": case.domain},
        "trace_events": [],
        "provider_profile": "fast_json",
        "errors": [],
    }

    g = build_graph()
    node_timings = []
    last_t = t0
    verdict = ""
    final_state: dict = {}
    all_trace_events: list = []

    try:
        for chunk in g.stream(
            state_in,
            config={"configurable": {"thread_id": case.case_id}, "recursion_limit": 150},
            stream_mode="updates",
        ):
            now = time.time()
            for node_name, patch in chunk.items():
                if not isinstance(patch, dict):
                    continue
                elapsed = round(now - last_t, 2)
                node_timings.append({"node": node_name, "elapsed_s": elapsed})
                last_t = now
                final_state.update(patch)
                # trace_events uses operator.add reducer; accumulate separately
                te = patch.get("trace_events")
                if isinstance(te, list):
                    all_trace_events.extend(te)
                fr = patch.get("final_recommendation", {})
                if isinstance(fr, dict) and fr.get("verdict"):
                    verdict = fr["verdict"]
                print(f"  [{node_name}] {elapsed:.1f}s", flush=True)
    except Exception as exc:
        print(f"  ERROR: {type(exc).__name__}: {exc}", flush=True)
        verdict = f"ERROR:{type(exc).__name__}"

    final_state["trace_events"] = all_trace_events

    # Extract attribution fields from the final graph state
    stop_reason = final_state.get("stop_reason", [])
    if not isinstance(stop_reason, list):
        stop_reason = [str(stop_reason)] if stop_reason else []
    claim_judge_verdict = final_state.get("claim_judge_verdict", "") or ""
    low_bar_status = (final_state.get("low_bar_review") or {}).get("status", "") if isinstance(final_state.get("low_bar_review"), dict) else ""
    human_gate_status = (final_state.get("human_gate") or {}).get("status", "") if isinstance(final_state.get("human_gate"), dict) else ""

    provider_chain = []
    for ev in all_trace_events:
        if isinstance(ev, dict) and ev.get("provider"):
            provider_chain.append({
                "node": ev.get("node", ""),
                "provider": ev.get("provider", ""),
                "model": ev.get("model", ""),
                "contract_id": ev.get("contract_id", ""),
                "elapsed_s": ev.get("elapsed_s"),
            })

    total = time.time() - t0
    result = {
        "case_id": case.case_id,
        "topic": case.topic,
        "domain": case.domain,
        "expected_verdict": case.expected_verdict,
        "actual_verdict": verdict,
        "total_s": round(total, 1),
        "n_nodes": len(node_timings),
        "node_timings": node_timings,
        "stop_reason": stop_reason,
        "claim_judge_verdict": claim_judge_verdict,
        "low_bar_status": low_bar_status,
        "human_gate_status": human_gate_status,
        "provider_chain": provider_chain,
    }
    results.append(result)
    print(f"  => verdict={verdict}, total={total:.1f}s, nodes={len(node_timings)}", flush=True)

# Summary
print(f"\n{'='*60}", flush=True)
print(f"=== BATCH SUMMARY: {len(results)} cases ===", flush=True)
print(f"{'Case':<8} {'Verdict':<12} {'Expected':<14} {'Time':>8} {'Nodes':>6}", flush=True)
print(f"{'-'*8} {'-'*12} {'-'*14} {'-'*8} {'-'*6}", flush=True)
for r in results:
    print(f"{r['case_id']:<8} {r['actual_verdict']:<12} {r['expected_verdict']:<14} {r['total_s']:>7.1f}s {r['n_nodes']:>6}", flush=True)
print(f"{'='*60}", flush=True)

# Save results JSON — include case_ids in filename to avoid concurrent overwrite
case_tag = "_".join(c.case_id for c in cases)
out_path = os.path.join("artifacts", "re7_6", "round0", f"batch_{case_tag}_{int(time.time())}.json")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"Results saved to {out_path}", flush=True)