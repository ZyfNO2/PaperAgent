"""Quick trace check."""
import json
tr = json.load(open("tmp_re13_eval/re5x-fix/trace.json", encoding="utf-8"))
print(f"events: {len(tr)}")
for e in tr:
    node = e.get("node","?")
    t = e.get("elapsed_s",0)
    prov = e.get("provider","")
    errs = e.get("errors",[])
    out = e.get("output_summary",{})
    line = f"  {node}  {t:.1f}s  prov={prov}"
    if errs:
        line += f"  ERRORS={errs}"
    if out:
        for k in ("verdict","score","overall_verdict","n_papers","n_packages","status","route","n_innovation"):
            if k in out:
                line += f"  {k}={out[k]}"
    print(line)
