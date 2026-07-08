"""Re3.8 Re3.9: Generate Batch result report like Re3.0 Batch20 format."""
import json
import os
from pathlib import Path

EVAL_DIRS = ["tmp_re34_eval", "tmp_re35_eval", "tmp_re36_eval", "tmp_re38_eval"]
OUT_FILE = "Plan/PaperAgent_Re3.8_Re3.9_50篇回归结果与标答.md"

# Ground truth from Batch20 report (subset)
GROUND_TRUTH = {
    "R34-002": {"domain": "工业缺陷/钢铁", "feas": "feasible", "baselines": ["YOLOv5", "ResNet"], "datasets": ["NEU-DET", "GC10-DET"], "repos": ["ultralytics/yolov5"]},
    "R34-033": {"domain": "医学/肺结节", "feas": "risky", "baselines": ["U-Net", "YOLOv5"], "datasets": ["LUNA16", "LIDC-IDRI"], "repos": ["ultralytics/yolov5"]},
    "R34-038": {"domain": "遥感/无人机", "feas": "feasible", "baselines": ["YOLOv5", "ResNet"], "datasets": ["DOTA", "VisDrone", "UAVDT"], "repos": ["ultralytics/yolov5"]},
    "R34-046": {"domain": "机器人/机械臂", "feas": "not_recommended", "baselines": ["ResNet"], "datasets": ["Cornell Grasping", "Jacquard"], "repos": []},
    "R34-066": {"domain": "自动驾驶/多模态", "feas": "risky", "baselines": ["ResNet"], "datasets": ["KITTI", "nuScenes"], "repos": []},
    "R34-092": {"domain": "能源装备/风机", "feas": "not_recommended", "baselines": ["ResNet"], "datasets": [], "repos": []},
    "R36-003": {"domain": "三维视觉/点云", "feas": "risky", "baselines": ["ORB-SLAM2"], "datasets": ["KITTI", "TUM RGB-D"], "repos": ["ORB_SLAM2"]},
    "R36-007": {"domain": "遥感/无人机", "feas": "feasible", "baselines": ["YOLOv5"], "datasets": ["DOTA", "VisDrone"], "repos": ["ultralytics/yolov5"]},
    "R36-015": {"domain": "医学/人体重建", "feas": "risky", "baselines": ["SMPL"], "datasets": ["SURREAL", "Human3.6M"], "repos": []},
    "R36-021": {"domain": "自动驾驶", "feas": "feasible", "baselines": ["YOLOv5"], "datasets": ["KITTI", "nuScenes"], "repos": ["ultralytics/yolov5"]},
    "R36-052": {"domain": "自动驾驶/强化学习", "feas": "risky", "baselines": ["PPO"], "datasets": ["CARLA"], "repos": []},
    "R36-074": {"domain": "土木/裂缝", "feas": "feasible", "baselines": ["U-Net", "YOLOv5"], "datasets": ["DeepCrack", "SDNET2018"], "repos": ["ultralytics/yolov5"]},
    "R36-079": {"domain": "土木/裂缝", "feas": "risky", "baselines": ["U-Net"], "datasets": ["DeepCrack"], "repos": []},
    "R36-084": {"domain": "土木/裂缝", "feas": "feasible", "baselines": ["U-Net"], "datasets": ["DeepCrack", "CRACK500"], "repos": []},
    "R36-091": {"domain": "电力/巡检", "feas": "risky", "baselines": ["YOLOv5"], "datasets": [], "repos": []},
    "R36-094": {"domain": "能源装备/SCADA", "feas": "risky", "baselines": [], "datasets": [], "repos": []},
    "R36-100": {"domain": "电力/巡检", "feas": "risky", "baselines": ["YOLOv5"], "datasets": [], "repos": []},
    "R38-005": {"domain": "工业缺陷", "feas": "feasible", "baselines": ["YOLOv5"], "datasets": ["NEU-DET"], "repos": ["ultralytics/yolov5"]},
    "R38-008": {"domain": "工业缺陷/PCB", "feas": "feasible", "baselines": ["YOLOv5"], "datasets": [], "repos": ["ultralytics/yolov5"]},
    "R38-014": {"domain": "工业缺陷/织物", "feas": "risky", "baselines": ["GAN"], "datasets": [], "repos": []},
    "R38-027": {"domain": "遥感/无人机", "feas": "feasible", "baselines": ["YOLOv5"], "datasets": ["DOTA"], "repos": ["ultralytics/yolov5"]},
    "R38-047": {"domain": "自动驾驶/交通标志", "feas": "feasible", "baselines": ["YOLOv5"], "datasets": ["GTSRB"], "repos": ["ultralytics/yolov5"]},
    "R38-050": {"domain": "自动驾驶", "feas": "feasible", "baselines": ["YOLOv5"], "datasets": ["KITTI", "nuScenes"], "repos": ["ultralytics/yolov5"]},
    "R38-075": {"domain": "土木/裂缝", "feas": "feasible", "baselines": ["U-Net", "YOLOv5"], "datasets": ["DeepCrack", "SDNET2018"], "repos": ["ultralytics/yolov5"]},
    "R38-049": {"domain": "机器人/机械臂", "feas": "not_recommended", "baselines": [], "datasets": ["YCB"], "repos": []},
    "R38-057": {"domain": "机器人/机械臂", "feas": "not_recommended", "baselines": [], "datasets": [], "repos": []},
    "R38-096": {"domain": "能源装备/防冰", "feas": "risky", "baselines": [], "datasets": [], "repos": []},
}

def find_state(case_id):
    for d in EVAL_DIRS:
        p = os.path.join(d, case_id, "state.json")
        if os.path.exists(p):
            return p
    return None

def truncate(s, n=200):
    s = (s or "").strip()
    return s[:n] + "..." if len(s) > n else s

lines = []
lines.append("# PaperAgent Re3.8+Re3.9 — 50篇回归结果与标答汇总\n")
lines.append("> 本文档汇总 Re3.8/Re3.9 回归测试中各 case 的最终结果（论文/Repo/Dataset/Baselines/创新点/缝合方案/研究叙事）以及对应的标答（Ground Truth）。\n")
lines.append("- **数据来源**: tmp_re34_eval, tmp_re35_eval, tmp_re36_eval, tmp_re38_eval")
lines.append("- **标答来源**: Re3.0 Batch20 标答 + 100篇测试集一级标注")
lines.append("- **case 总数**: 见下表\n")

# Collect all cases
cases = []
for d in EVAL_DIRS:
    if not os.path.exists(d):
        continue
    for case_dir in sorted(os.listdir(d)):
        sp = os.path.join(d, case_dir, "state.json")
        if os.path.exists(sp):
            cases.append((case_dir, sp))

# Overview table
lines.append("## 总览\n")
lines.append("| Case ID | 题目 | 论文数 | Repo | Dataset | Baseline | 可行性 | 评审 |")
lines.append("|---|---|---|---|---|---|---|---|")

for case_id, sp in cases:
    s = json.load(open(sp, encoding="utf-8"))
    topic = s.get("topic", "?")
    vp = len(s.get("verified_papers", []))
    rc = len(s.get("repo_candidates", []))
    dc = len(s.get("dataset_candidates", []))
    bc = len(s.get("baseline_candidates", []))
    feas = s.get("feasibility_report", {})
    review = s.get("review_report", {})
    lines.append(f"| {case_id} | {truncate(topic, 30)} | {vp} | {rc} | {dc} | {bc} | {feas.get('verdict', '?')}({feas.get('score', '?')}) | {review.get('overall_verdict', '?')} |")

lines.append(f"\n**总计**: {len(cases)} cases\n")

# Per-case detail
for case_id, sp in cases:
    s = json.load(open(sp, encoding="utf-8"))
    topic = s.get("topic", "?")
    vp = s.get("verified_papers") or []
    wp = s.get("weak_papers") or []
    rc = s.get("repo_candidates") or []
    dc = s.get("dataset_candidates") or []
    bc = s.get("baseline_candidates") or []
    pc = s.get("parallel_candidates") or []
    inn = s.get("innovation_points") or []
    plan = s.get("stitching_plan") or {}
    narrative = s.get("research_narratives") or {}
    feas = s.get("feasibility_report", {})
    review = s.get("review_report", {})
    atoms = s.get("topic_atoms") or {}

    lines.append(f"\n## {case_id} — {topic}\n")
    lines.append(f"- **可行性裁决**: `{feas.get('verdict', '?')}` (分数: {feas.get('score', '?')})")
    lines.append(f"- **可行性理由**: {truncate(feas.get('reason', ''), 150)}")
    lines.append(f"- **复核裁决**: `{review.get('overall_verdict', '?')}`")
    lines.append(f"- **领域**: {atoms.get('domain', '?')}")
    lines.append(f"- **方法关键词**: {atoms.get('method', [])}")
    lines.append(f"- **对象关键词**: {atoms.get('object', [])}")

    lines.append(f"\n### Verified Papers ({len(vp)} 篇)")
    for p in vp[:10]:
        title = p.get("title", "?")
        url = p.get("url", "")
        src = p.get("source", "?")
        abstract = truncate(p.get("abstract", ""), 150)
        lines.append(f"- **{title}** — {src}")
        if url:
            lines.append(f"  - URL: {url}")
        if abstract:
            lines.append(f"  - Abstract: {abstract}")
    if len(vp) > 10:
        lines.append(f"- ... 等共 {len(vp)} 篇")

    lines.append(f"\n### Weak Papers ({len(wp)} 篇)")
    if wp:
        for p in wp[:5]:
            lines.append(f"- **{p.get('title', '?')}** — {p.get('source', '?')}")
        if len(wp) > 5:
            lines.append(f"- ... 等共 {len(wp)} 篇")
    else:
        lines.append("（无）")

    lines.append(f"\n### Repos ({len(rc)} 个)")
    for r in rc[:10]:
        name = r.get("mentioned_repo") or r.get("from_paper", "?")
        url = r.get("url", "")
        lines.append(f"- **{name}**")
        if url:
            lines.append(f"  - URL: {url}")
    if not rc:
        lines.append("（无）")

    lines.append(f"\n### Datasets ({len(dc)} 个)")
    for d in dc[:10]:
        name = d.get("name", "?")
        source = d.get("source", "?")
        lines.append(f"- **{name}** (source: {source})")
    if not dc:
        lines.append("（无）")

    lines.append(f"\n### Baselines ({len(bc)} 个)")
    for b in bc[:10]:
        lines.append(f"- {b.get('title', '?')}")
    if not bc:
        lines.append("（无）")

    lines.append(f"\n### Innovation Points ({len(inn)} 个)")
    for ip in inn[:5]:
        desc = truncate(ip.get("description", ""), 150)
        lines.append(f"- {desc}")
    if not inn:
        lines.append("（无）")

    if plan:
        lines.append("\n### Stitching Plan (缝合方案)")
        lines.append(f"- **Baseline**: {plan.get('baseline_model', '?')}")
        lines.append(f"- **Module B**: {plan.get('module_b', '?')}")
        lines.append(f"- **Module C**: {plan.get('module_c', '?')}")

    if narrative:
        lines.append("\n### Research Narrative (研究叙事)")
        nick = narrative.get("nick_model", "?")
        summary = truncate(narrative.get("narrative_summary", narrative.get("summary", "")), 300)
        lines.append(f"- **Nick Model**: {nick}")
        lines.append(f"- **叙事摘要**: {summary}")

    # Ground truth
    gt = GROUND_TRUTH.get(case_id)
    if gt:
        lines.append("\n### 标答 (Ground Truth)")
        lines.append(f"- **领域**: {gt['domain']}")
        lines.append(f"- **可行性**: `{gt['feas']}`")
        lines.append(f"- **标准 Baselines**: {', '.join(gt['baselines']) if gt['baselines'] else '（无）'}")
        lines.append(f"- **标准 Datasets**: {', '.join(gt['datasets']) if gt['datasets'] else '（无）'}")
        lines.append(f"- **标准 Repos**: {', '.join(gt['repos']) if gt['repos'] else '（无）'}")

# Write
Path("Plan").mkdir(exist_ok=True)
with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Report written to {OUT_FILE}")
print(f"Total cases: {len(cases)}")
