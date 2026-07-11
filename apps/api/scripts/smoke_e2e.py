"""End-to-end smoke test: run full graph on one case."""
import os, sys, time, json
sys.stdout.reconfigure(line_buffering=True)  # ensure real-time output
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

# Find XD-09 (STOP case)
case = None
for c in CROSS_DOMAIN_CASES:
    if c.case_id == "XD-09":
        case = c
        break
if not case:
    case = CROSS_DOMAIN_CASES[8]  # fallback to index 8
print(f"Running: {case.case_id} - {case.topic}", flush=True)
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
        fr = patch.get("final_recommendation", {})
        verdict = fr.get("verdict", "") if isinstance(fr, dict) else ""
        artifact = patch.get("artifact_id", "")
        print(f"  [{node_name}] {elapsed:.1f}s verdict={verdict} artifact={artifact}", flush=True)

total = time.time() - t0
print(f"\nTotal: {total:.1f}s", flush=True)
print("Node timings:", flush=True)
for nt in node_timings:
    print(f"  {nt['node']}: {nt['elapsed_s']}s", flush=True)