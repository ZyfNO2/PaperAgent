"""Re3.9.1 Phase 2: Verify PubMed injection — 1 medical + 1 non-medical case."""
import json
import time
import traceback
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("G:/PaperAgent/.env")

from apps.api.app.services.agents.graph.research_graph import build_graph  # noqa: E402
from apps.api.app.services.agents.graph.state import ResearchState  # noqa: E402

OUT_DIR = Path("G:/PaperAgent/tmp_re39_eval")

CASES = [
    ("R39-LUNG", "基于YOLOV5的肺结节检测算法研究"),
    ("R39-CRACK", "基于深度学习的混凝土桥梁裂缝检测研究"),
]

g = build_graph()

for case_id, topic in CASES:
    if (OUT_DIR / case_id / "state.json").exists():
        print(f"\n  SKIP {case_id} (already done)")
        continue

    print(f"\n{'='*80}")
    print(f"  CASE: {case_id} | TOPIC: {topic}")
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
        (cd / "state.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        (cd / "trace.json").write_text(json.dumps(out.get("trace_events") or [], ensure_ascii=False, indent=2, default=str), encoding="utf-8")

        vp = out.get("verified_papers") or []
        rc = out.get("repo_candidates") or []
        dc = out.get("dataset_candidates") or []
        bc = out.get("baseline_candidates") or []
        feas = out.get("feasibility_report") or {}
        review = out.get("review_report") or {}
        atoms = out.get("topic_atoms") or {}
        ss = out.get("search_steps") or []

        tools_used = [s.get("tool", "") for s in ss if s.get("type") == "tool_call"]
        pubmed_steps = [s for s in ss if s.get("tool") == "pubmed"]

        print(f"  elapsed={elapsed}s vp={len(vp)} rc={len(rc)} dc={len(dc)} bc={len(bc)}")
        print(f"  feas={feas.get('verdict', '?')}({feas.get('score', '?')}) review={review.get('overall_verdict', '?')}")
        print(f"  atoms: method={atoms.get('method', [])} domain={atoms.get('domain', '?')}")
        print(f"  tools_used: {tools_used}")
        print(f"  pubmed_steps: {len(pubmed_steps)}")

        if case_id == "R39-LUNG":
            assert len(pubmed_steps) >= 1, "PubMed should be called for medical topic!"
            print(f"  ✅ PubMed called {len(pubmed_steps)} time(s)")
        else:
            assert len(pubmed_steps) == 0, "PubMed should NOT be called for non-medical topic!"
            print("  ✅ PubMed not called (correct for non-medical)")

    except Exception as exc:
        elapsed = round(time.time() - t0, 2)
        print(f"  ERROR after {elapsed}s: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        cd = OUT_DIR / case_id
        cd.mkdir(parents=True, exist_ok=True)
        (cd / "error.txt").write_text(f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}", encoding="utf-8")

    time.sleep(10)

print("\nDone.")
