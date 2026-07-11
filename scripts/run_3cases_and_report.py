"""Run 3 new cases + generate report."""
import asyncio
import json
import os
import shutil
import time
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:18182"

CASES = [
    ("R39-CORR", "钢筋混凝土中钢筋腐蚀原理的研究"),
    ("R39-NDT", "混凝土非破损检测技术开发与应用研究"),
    ("R39-LOAD", "基于大数据分析的电力负荷预测模型研究"),
]

REPORT_CASES = [
    ("R39-CORR", "tmp_re13_eval"),
    ("R39-NDT", "tmp_re13_eval"),
    ("R39-LOAD", "tmp_re13_eval"),
    ("R39-CONS", "tmp_re13_eval"),
    ("R39-PILE", "tmp_re13_eval"),
    ("R39-GAS", "tmp_re13_eval"),
]

OUT_FILE = "Plan/PaperAgent_Re3.9.4_6篇测试结果与标答.md"


def truncate(s, n=300):
    s = (s or "").strip()
    return s[:n] + "..." if len(s) > n else s


async def submit_and_wait(case_id, topic):
    case_dir = Path(f"G:/PaperAgent/tmp_re13_eval/{case_id}")
    if case_dir.exists():
        shutil.rmtree(case_dir)

    print(f"\n{'='*80}")
    print(f"  CASE: {case_id} | TOPIC: {topic}")
    print(f"{'='*80}", flush=True)

    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.post(f"{BASE_URL}/api/v1/research/", json={"case_id": case_id, "topic": topic})
        print(f"  Submit: {resp.status_code}")

    t0 = time.time()
    for i in range(200):
        await asyncio.sleep(3)
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"{BASE_URL}/api/v1/research/{case_id}/status")
            data = resp.json()
            st = data.get("status", "?")
            if i % 10 == 0:
                print(f"  t={i*3}s: {st} current={data.get('current_node','?')}")
            if st in ("done", "error"):
                elapsed = round(time.time() - t0, 1)
                print(f"  Done: {st} elapsed={elapsed}s vp={data.get('n_papers','?')}")
                return st
    print("  TIMEOUT")
    return "timeout"


async def main():
    # Run 3 cases
    for case_id, topic in CASES:
        await submit_and_wait(case_id, topic)
        await asyncio.sleep(5)

    # Generate report
    print(f"\n{'='*80}")
    print("Generating report...")
    lines = []
    lines.append("# PaperAgent Re3.9.4 — 6篇测试结果与标答汇总\n")
    lines.append("> 本文档汇总 R39-CONS、R39-PILE、R39-GAS、R39-CORR、R39-NDT、R39-LOAD 六个 case 的最终结果。\n")
    lines.append("- **数据来源**: tmp_re13_eval")
    lines.append("- **case 总数**: 6\n")

    # Load all states
    all_data = {}
    for case_id, eval_dir in REPORT_CASES:
        sp = os.path.join(eval_dir, case_id, "state.json")
        if os.path.exists(sp):
            all_data[case_id] = json.load(open(sp, encoding="utf-8"))

    # Overview table
    lines.append("## 总览\n")
    lines.append("| Case ID | 题目 | 论文数 | Repo | Dataset | Baseline | 可行性 | 评审 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for case_id, s in all_data.items():
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
    for case_id, s in all_data.items():
        topic = s.get("topic", "?")
        vp = s.get("verified_papers") or []
        wp = s.get("weak_papers") or []
        rc = s.get("repo_candidates") or []
        dc = s.get("dataset_candidates") or []
        bc = s.get("baseline_candidates") or []
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

        # Filter
        if filter_results:
            lines.append("\n### Filter Results")
            lines.append(f"- total: {filter_results.get('total', 0)}, kept: {filter_results.get('kept', 0)}, dropped: {filter_results.get('dropped', 0)}, low_relevance: {filter_results.get('low_relevance', 0)}")

        # Verified Papers
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

        # Weak
        lines.append(f"\n### Weak Papers ({len(wp)} 篇)")
        if wp:
            for p in wp[:5]:
                lines.append(f"- **{p.get('title', '?')}** — {p.get('source', '?')} (relevance: {p.get('relevance_flag', 'none')})")
            if len(wp) > 5:
                lines.append(f"- ... 等共 {len(wp)} 篇")
        else:
            lines.append("（无）")

        # Repos
        lines.append(f"\n### Repos ({len(rc)} 个)")
        for r in rc[:10]:
            name = r.get("mentioned_repo") or r.get("from_paper", "?")
            url = r.get("url", "")
            lines.append(f"- **{name}**")
            if url:
                lines.append(f"  - URL: {url}")
        if not rc:
            lines.append("（无）")

        # Datasets
        lines.append(f"\n### Datasets ({len(dc)} 个)")
        for d in dc[:10]:
            name = d.get("name", "?")
            source = d.get("source", "?")
            lines.append(f"- **{name}** (source: {source})")
        if not dc:
            lines.append("（无）")

        # Baselines
        lines.append(f"\n### Baselines ({len(bc)} 个)")
        for b in bc[:10]:
            lines.append(f"- {b.get('title', '?')}")
        if not bc:
            lines.append("（无）")

        # Innovation
        lines.append(f"\n### Innovation Points ({len(inn)} 个)")
        for ip in inn[:5]:
            desc = truncate(ip.get("description", ""), 200)
            lines.append(f"- {desc}")
        if not inn:
            lines.append("（无）")

        # Stitching Plan
        if plan:
            lines.append("\n### Stitching Plan (缝合方案)")
            lines.append(f"- **Baseline**: {plan.get('baseline_model', '?')}")
            lines.append(f"- **Module B**: {plan.get('module_b', '?')}")
            lines.append(f"- **Module C**: {plan.get('module_c', '?')}")

        # Narrative
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
    print(f"Cases in report: {list(all_data.keys())}")


asyncio.run(main())
