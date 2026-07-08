"""Re1.3 E2E test — run the full graph with real LLM on 3 topics."""
import json
import time
from pathlib import Path

# Load .env
from dotenv import load_dotenv
load_dotenv("G:/PaperAgent/.env")

OUT_DIR = Path("G:/PaperAgent/tmp_re13_eval")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TOPICS = [
    ("re13-steel-yolov5", "基于YOLOv5的钢材表面缺陷检测研究"),
    ("re13-semantic-slam", "基于深度学习的视觉SLAM语义地图的研究"),
    ("re13-medical-llm", "基于大语言模型的医学问答可信度评估方法研究"),
]

from apps.api.app.services.agents.graph.research_graph import build_graph
from apps.api.app.services.agents.graph.state import ResearchState

g = build_graph()

for case_id, topic_zh in TOPICS:
    print(f"\n{'='*80}")
    print(f"  CASE: {case_id}")
    print(f"  TOPIC: {topic_zh}")
    print(f"{'='*80}")

    t0 = time.time()
    state_in: ResearchState = {
        "case_id": case_id,
        "topic": topic_zh,
        "user_constraints": {"topic_zh": topic_zh},
        "trace_events": [],
        "provider_profile": "fast_json",
        "errors": [],
    }

    try:
        out = g.invoke(state_in, config={"configurable": {"thread_id": case_id}, "recursion_limit": 50})
        elapsed = round(time.time() - t0, 2)
        out["elapsed_s"] = elapsed

        # Save artifacts
        cd = OUT_DIR / case_id
        cd.mkdir(parents=True, exist_ok=True)
        (cd / "state.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        (cd / "trace.json").write_text(
            json.dumps(out.get("trace_events") or [], ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        (cd / "evidence_graph.json").write_text(
            json.dumps(out.get("evidence_graph") or {}, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        # Print summary
        vp = out.get("verified_papers") or []
        fr = out.get("filter_results") or {}
        seeds = out.get("seed_papers") or []
        expanded = out.get("expanded_papers") or []
        surveys = out.get("surveys_found") or []
        repos = out.get("repos_found") or []
        dc = out.get("dataset_candidates") or []
        rc = out.get("repo_candidates") or []
        bc = out.get("baseline_candidates") or []
        wp = out.get("work_packages") or []
        final = out.get("final_recommendation") or {}

        print(f"  elapsed: {elapsed}s")
        print(f"  paper_candidates: {len(out.get('paper_candidates') or [])}")
        print(f"  filter_results: kept={fr.get('kept','?')}, dropped={fr.get('dropped','?')}")
        print(f"  verified_papers: {len(vp)}")
        print(f"  seed_papers: {len(seeds)}")
        print(f"  expanded_papers: {len(expanded)}")
        print(f"  surveys_found: {len(surveys)}")
        print(f"  repos_found: {len(repos)}")
        print(f"  dataset_candidates: {len(dc)}")
        print(f"  repo_candidates: {len(rc)}")
        print(f"  baseline_candidates: {len(bc)}")
        print(f"  work_packages: {len(wp)}")
        print(f"  final_status: {final.get('low_bar_status', 'unknown')}")

        # Print verified paper titles
        if vp:
            print(f"\n  --- verified_papers ({len(vp)}) ---")
            for i, p in enumerate(vp[:20]):
                title = (p.get("title") or "")[:80]
                verdict = p.get("verdict", "")
                rel = p.get("relation_to_topic", "")
                print(f"    [{i:2d}] [{verdict:12s}] [{rel:10s}] {title}")
            if len(vp) > 20:
                print(f"    ... and {len(vp)-20} more")

        # Print seed papers
        if seeds:
            print(f"\n  --- seed_papers ({len(seeds)}) ---")
            for s in seeds:
                title = (s.get("title") or "")[:70]
                score = s.get("relevance_score", 0)
                reason = s.get("seed_selection_reason", "")
                print(f"    [score={score:3d}] {title} ({reason})")

        # Print expanded papers sample
        if expanded:
            print(f"\n  --- expanded_papers ({len(expanded)} total, showing first 10) ---")
            for p in expanded[:10]:
                title = (p.get("title") or "")[:70]
                seed = (p.get("expanded_from_seed") or "")[:40]
                print(f"    {title}")
                print(f"      from: {seed}")

        # Print surveys
        if surveys:
            print(f"\n  --- surveys_found ({len(surveys)}) ---")
            for s in surveys:
                print(f"    {s.get('title','')[:70]}")

        # Print repos
        if repos:
            print(f"\n  --- repos_found ({len(repos)}) ---")
            for r in repos:
                print(f"    {r.get('url','')[:70]}")

        # Print trace summary
        traces = out.get("trace_events") or []
        print(f"\n  --- trace ({len(traces)} events) ---")
        for t in traces:
            node = t.get("node", "")
            elapsed_t = t.get("elapsed_s", 0)
            out_s = t.get("output_summary", {})
            print(f"    {node:30s} {elapsed_t:8.1f}s  {out_s}")

    except Exception as exc:
        elapsed = round(time.time() - t0, 2)
        print(f"  ERROR after {elapsed}s: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()

        # Save partial state
        cd = OUT_DIR / case_id
        cd.mkdir(parents=True, exist_ok=True)
        (cd / "error.txt").write_text(f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}", encoding="utf-8")

print(f"\n{'='*80}")
print("All cases complete.")
