"""Re3.8 50-paper regression verification."""
import json
import os

ALL_CASES = [
    # Re3.x early (3)
    "V-YOLO-33", "V-SLAM-33", "V-MED-33",
    # Re3.4 (6)
    "R34-002", "R34-033", "R34-038", "R34-046", "R34-066", "R34-092",
    # Re3.5 (2)
    "R35-033", "R35-046",
    # Re3.6 (5)
    "R36-003", "R36-007", "R36-015", "R36-021", "R36-052",
    # Re3.8 Phase 3 (7)
    "R36-060", "R36-074", "R36-079", "R36-084", "R36-091", "R36-094", "R36-100",
    # Re3.8 Phase 5 (27)
    "R38-005", "R38-008", "R38-011", "R38-023",
    "R38-014", "R38-075", "R38-076", "R38-083",
    "R38-047", "R38-050", "R38-067",
    "R38-026", "R38-040", "R38-095", "R38-098",
    "R38-037", "R38-043", "R38-027",
    "R38-006", "R38-009", "R38-018",
    "R38-004", "R38-013", "R38-029", "R38-034",
    "R38-049", "R38-057", "R38-096",
]

EVAL_DIRS = ["tmp_re13_eval", "tmp_re34_eval", "tmp_re35_eval", "tmp_re36_eval", "tmp_re38_eval"]

def find_state(case_id):
    for d in EVAL_DIRS:
        p = os.path.join(d, case_id, "state.json")
        if os.path.exists(p):
            return p
    return None

results = []
all_feas_scores = []
all_feas_verdicts = []
all_review_verdicts = []
all_domains = {}

for case_id in ALL_CASES:
    sp = find_state(case_id)
    if not sp:
        results.append((case_id, "SKIP", "no state.json", {}))
        continue
    d = json.load(open(sp, encoding="utf-8"))
    vp = len(d.get("verified_papers", []))
    rc = len(d.get("repo_candidates", []))
    bc = len(d.get("baseline_candidates") or [])
    pc = len(d.get("parallel_candidates") or [])
    dc = len(d.get("dataset_candidates") or [])
    fr = d.get("final_recommendation", {})
    feas = d.get("feasibility_report", {})
    review = d.get("review_report", {})
    atoms = d.get("topic_atoms") or {}
    domain = atoms.get("domain", "unknown")

    tp = sp.replace("state.json", "trace.json")
    trace = json.load(open(tp, encoding="utf-8")) if os.path.exists(tp) else []
    has_recursion = any("RecursionError" in str(ev) for ev in trace)
    sk_count = sum(1 for ev in trace if ev.get("state_keys"))
    sk_total = len(trace)

    feas_v = feas.get("verdict", "?")
    feas_s = feas.get("score", "?")
    review_v = review.get("overall_verdict", "?")
    all_feas_scores.append(feas_s)
    all_feas_verdicts.append(feas_v)
    all_review_verdicts.append(review_v)
    all_domains[domain] = all_domains.get(domain, 0) + 1

    issues = []
    if vp < 3:
        issues.append(f"vp={vp}<3")
    if fr.get("n_papers", 0) != vp:
        issues.append(f"fr_mismatch={fr.get('n_papers')}!={vp}")
    if fr.get("n_papers", 0) == 0:
        issues.append("fr=0")
    if has_recursion:
        issues.append("RecursionError")

    status = "FAIL" if issues else "PASS"
    info = {"vp": vp, "rc": rc, "bc": bc, "pc": pc, "dc": dc,
            "feas": feas_v, "score": feas_s, "review": review_v,
            "domain": domain, "sk": f"{sk_count}/{sk_total}"}
    results.append((case_id, status, "; ".join(issues) if issues else "OK", info))

print("=" * 120)
print("Re3.8 50-Paper Regression Results")
print("=" * 120)
for case_id, status, detail, info in results:
    if info:
        print(f"{case_id:15s}: {status:4s} | vp={info['vp']:3d} rc={info['rc']:2d} dc={info['dc']:2d} "
              f"bc={info['bc']:2d} pc={info['pc']:2d} | feas={info['feas']}({info['score']}) "
              f"review={info['review']} | sk={info['sk']} dom={info['domain']}")
    else:
        print(f"{case_id:15s}: {status:4s} | {detail}")

n_pass = sum(1 for _, s, _, _ in results if s == "PASS")
n_fail = sum(1 for _, s, _, _ in results if s == "FAIL")
n_skip = sum(1 for _, s, _, _ in results if s == "SKIP")
n_done = n_pass + n_fail

print(f"\n{'='*120}")
print(f"TOTAL: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP out of {len(results)} ({n_done} completed)")
if n_done > 0:
    print(f"PASS rate: {n_pass/n_done*100:.1f}%")
print(f"Feasibility verdicts: {set(all_feas_verdicts)} ({len(set(all_feas_verdicts))} unique)")
print(f"Review verdicts: {set(all_review_verdicts)} ({len(set(all_review_verdicts))} unique)")
print(f"Feasibility scores: {sorted(all_feas_scores)} ({len(set(all_feas_scores))} unique)")
print(f"Domains: {all_domains}")
