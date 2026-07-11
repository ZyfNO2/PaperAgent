# -*- coding: utf-8 -*-
"""Re3.8/Re3.9 Final audit: check every case for data quality issues."""
import io
import json
import os
import re
import sys
from collections import Counter

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

EVAL_DIRS = ["tmp_re34_eval", "tmp_re35_eval", "tmp_re36_eval", "tmp_re38_eval"]

def find_state(case_id):
    for d in EVAL_DIRS:
        p = os.path.join(d, case_id, "state.json")
        if os.path.exists(p):
            return p, d
    return None, None

def has_chinese(s):
    if not s:
        return False
    return bool(re.search(r'[\u4e00-\u9fff]', s))

def audit_case(case_id, sp, eval_dir):
    s = json.load(open(sp, encoding="utf-8"))
    tp = sp.replace("state.json", "trace.json")
    trace = json.load(open(tp, encoding="utf-8")) if os.path.exists(tp) else []

    issues = []
    warnings = []

    _topic = s.get("topic", "")
    vp = s.get("verified_papers") or []
    _wp = s.get("weak_papers") or []
    rc = s.get("repo_candidates") or []
    dc = s.get("dataset_candidates") or []
    bc = s.get("baseline_candidates") or []
    pc = s.get("parallel_candidates") or []
    fr = s.get("final_recommendation") or {}
    feas = s.get("feasibility_report") or {}
    review = s.get("review_report") or {}
    atoms = s.get("topic_atoms") or {}
    inn = s.get("innovation_points") or []
    plan = s.get("stitching_plan") or {}
    narrative = s.get("research_narratives") or {}
    search_steps = s.get("search_steps") or []

    # 1. Critical: verified_papers count
    if len(vp) == 0:
        issues.append("vp=0 (no verified papers)")
    elif len(vp) < 3:
        issues.append(f"vp={len(vp)}<3 (too few papers)")

    # 2. final_rec mismatch
    fr_np = fr.get("n_papers", -1)
    if fr_np != len(vp):
        issues.append(f"fr.n_papers={fr_np}!=vp={len(vp)}")
    if fr_np == 0:
        issues.append("fr.n_papers=0")

    # 3. RecursionError
    has_recursion = any("RecursionError" in str(ev) for ev in trace)
    if has_recursion:
        issues.append("RecursionError in trace")

    # 4. state_keys coverage
    sk_count = sum(1 for ev in trace if ev.get("state_keys"))
    sk_total = len(trace)
    if sk_total > 0 and sk_count / sk_total < 0.8:
        issues.append(f"state_keys={sk_count}/{sk_total} ({sk_count/sk_total*100:.0f}%)")

    # 5. topic_atoms has Chinese keywords (should be English after Re3.8/3.9 fix)
    method = atoms.get("method") or []
    obj = atoms.get("object") or []
    task = atoms.get("task") or []
    cn_in_atoms = False
    for kw in method + obj + task:
        if has_chinese(str(kw)):
            cn_in_atoms = True
            break
    if cn_in_atoms:
        issues.append(f"Chinese in topic_atoms: method={method} object={obj} task={task}")

    # 6. feasibility verdict
    feas_v = feas.get("verdict", "?")
    feas_s = feas.get("score", "?")
    if feas_v not in ("feasible", "risky", "not_recommended"):
        issues.append(f"feas_verdict={feas_v} (unknown)")

    # 7. review verdict
    review_v = review.get("overall_verdict", "?")
    if review_v not in ("ACCEPT", "MINOR_REVISION", "BLOCK"):
        issues.append(f"review_verdict={review_v} (unknown)")

    # 8. Duplicate verified papers (same title)
    titles = [t.get("title", "").strip().lower() for t in vp]
    dup_titles = [t for t, c in Counter(titles).items() if c > 1 and t]
    if dup_titles:
        warnings.append(f"{len(dup_titles)} duplicate paper titles")

    # 9. Empty title papers
    empty_titles = sum(1 for t in vp if not t.get("title", "").strip())
    if empty_titles > 0:
        warnings.append(f"{empty_titles} papers with empty title")

    # 10. dataset source check
    ds_sources = Counter(d.get("source", "unknown") for d in dc)
    # Check for old source labels
    old_sources = [s for s in ds_sources if s in ("paper_abstract", "innovation_plan_heuristic", "paper_title_heuristic")]
    if old_sources:
        warnings.append(f"old source labels: {old_sources}")

    # 11. innovation points empty description
    empty_inn = sum(1 for i in inn if not i.get("description", "").strip())
    if empty_inn > 0 and len(inn) > 0:
        warnings.append(f"{empty_inn}/{len(inn)} innovation points with empty description")

    # 12. narrative empty
    if not narrative.get("narrative_summary") and not narrative.get("summary"):
        if not narrative:
            warnings.append("research_narrative empty")
        else:
            warnings.append("research_narratives has no summary text")

    # 13. stitching plan empty
    if not plan.get("baseline_model"):
        warnings.append("stitching_plan has no baseline_model")

    # 14. baseline vs parallel ratio
    if len(bc) > 0 and len(pc) > 0:
        ratio = len(bc) / (len(bc) + len(pc))
        if ratio > 0.95:
            warnings.append(f"baseline ratio={ratio:.0%} (almost all baselines)")
        elif ratio < 0.05:
            warnings.append(f"baseline ratio={ratio:.0%} (almost all parallel)")

    # 15. search_steps duplicate queries
    tool_queries = [(s.get("tool"), s.get("query")) for s in search_steps if s.get("type") == "tool_call"]
    dup_queries = [tq for tq, c in Counter(tool_queries).items() if c > 1 and tq[0] and tq[1]]
    if dup_queries:
        max_dup = max(Counter(tool_queries).values())
        if max_dup >= 3:
            warnings.append(f"search_steps: {len(dup_queries)} duplicate queries, max_repeat={max_dup}")

    # 16. feasibility score range
    if isinstance(feas_s, (int, float)):
        if feas_s < 0 or feas_s > 100:
            issues.append(f"feas_score={feas_s} out of range [0,100]")

    # 17. verified paper with no URL
    no_url = sum(1 for t in vp if not (t.get("url") or "").strip())
    if no_url > 0:
        warnings.append(f"{no_url}/{len(vp)} verified papers without URL")

    # 18. heuristic fallback nodes
    heuristic_nodes = [ev.get("node", "?") for ev in trace if ev.get("provider") == "heuristic"]
    if heuristic_nodes:
        warnings.append(f"heuristic nodes: {heuristic_nodes}")

    return {
        "issues": issues,
        "warnings": warnings,
        "vp": len(vp),
        "rc": len(rc),
        "dc": len(dc),
        "bc": len(bc),
        "pc": len(pc),
        "feas": f"{feas_v}({feas_s})",
        "review": review_v,
        "domain": atoms.get("domain", "?"),
        "sk": f"{sk_count}/{sk_total}",
        "elapsed": s.get("elapsed_s", "?"),
    }

# Run audit
all_cases = []
for d in EVAL_DIRS:
    if not os.path.exists(d):
        continue
    for case_dir in sorted(os.listdir(d)):
        sp = os.path.join(d, case_dir, "state.json")
        if os.path.exists(sp):
            all_cases.append((case_dir, sp, d))

print("=" * 120)
print("Re3.8/Re3.9 Final Audit — Per-Case Data Quality Check")
print("=" * 120)

total_issues = 0
total_warnings = 0
case_results = []

for case_id, sp, eval_dir in all_cases:
    r = audit_case(case_id, sp, eval_dir)
    case_results.append((case_id, r))
    total_issues += len(r["issues"])
    total_warnings += len(r["warnings"])

# Print issues first
print("\n--- ISSUES (P0) ---\n")
for case_id, r in case_results:
    if r["issues"]:
        print(f"❌ {case_id} ({r['domain']}): {len(r['issues'])} issues")
        for iss in r["issues"]:
            print(f"   ! {iss}")

print("\n--- WARNINGS (P1) ---\n")
for case_id, r in case_results:
    if r["warnings"]:
        print(f"⚠ {case_id}: {len(r['warnings'])} warnings")
        for w in r["warnings"]:
            print(f"   ~ {w}")

# Summary table
print(f"\n{'='*120}")
print("SUMMARY TABLE")
print(f"{'='*120}")
print(f"{'Case':15s} {'VP':>4s} {'RC':>4s} {'DC':>4s} {'BC':>4s} {'PC':>4s} {'Feas':>15s} {'Review':>15s} {'SK':>8s} {'Issues':>6s} {'Warns':>6s} Domain")
print("-" * 120)
for case_id, r in case_results:
    status = "❌" if r["issues"] else ("⚠" if r["warnings"] else "✅")
    print(f"{status} {case_id:13s} {r['vp']:4d} {r['rc']:4d} {r['dc']:4d} {r['bc']:4d} {r['pc']:4d} {r['feas']:>15s} {r['review']:>15s} {r['sk']:>8s} {len(r['issues']):6d} {len(r['warnings']):6d} {r['domain']}")

# Statistics
print(f"\n{'='*120}")
print("STATISTICS")
print(f"{'='*120}")
print(f"Total cases: {len(all_cases)}")
print(f"Cases with issues: {sum(1 for _, r in case_results if r['issues'])}")
print(f"Cases with warnings: {sum(1 for _, r in case_results if r['warnings'])}")
print(f"Clean cases (no issues, no warnings): {sum(1 for _, r in case_results if not r['issues'] and not r['warnings'])}")
print(f"Total issues: {total_issues}")
print(f"Total warnings: {total_warnings}")

# Feasibility distribution
feas_scores = []
feas_verdicts = Counter()
review_verdicts = Counter()
domains = Counter()
for _, r in case_results:
    parts = r["feas"].split("(")
    feas_verdicts[parts[0]] += 1
    if len(parts) > 1:
        score = parts[1].rstrip(")")
        try:
            feas_scores.append(int(score))
        except ValueError:
            pass
    review_verdicts[r["review"]] += 1
    domains[r["domain"]] += 1

print(f"\nFeasibility verdicts: {dict(feas_verdicts)}")
print(f"Review verdicts: {dict(review_verdicts)}")
print(f"Domains: {dict(domains)}")
if feas_scores:
    print(f"Feasibility scores: {sorted(feas_scores)} ({len(set(feas_scores))} unique)")
    print(f"  min={min(feas_scores)} max={max(feas_scores)} mean={sum(feas_scores)/len(feas_scores):.1f}")
