"""Extract Re1.3 E2E results for display."""
import json, sys

case = sys.argv[1] if len(sys.argv) > 1 else "re13-steel-yolov5"
path = f"tmp_re13_eval/{case}/state.json"

with open(path, encoding="utf-8") as f:
    st = json.load(f)

topic = st.get("topic", "")
print(f"topic: {topic}")
print(f"elapsed_s: {st.get('elapsed_s', '?')}")
print()

pc = st.get("paper_candidates") or []
vp = st.get("verified_papers") or []
fr = st.get("filter_results") or {}
seeds = st.get("seed_papers") or []
expanded = st.get("expanded_papers") or []
surveys = st.get("surveys_found") or []
repos = st.get("repos_found") or []
dc = st.get("dataset_candidates") or []
rc = st.get("repo_candidates") or []
bc = st.get("baseline_candidates") or []
pc_cands = st.get("parallel_candidates") or []
wp = st.get("work_packages") or []
final = st.get("final_recommendation") or {}

print(f"paper_candidates: {len(pc)}")
print(f"filter_results: kept={fr.get('kept','?')}, dropped={fr.get('dropped','?')}")
if fr.get("dropped_items"):
    print("  dropped samples:")
    for d in fr["dropped_items"][:8]:
        t = d.get("title", "")[:60]
        r = d.get("reason", "")[:60]
        print(f"    - {t} | reason: {r}")
print(f"verified_papers: {len(vp)}")
print(f"seed_papers: {len(seeds)}")
print(f"expanded_papers: {len(expanded)}")
print(f"surveys_found: {len(surveys)}")
print(f"repos_found: {len(repos)}")
print(f"dataset_candidates: {len(dc)}")
print(f"repo_candidates: {len(rc)}")
print(f"baseline_candidates: {len(bc)}")
print(f"parallel_candidates: {len(pc_cands)}")
print(f"work_packages: {len(wp)}")
print(f"final_status: {final.get('low_bar_status', 'unknown')}")
print()

if vp:
    print("=== verified_papers ===")
    for i, p in enumerate(vp[:25]):
        title = (p.get("title") or "")[:70]
        verdict = p.get("verdict", "")
        rel = p.get("relation_to_topic", "")
        hits = (p.get("hit_keywords") or [])[:3]
        print(f"  [{i:2d}] [{verdict:12s}] [{rel:10s}] {title}")
        print(f"        hit: {hits}")
    if len(vp) > 25:
        print(f"  ... and {len(vp)-25} more")

if seeds:
    print()
    print("=== seed_papers ===")
    for s in seeds:
        title = (s.get("title") or "")[:70]
        score = s.get("relevance_score", 0)
        reason = s.get("seed_selection_reason", "")
        print(f"  [score={score:3d}] {title}")
        print(f"    reason: {reason}")

if expanded:
    print()
    print(f"=== expanded_papers ({len(expanded)} total, first 15) ===")
    for p in expanded[:15]:
        title = (p.get("title") or "")[:70]
        seed = (p.get("expanded_from_seed") or "")[:40]
        pid = p.get("paper_id") or p.get("doi") or ""
        print(f"  {title}")
        print(f"    from: {seed} | id: {pid}")

if surveys:
    print()
    print("=== surveys_found ===")
    for s in surveys:
        print(f"  {s.get('title','')[:70]}")

if repos:
    print()
    print("=== repos_found ===")
    for r in repos:
        print(f"  {r.get('url','')[:70]}")

if bc:
    print()
    print(f"=== baseline_candidates ({len(bc)}) ===")
    for b in bc[:10]:
        print(f"  {(b.get('title') or '')[:70]}")

if dc:
    print()
    print(f"=== dataset_candidates ({len(dc)}) ===")
    for d in dc[:5]:
        name = (d.get("name") or d.get("title") or "")[:70]
        url = d.get("url", "")[:60]
        print(f"  {name} | {url}")

if rc:
    print()
    print(f"=== repo_candidates ({len(rc)}) ===")
    for r in rc[:5]:
        name = (r.get("name") or r.get("title") or "")[:70]
        url = r.get("url", "")[:60]
        print(f"  {name} | {url}")

if wp:
    print()
    print(f"=== work_packages ({len(wp)}) ===")
    for w in wp[:3]:
        title = (w.get("title") or w.get("name") or "")[:70]
        desc = (w.get("description") or w.get("summary") or "")[:120]
        print(f"  {title}")
        if desc:
            print(f"    {desc}")

print()
traces = st.get("trace_events") or []
print(f"=== trace ({len(traces)} events) ===")
for t in traces:
    node = t.get("node", "")
    el = t.get("elapsed_s", 0)
    out = t.get("output_summary", {})
    errs = t.get("errors", [])
    print(f"  {node:30s} {el:8.1f}s  {out}  errors={len(errs)}")
