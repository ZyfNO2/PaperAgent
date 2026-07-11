"""Deep check search trace."""
import json, os

base = "G:/PaperAgent/tmp_re13_eval"
case = "FIX-01"
trace_path = os.path.join(base, case, "trace.json")

with open(trace_path, "r", encoding="utf-8") as f:
    trace = json.load(f)

evs = trace if isinstance(trace, list) else trace.get("trace_events", [])

for e in evs:
    n = e.get("node", "?")
    if n in ("search_agent", "paper_retriever", "search_planner"):
        inp = e.get("input_summary", {})
        out = e.get("output_summary", {})
        tool_calls = out.get("raw_tools", []) or out.get("tool_calls", [])
        per_adapter = out.get("per_adapter", {})
        print(f"\n--- {n} ---")
        print(f"  input: provider={inp.get('provider','?')}")
        print(f"  output: n_papers={out.get('n_paper_candidates','?')} n_repos={out.get('n_repo_candidates','?')}")
        print(f"  per_adapter: {json.dumps(per_adapter, ensure_ascii=False)}")
        print(f"  failed: {out.get('failed_adapters',[])}")
        print(f"  skipped: {out.get('skipped_adapters',[])}")
        print(f"  raw_tools_called: {tool_calls}")
