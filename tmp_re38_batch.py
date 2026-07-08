"""Re3.8: Run 7 remaining R36 cases + selected new cases."""
import json, os, sys, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv("G:/PaperAgent/.env")

OUT_DIR = Path("G:/PaperAgent/tmp_re38_eval")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Phase 3: 7 remaining from Re3.6
CASES_P3 = [
    ("R36-060", "基于深度学习的车道线检测方法研究"),
    ("R36-074", "基于深度学习的混凝土桥梁裂缝检测研究"),
    ("R36-079", "基于结构光的隧道裂缝检测技术研究与实现"),
    ("R36-084", "基于U-Net卷积网络的地质岩层裂缝检测方法"),
    ("R36-091", "基于云计算的输电线路缺陷检测平台"),
    ("R36-094", "基于SCADA数据的风机叶片结冰诊断研究"),
    ("R36-100", "基于深度学习的配电设备视觉识别技术研究"),
]

# Phase 5: 30 new cases (subset for first batch of 10)
CASES_P5_BATCH1 = [
    ("R38-005", "基于深度学习的钢材表面缺陷检测算法研究"),
    ("R38-008", "基于机器视觉的PCB缺陷检测系统研究"),
    ("R38-011", "基于深度学习的锂电池表面缺陷检测方法研究"),
    ("R38-023", "基于深度学习的焊缝缺陷检测技术研究"),
    ("R38-047", "基于深度学习的交通标志识别算法研究"),
    ("R38-050", "基于深度学习的行人检测与跟踪算法研究"),
    ("R38-027", "基于深度学习的农作物病虫害检测研究"),
    ("R38-037", "基于无人机遥感的森林火灾检测算法研究"),
    ("R38-006", "基于深度学习的三维物体重建技术研究"),
    ("R38-004", "基于深度学习的医学图像分割算法研究"),
]

ALL_CASES = CASES_P3 + CASES_P5_BATCH1

from apps.api.app.services.agents.graph.research_graph import build_graph
from apps.api.app.services.agents.graph.state import ResearchState

g = build_graph()

for case_id, topic in ALL_CASES:
    # Skip if already has state.json
    existing = None
    for d in ["tmp_re36_eval", "tmp_re38_eval"]:
        p = Path(d) / case_id / "state.json"
        if p.exists():
            existing = p
            break
    if existing:
        print(f"\n  SKIP {case_id} (already has state.json)")
        continue

    print(f"\n{'='*80}")
    print(f"  CASE: {case_id} | TOPIC: {topic}")
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
        pc = out.get("parallel_candidates") or []
        fr = out.get("final_recommendation") or {}
        feas = out.get("feasibility_report") or {}
        review = out.get("review_report") or {}
        atoms = out.get("topic_atoms") or {}
        trace = out.get("trace_events") or []

        sk_count = sum(1 for t in trace if t.get("state_keys"))
        has_recursion = any("RecursionError" in str(t) for t in trace)

        issues = []
        if len(vp) < 3: issues.append(f"vp={len(vp)}<3")
        if fr.get("n_papers",0) != len(vp): issues.append(f"fr.np={fr.get('n_papers')}!={len(vp)}")
        if fr.get("n_papers",0) == 0: issues.append("fr_np=0")
        if has_recursion: issues.append("RecursionError")
        if sk_count < 5: issues.append(f"sk={sk_count}")

        status = "FAIL" if issues else "PASS"
        print(f"  elapsed={elapsed}s vp={len(vp)} rc={len(rc)} dc={len(dc)} bc={len(bc)} pc={len(pc)}")
        print(f"  feas={feas.get('verdict','?')}({feas.get('score','?')}) review={review.get('overall_verdict','?')}")
        print(f"  fr: n_papers={fr.get('n_papers',0)} n_baseline={fr.get('n_baseline',0)} n_parallel={fr.get('n_parallel',0)}")
        print(f"  atoms: method={atoms.get('method',[])} domain={atoms.get('domain','?')}")
        print(f"  sk={sk_count}/{len(trace)} | {status}")
        if issues:
            print(f"  ISSUES: {'; '.join(issues)}")

    except Exception as exc:
        elapsed = round(time.time() - t0, 2)
        print(f"  ERROR after {elapsed}s: {type(exc).__name__}: {exc}")
        import traceback; traceback.print_exc()
        cd = OUT_DIR / case_id; cd.mkdir(parents=True, exist_ok=True)
        (cd / "error.txt").write_text(f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}", encoding="utf-8")

    time.sleep(10)

print(f"\n{'='*80}")
print("All cases complete.")
