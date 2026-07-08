"""Re3.6 batch verification: check all 12 cases for P0/P1 criteria."""
import json
import os

CASES = [
    ("R36-003", "基于点云多平面检测的三维重建关键技术研究"),
    ("R36-007", "基于视觉的无人机识别与跟踪技术研究"),
    ("R36-015", "基于患者虚拟定位的三维人体重建关键技术研究"),
    ("R36-021", "基于深度学习的自动驾驶感知算法研究"),
    ("R36-052", "基于深度强化学习的无人驾驶感知与决策研究"),
    ("R36-060", "基于深度学习的车道线检测方法研究"),
    ("R36-074", "基于深度学习的混凝土桥梁裂缝检测研究"),
    ("R36-079", "基于结构光的隧道裂缝检测技术研究与实现"),
    ("R36-084", "基于U-Net卷积网络的地质岩层裂缝检测方法"),
    ("R36-091", "基于云计算的输电线路缺陷检测平台"),
    ("R36-094", "基于SCADA数据的风机叶片结冰诊断研究"),
    ("R36-100", "基于深度学习的配电设备视觉识别技术研究"),
]

results = []
verdicts_feas = []
verdicts_review = []

for case_id, topic in CASES:
    state_path = f"tmp_re36_eval/{case_id}/state.json"
    trace_path = f"tmp_re36_eval/{case_id}/trace.json"
    if not os.path.exists(state_path):
        results.append((case_id, "SKIP", "no state.json", {}, 0))
        continue

    d = json.load(open(state_path, encoding="utf-8"))
    vp = len(d.get("verified_papers", []))
    rc = len(d.get("repo_candidates", []))
    bc = len(d.get("baseline_candidates", []))
    pc = len(d.get("parallel_candidates", []))
    dc = len(d.get("dataset_candidates", []))
    fr = d.get("final_recommendation", {})
    feas = d.get("feasibility_report", {})
    review = d.get("review_report", {})
    atoms = d.get("topic_atoms", {})

    trace = []
    if os.path.exists(trace_path):
        trace = json.load(open(trace_path, encoding="utf-8"))

    has_recursion = any("RecursionError" in str(ev) for ev in trace)
    sk_count = sum(1 for ev in trace if ev.get("state_keys"))
    sk_total = len(trace)
    sk_ratio = (sk_count / sk_total * 100) if sk_total > 0 else 0

    feas_v = feas.get("verdict", "?")
    review_v = review.get("overall_verdict", "?")
    verdicts_feas.append(feas_v)
    verdicts_review.append(review_v)

    issues = []
    if vp < 3:
        issues.append(f"vp={vp}<3")
    if fr.get("n_papers", 0) != vp:
        issues.append(f"fr.n_papers={fr.get('n_papers')}!={vp}")
    if fr.get("n_papers", 0) == 0:
        issues.append("fr_n_papers=0")
    if has_recursion:
        issues.append("RecursionError")
    if sk_ratio < 80:
        issues.append(f"sk_ratio={sk_ratio:.0f}%<80%")

    # P1 checks
    reason = feas.get("reason", "")
    if case_id == "R36-015":
        if not any(kw in reason for kw in ["合规", "隐私", "医疗", "医学", "medical", "privacy"]):
            issues.append("missing compliance risk")

    status = "FAIL" if issues else "PASS"
    info = {
        "vp": vp, "rc": rc, "bc": bc, "pc": pc, "dc": dc,
        "feas": feas_v, "score": feas.get("score", "?"),
        "review": review_v,
        "fr_np": fr.get("n_papers", 0),
        "sk": f"{sk_count}/{sk_total}",
        "domain": atoms.get("domain", "?"),
    }
    results.append((case_id, status, "; ".join(issues) if issues else "OK", info, sk_ratio))

print("=" * 110)
print("Re3.6 Batch Regression Results (12 cases)")
print("=" * 110)
for case_id, status, detail, info, sk_ratio in results:
    if info:
        print(f"{case_id}: {status} | vp={info['vp']} rc={info['rc']} bc={info['bc']} pc={info['pc']} dc={info['dc']} | "
              f"feas={info['feas']}({info['score']}) review={info['review']} | sk={info['sk']} domain={info['domain']}")
        if status == "FAIL":
            print(f"  ! {detail}")
    else:
        print(f"{case_id}: {status} | {detail}")

n_pass = sum(1 for _, s, _, _, _ in results if s == "PASS")
n_fail = sum(1 for _, s, _, _, _ in results if s == "FAIL")
n_skip = sum(1 for _, s, _, _, _ in results if s == "SKIP")
print(f"\n{'='*110}")
print(f"TOTAL: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP out of {len(results)}")
print(f"Feasibility verdicts: {set(verdicts_feas)} ({len(set(verdicts_feas))} unique)")
print(f"Review verdicts: {set(verdicts_review)} ({len(set(verdicts_review))} unique)")
print(f"State keys avg coverage: {sum(r[4] for r in results)/max(len(results),1):.0f}%")
