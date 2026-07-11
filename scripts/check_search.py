"""Check search adapter results from trace."""
import json, os, sys
base = "G:/PaperAgent/tmp_re13_eval"
case = sys.argv[1] if len(sys.argv) > 1 else "FIX-02"
trace_path = os.path.join(base, case, "trace.json")
with open(trace_path, "r", encoding="utf-8") as f:
    trace = json.load(f)
evs = trace if isinstance(trace, list) else trace.get("trace_events", [])
for e in evs:
    n = e.get("node", "?")
    if n in ("search_agent", "paper_retriever", "search_planner"):
        out = e.get("output_summary", {})
        pa = out.get("per_adapter", {})
        raw = out.get("raw_tools", [])
        print(f"[{case}] {n}: n_papers={out.get('n_paper_candidates','?')} per_adapter={json.dumps(pa)} raw_tools={raw}")
    if n == "search_planner":
        out = e.get("output_summary", {})
        print(f"[{case}] {n}: n_queries={out.get('n_queries','?')} rounds={out.get('rounds','?')}")
