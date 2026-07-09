"""Generate Batch20-format report for 3 cases: R39-CONS, R39-PILE, R39-GAS."""
import json
import os
from pathlib import Path

CASES = [
    ("R39-CONS", "tmp_re13_eval"),
    ("R39-PILE", "tmp_re13_eval"),
    ("R39-GAS", "tmp_re13_eval"),
]

OUT_FILE = "Plan/PaperAgent_Re3.9.4_3篇测试结果与标答.md"

def truncate(s, n=300):
    s = (s or "").strip()
    return s[:n] + "..." if len(s) > n else s

lines = []
lines.append("# PaperAgent Re3.9.4 — 3篇测试结果与标答汇总\n")
lines.append("> 本文档汇总 R39-CONS、R39-PILE、R39-GAS 三个 case 的最终结果。\n")
lines.append("- **数据来源**: tmp_re13_eval")
lines.append("- **case 总数**: 3\n")

# Overview table
lines.append("## 总览\n")
lines.append("| Case ID | 题目 | 论文数 | Repo | Dataset | Baseline | 可行性 | 评审 |")
lines.append("|---|---|---|---|---|---|---|---|")

all_data = {}
for case_id, eval_dir in CASES:
    sp = os.path.join(eval_dir, case_id, "state.json")
    if not os.path.exists(sp):
        lines.append(f"| {case_id} | — | SKIP | — | — | — | — | — |")
        continue
    s = json.load(open(sp, encoding="utf-8"))
    all_data[case_id] = s
    topic = s.get("topic", "?")
    vp = len(s.get("verified_papers", []))
    rc = len(s.get("repo_candidates", []))
    dc = len(s.get("dataset_candidates", []))
    bc = len(s.get("baseline_candidates", []))
    feas = s.get("feasibility_report", {})
    review = s.get("review_report", {})
    lines.append(f"| {case_id} | {truncate(topic, 25)} | {vp} | {rc} | {dc} | {bc} | {feas.get('verdict', '?')}({feas.get('score', '?')}) | {review.get('overall_verdict', '?')} |")

lines.append("")

# Per-case detail
for case_id, eval_dir in CASES:
    s = all_data.get(case_id)
    if not s:
        continue

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
    search_steps = s.get("search_steps") or []
    filter_results = s.get("filter_results", {})

    lines.append(f"\n## {case_id} — {topic}\n")
    lines.append(f"- **可行性裁决**: `{feas.get('verdict', '?')}` (分数: {feas.get('score', '?')})")
    lines.append(f"- **可行性理由**: {truncate(feas.get('reason', ''), 200)}")
    lines.append(f"- **复核裁决**: `{review.get('overall_verdict', '?')}`")
    lines.append(f"- **领域**: {atoms.get('domain', '?')}")
    lines.append(f"- **方法关键词**: {atoms.get('method', [])}")
    lines.append(f"- **对象关键词**: {atoms.get('object', [])}")
    lines.append(f"- **任务关键词**: {atoms.get('task', [])}")

    # Check Chinese in atoms
    all_kw = (atoms.get("method") or []) + (atoms.get("object") or []) + (atoms.get("task") or [])
    has_cn = any(any(ord(c) > 127 for c in str(k)) for k in all_kw)
    lines.append(f"- **关键词全英文**: {'✅' if not has_cn else '❌ 有中文'}")

    # Search steps
    lines.append(f"\n### Search Steps ({len(search_steps)} 步)")
    for ss in search_steps:
        stype = ss.get("type", "?")
        if stype == "tool_call":
            tool = ss.get("tool", "?")
            query = ss.get("query", "?")[:60]
            n = ss.get("n_results", 0)
            failed = ss.get("failed", False)
            status = "FAILED" if failed else f"{n} results"
            lines.append(f"- step {ss.get('step', '?')}: {tool} \"{query}\" -> {status}")
        elif stype == "stop":
            lines.append(f"- step {ss.get('step', '?')}: STOP — {ss.get('reason', '')}")
        elif stype == "reflection":
            lines.append(f"- step {ss.get('step', '?')}: REFLECTION — {ss.get('reason', '')}")

    # Filter results
    if filter_results:
        lines.append("\n### Filter Results")
        lines.append(f"- total: {filter_results.get('total', 0)}")
        lines.append(f"- kept: {filter_results.get('kept', 0)}")
        lines.append(f"- dropped: {filter_results.get('dropped', 0)}")
        lines.append(f"- low_relevance: {filter_results.get('low_relevance', 0)}")

    lines.append(f"\n### Verified Papers ({len(vp)} 篇)")
    for p in vp[:15]:
        title = p.get("title", "?")
        url = p.get("url", "")
        src = p.get("source", "?")
        abstract = truncate(p.get("abstract", ""), 150)
        lines.append(f"- **{title}** — {src}")
        if url:
            lines.append(f"  - URL: {url}")
        if abstract:
            lines.append(f"  - Abstract: {abstract}")
    if len(vp) > 15:
        lines.append(f"- ... 等共 {len(vp)} 篇")
    if not vp:
        lines.append("（无）")

    lines.append(f"\n### Weak Papers ({len(wp)} 篇)")
    if wp:
        for p in wp[:5]:
            lines.append(f"- **{p.get('title', '?')}** — {p.get('source', '?')} (relevance: {p.get('relevance_flag', 'none')})")
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
        desc = truncate(ip.get("description", ""), 200)
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
        summary = truncate(narrative.get("narrative_summary", narrative.get("summary", "")), 400)
        lines.append(f"- **Nick Model**: {nick}")
        lines.append(f"- **叙事摘要**: {summary}")

# Write
Path("Plan").mkdir(exist_ok=True)
with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Report written to {OUT_FILE}")
print(f"Cases: {list(all_data.keys())}")
