"""Debug: run the graph directly (not via server) to see adapter results."""
import json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv("G:/PaperAgent/.env", override=True)

from apps.api.app.services.agents.graph import research_graph as rg

CASE_ID = "re24-debug-direct"
TOPIC = "基于深度学习的医学图像分割研究"

state_in = {
    "case_id": CASE_ID,
    "topic": TOPIC,
    "user_constraints": {"topic_zh": TOPIC},
    "trace_events": [],
    "provider_profile": "fast_json",
    "errors": [],
}

g = rg.build_graph()
out = g.invoke(state_in, config={"configurable": {"thread_id": CASE_ID}, "recursion_limit": 100})

raw = out.get("raw_results", {})
vp = out.get("verified_papers") or []
wp = out.get("weak_papers") or []
ep = out.get("expanded_papers") or []

print(f"raw: { {k: len(v) for k, v in raw.items() if isinstance(v, list)} }")
print(f"verified: {len(vp)}, weak: {len(wp)}, expanded: {len(ep)}")

# Save state
cd = Path(f"tmp_re13_eval/{CASE_ID}")
cd.mkdir(parents=True, exist_ok=True)
(cd / "state.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str),
    encoding="utf-8",
)

# Print trace
for t in out.get("trace_events") or []:
    node = t.get("node", "?")
    out_s = t.get("output_summary", {})
    print(f"  {node:30s} {out_s}")
