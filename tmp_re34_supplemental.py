"""Re3.4 supplemental: 4 new topics regression test."""
import json
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv("G:/PaperAgent/.env")

OUT_DIR = Path("G:/PaperAgent/tmp_re34_eval")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CASES = [
    ("R34-S01", "基于多视差一致性的伪深度图误差过滤方法"),
    ("R34-S02", "无人机ZED立体匹配网络训练与评测研究"),
    ("R34-S03", "深度先验引导的无监督立体匹配与视差置信度估计"),
    ("R34-S04", "基于三维点云重建的混凝土结构裂缝定位与追踪"),
]

from apps.api.app.services.agents.graph.research_graph import build_graph
from apps.api.app.services.agents.graph.state import ResearchState

g = build_graph()

for case_id, topic in CASES:
    print(f"\n{'='*80}")
    print(f"  CASE: {case_id}")
    print(f"  TOPIC: {topic}")
    print(f"{'='*80}", flush=True)

    t0 = time.time()
    state_in: ResearchState = {
        "case_id": case_id,
        "topic": topic,
        "user_constraints": {"topic_zh": topic},
        "trace_events": [],
        "provider_profile": "fast_json",
        "errors": [],
    }

    try:
        out = g.invoke(state_in, config={"configurable": {"thread_id": case_id}, "recursion_limit": 100})
        elapsed = round(time.time() - t0, 2)
        out["elapsed_s"] = elapsed

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

        vp = out.get("verified_papers") or []
        dc = out.get("dataset_candidates") or []
        rc = out.get("repo_candidates") or []
        bc = out.get("baseline_candidates") or []
        wp = out.get("work_packages") or []
        final = out.get("final_recommendation") or {}
        feas = out.get("feasibility_report") or {}
        review = out.get("review_report") or {}

        print(f"  elapsed: {elapsed}s")
        print(f"  verified_papers: {len(vp)}")
        print(f"  dataset_candidates: {len(dc)}")
        print(f"  repo_candidates: {len(rc)}")
        print(f"  baseline_candidates: {len(bc)}")
        print(f"  work_packages: {len(wp)}")
        print(f"  feasibility: {feas.get('verdict', '?')} (score={feas.get('score', '?')})")
        print(f"  review: {review.get('overall_verdict', '?')}")
        print(f"  final_rec n_papers={final.get('n_papers', '?')} n_repo={final.get('n_repo', '?')} n_baseline={final.get('n_baseline', '?')}")

    except Exception as exc:
        elapsed = round(time.time() - t0, 2)
        print(f"  ERROR after {elapsed}s: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        cd = OUT_DIR / case_id
        cd.mkdir(parents=True, exist_ok=True)
        (cd / "error.txt").write_text(
            f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}", encoding="utf-8")

    time.sleep(5)

print(f"\n{'='*80}")
print("All 4 cases complete.")
