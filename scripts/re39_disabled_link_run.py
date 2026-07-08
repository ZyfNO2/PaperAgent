"""Re3.9 Phase 5: Run 2 cases with S2+OpenAlex disabled via env vars."""
import json
import os
import time
import traceback
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("G:/PaperAgent/.env")

# Disable S2 + OpenAlex BEFORE importing graph
os.environ["PAPERAGENT_DISABLE_S2"] = "1"
os.environ["PAPERAGENT_DISABLE_OPENALEX"] = "1"

from apps.api.app.services.agents.graph.research_graph import build_graph  # noqa: E402
from apps.api.app.services.agents.graph.state import ResearchState  # noqa: E402

OUT_DIR = Path("G:/PaperAgent/tmp_re39_eval")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CASES = [
    ("R39-MED", "基于YOLOV5的肺结节检测算法研究"),
    ("R39-066", "面向自动驾驶中多模态融合感知算法的攻击和防御"),
]

g = build_graph()

for case_id, topic in CASES:
    if (OUT_DIR / case_id / "state.json").exists():
        print(f"\n  SKIP {case_id} (already has state.json)")
        continue

    print(f"\n{'='*80}")
    print(f"  CASE: {case_id} | TOPIC: {topic}")
    print(f"  S2 DISABLED={os.environ.get('PAPERAGENT_DISABLE_S2')}")
    print(f"  OPENALEX DISABLED={os.environ.get('PAPERAGENT_DISABLE_OPENALEX')}")
    print(f"{'='*80}", flush=True)

    t0 = time.time()
    state_in: ResearchState = {
        "case_id": case_id, "topic": topic,
        "user_constraints": {"topic_zh": topic},
        "trace_events": [], "provider_profile": "fast_json", "errors": [],
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
        fr = out.get("final_recommendation") or {}
        feas = out.get("feasibility_report") or {}
        review = out.get("review_report") or {}
        atoms = out.get("topic_atoms") or {}
        trace = out.get("trace_events") or []
        search_steps = out.get("search_steps") or []

        # Check that S2/OpenAlex were not called
        tools_used = [s.get("tool", "") for s in search_steps if s.get("type") == "tool_call"]
        s2_called = "semantic_scholar" in tools_used
        oa_called = "openalex" in tools_used
        pubmed_called = "pubmed" in tools_used

        sk_count = sum(1 for t in trace if t.get("state_keys"))

        print(f"  elapsed={elapsed}s vp={len(vp)} rc={len(rc)} dc={len(dc)} bc={len(bc)}")
        print(f"  feas={feas.get('verdict','?')}({feas.get('score','?')}) review={review.get('overall_verdict','?')}")
        print(f"  fr: n_papers={fr.get('n_papers',0)}")
        print(f"  atoms: method={atoms.get('method',[])} domain={atoms.get('domain','?')}")
        print(f"  tools_used: {tools_used}")
        print(f"  S2_called={s2_called} OA_called={oa_called} PubMed_called={pubmed_called}")
        print(f"  sk={sk_count}/{len(trace)}")

    except Exception as exc:
        elapsed = round(time.time() - t0, 2)
        print(f"  ERROR after {elapsed}s: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        cd = OUT_DIR / case_id
        cd.mkdir(parents=True, exist_ok=True)
        (cd / "error.txt").write_text(f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}", encoding="utf-8")

    time.sleep(10)

print(f"\n{'='*80}")
print("Phase 5 cases complete.")
