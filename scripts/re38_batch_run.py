"""Re3.8 Phase 5: Run remaining R38 cases to reach 50-paper total."""
import json
import time
import traceback
from pathlib import Path
from dotenv import load_dotenv

from apps.api.app.services.agents.graph.research_graph import build_graph
from apps.api.app.services.agents.graph.state import ResearchState

load_dotenv("G:/PaperAgent/.env")

OUT_DIR = Path("G:/PaperAgent/tmp_re38_eval")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 24 remaining cases (27 already done across R34/R35/R36/R38)
# Skip R38-094b (thesis 094 already done as R36-094) and R38-033b (thesis 033 already done as R35-033)
CASES = [
    ("R38-014", "基于生成对抗网络的织物缺陷检测算法研究"),
    ("R38-075", "基于深度学习的混凝土路面裂缝检测研究"),
    ("R38-076", "基于深度学习的道路裂缝检测研究"),
    ("R38-083", "基于多分辨率网络的桥梁裂缝分割算法研究"),
    ("R38-047", "基于深度学习无人驾驶交通安全标志检测与识别研究"),
    ("R38-050", "基于深度学习的自动驾驶感知算法"),
    ("R38-067", "基于深度学习的车辆检测及应用研究"),
    ("R38-026", "基于深度卷积神经网络的巡检图像电力部件识别方法研究"),
    ("R38-040", "基于改进YOLO网络与极限学习机的绝缘子故障检测"),
    ("R38-095", "基于深度学习的输电杆塔关键点检测方法研究"),
    ("R38-098", "基于深度学习的接触网绝缘子识别及其污秽检测技术研究"),
    ("R38-037", "基于YOLO算法的遥感图像飞机目标检测技术研究"),
    ("R38-043", "基于无人机平台的动态目标检测系统开发"),
    ("R38-027", "基于YOLOv5模型的遥感影像飞机目标检测"),
    ("R38-006", "三维重建中点云数据处理关键技术研究"),
    ("R38-009", "点云的三维重建与纹理映射"),
    ("R38-018", "基于深度学习的三维点云补全方法研究"),
    ("R38-004", "基于改进YOLOv4模型的快速目标检测与测距算法研究"),
    ("R38-013", "基于机器视觉的板类堆叠零件分拣系统研究"),
    ("R38-029", "基于多种数据库的改进YOLO算法研究"),
    ("R38-034", "基于深度学习的目标检测算法研究"),
    ("R38-049", "基于特征点的目标位姿估计与机械臂抓取控制"),
    ("R38-057", "基于深度相机的机械臂动态避障规划研究"),
    ("R38-096", "基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究"),
]

g = build_graph()

for case_id, topic in CASES:
    # Skip if already has state.json
    if (OUT_DIR / case_id / "state.json").exists():
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
        if len(vp) < 3:
            issues.append(f"vp={len(vp)}<3")
        if fr.get("n_papers", 0) != len(vp):
            issues.append(f"fr.np={fr.get('n_papers')}!={len(vp)}")
        if fr.get("n_papers", 0) == 0:
            issues.append("fr_np=0")
        if has_recursion:
            issues.append("RecursionError")
        if sk_count < 5:
            issues.append(f"sk={sk_count}")

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
        traceback.print_exc()
        cd = OUT_DIR / case_id
        cd.mkdir(parents=True, exist_ok=True)
        (cd / "error.txt").write_text(f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}", encoding="utf-8")

    time.sleep(10)

print(f"\n{'='*80}")
print("All cases complete.")
