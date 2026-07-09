import json, os
p = "tmp_re13_eval/R39-CONS"
tp = os.path.join(p, "trace.json")
sp = os.path.join(p, "state_partial.json")
t = json.load(open(tp, encoding="utf-8")) if os.path.exists(tp) else []
pp = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {}
print(f"trace={len(t)} partial_papers={len(pp.get('paper_candidates', []))}")
print("nodes:", [e.get("node", "?") for e in t])
