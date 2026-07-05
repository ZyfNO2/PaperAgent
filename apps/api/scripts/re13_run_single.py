"""Run a single Re1.3 E2E case to collect real data."""
import json
import os
import sys
import time
from pathlib import Path

# Ensure .env is loaded
from dotenv import load_dotenv
load_dotenv()

# Force StepFun as primary
os.environ["FAST_JSON_PRIMARY"] = "stepfun"
os.environ["STEPFUN_RPM_LIMIT"] = "10"
os.environ["VERIFIER_MAX_WORKERS"] = "1"

from apps.api.app.services.agents.graph import research_graph as rg
from apps.api.app.services.agents.graph.state import ResearchState

case_id = "re13-steel-yolov5"
topic = "YOLOv5-based steel surface defect detection on hot-rolled strip using NEU-DET dataset"

print(f"=== Re1.3 E2E: {case_id} ===")
print(f"topic: {topic}")
print(f"provider: stepfun (RPM=10, max_workers=1)")
print()

state_in: ResearchState = {
    "case_id": case_id,
    "topic": topic,
    "user_constraints": {"topic_zh": "基于YOLOv5的钢材表面缺陷检测研究"},
    "trace_events": [],
    "provider_profile": "fast_json",
    "errors": [],
}

t0 = time.time()
g = rg.build_graph()
out = g.invoke(state_in, config={"configurable": {"thread_id": case_id}})
elapsed = round(time.time() - t0, 2)

print(f"\n=== COMPLETE: {elapsed}s ===")
print()

# Save state
out_dir = Path(f"tmp_re13_eval/{case_id}")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "state.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str),
    encoding="utf-8",
)
(out_dir / "trace.json").write_text(
    json.dumps(out.get("trace_events") or [], ensure_ascii=False, indent=2, default=str),
    encoding="utf-8",
)
(out_dir / "evidence_graph.json").write_text(
    json.dumps(out.get("evidence_graph") or {}, ensure_ascii=False, indent=2, default=str),
    encoding="utf-8",
)

# Print summary
print("=== SUMMARY ===")
pc = out.get("paper_candidates") or []
vp = out.get("verified_papers") or []
fr = out.get("filter_results") or {}
sp = out.get("seed_papers") or []
ep = out.get("expanded_papers") or []
sf = out.get("surveys_found") or []
rf = out.get("repos_found") or []
dc = out.get("dataset_candidates") or []
rc = out.get("repo_candidates") or []
bc = out.get("baseline_candidates") or []
wp = out.get("work_packages") or []

print(f"  paper_candidates: {len(pc)}")
print(f"  filter_results: kept={fr.get('kept',0)}, dropped={fr.get('dropped',0)}")
print(f"  verified_papers: {len(vp)}")
print(f"  seed_papers: {len(sp)}")
print(f"  expanded_papers: {len(ep)}")
print(f"  surveys_found: {len(sf)}")
print(f"  repos_found: {len(rf)}")
print(f"  dataset_candidates: {len(dc)}")
print(f"  repo_candidates: {len(rc)}")
print(f"  baseline_candidates: {len(bc)}")
print(f"  work_packages: {len(wp)}")
print(f"  elapsed: {elapsed}s")

# Print verified papers
if vp:
    print("\n=== VERIFIED PAPERS ===")
    for p in vp:
        title = (p.get("title") or "")[:80]
        verdict = p.get("verdict", "")
        rel = p.get("relation_to_topic", "")
        hits = ", ".join((p.get("hit_keywords") or [])[:5])
        print(f"  [{verdict:12s}] [{rel:10s}] {title}")
        print(f"    hit: {hits}")

# Print filter results
if fr.get("dropped_items"):
    print("\n=== FILTERED OUT (quality_filter) ===")
    for d in fr["dropped_items"]:
        print(f"  DROPPED: {d.get('title','')[:70]} | reason: {d.get('reason','')}")

# Print seeds
if sp:
    print("\n=== SEED PAPERS (auto-selected) ===")
    for s in sp:
        print(f"  score={s.get('relevance_score',0):3d} | {s.get('title','')[:70]}")
        print(f"    reason: {s.get('seed_selection_reason','')}")

# Print expanded papers
if ep:
    print(f"\n=== EXPANDED PAPERS ({len(ep)} total) ===")
    for p in ep[:10]:
        title = (p.get("title") or "")[:70]
        seed = p.get("expanded_from_seed", "")[:40]
        print(f"  {title}")
        print(f"    from: {seed}")
    if len(ep) > 10:
        print(f"  ... and {len(ep)-10} more")

# Print trace summary
traces = out.get("trace_events") or []
print("\n=== TRACE ===")
for t in traces:
    node = t.get("node", "")
    elapsed_t = t.get("elapsed_s", 0)
    out_sum = t.get("output_summary", {})
    print(f"  {node:30s} {elapsed_t:8.1f}s  {out_sum}")
