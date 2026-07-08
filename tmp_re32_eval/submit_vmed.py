"""Submit V-MED case via Python httpx to avoid PowerShell encoding issues."""
import httpx, json, time

# Submit the case
body = {
    "case_id": "V-MED-32k",
    "topic": "基于大语言模型的医学问答可信度评估方法研究",
    "target_tier": "SCI-Q2",
}
r = httpx.post("http://127.0.0.1:18181/api/v1/research/", json=body, timeout=10)
print(f"Submit: {r.json()}")

# Poll for completion
for i in range(30):
    time.sleep(10)
    s = httpx.get("http://127.0.0.1:18181/api/v1/research/V-MED-32k/status", timeout=5)
    status = s.json().get("status", "")
    print(f"  poll {i+1}: {status}")
    if status == "done":
        break

# Get state
r = httpx.get("http://127.0.0.1:18181/api/v1/research/V-MED-32k/state", timeout=10)
state = r.json()
atoms = state.get("topic_atoms", {})
method = atoms.get("method", [])
task = atoms.get("task", [])
domain = atoms.get("domain")
vp = state.get("verified_papers", [])
rc = state.get("repo_candidates", [])
dc = state.get("dataset_candidates", [])
ss = state.get("search_steps", [])
rn = state.get("research_narrative", {})
rv = state.get("review_report", {})
fe = state.get("feasibility_report", {})

with open("tmp_re32_eval/V-MED-32k_check.txt", "w", encoding="utf-8") as f:
    f.write(f"method: {method}\n")
    f.write(f"task: {task}\n")
    f.write(f"domain: {domain}\n")
    f.write(f"verified_papers: {len(vp)}\n")
    f.write(f"repo_candidates: {len(rc)}\n")
    f.write(f"dataset_candidates: {len(dc)}\n")
    f.write(f"search_steps: {len(ss)}\n")
    for s in ss:
        f.write(f"  step={s.get('step')} tool={s.get('tool')} query={s.get('query')} results={s.get('n_results')}\n")
    f.write(f"review verdict: {rv.get('overall_verdict', '')}\n")
    f.write(f"feasibility: {fe.get('verdict', '')} score={fe.get('score', '')}\n")
    f.write(f"narrative keys: {list(rn.keys()) if isinstance(rn, dict) else 'empty'}\n")
    f.write(f"\nVerified paper titles:\n")
    for p in vp:
        f.write(f"  - {p.get('title', '')}\n")
print("done - check tmp_re32_eval/V-MED-32k_check.txt")
