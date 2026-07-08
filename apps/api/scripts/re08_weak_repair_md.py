"""Generate PaperAgent_Re08_弱项补证明细.md."""
from __future__ import annotations

import json
from pathlib import Path

RE08 = Path("G:/PaperAgent/tmp_re04_eval/balanced40_re08")
OUT = Path("G:/PaperAgent/Plan/PaperAgent_Re08_弱项补证明细.md")

cases = []
for p in RE08.glob("*/ENG-THESIS-*.json"):
    try:
        c = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    if c.get("status") in ("fail", "weak"):
        cases.append(c)
cases.sort(key=lambda c: (0 if c["status"] == "fail" else 1, c["case_id"]))

out: list[str] = []
out.append("# PaperAgent Re08 弱项补证明细 (16 cases = 3 fail + 13 weak)")
out.append("")
out.append("> 起草日：2026-07-03")
out.append("> 范围：Re08 SOP §4.3 GapRepairPlanner 产物")
out.append("> 数据来源：`tmp_re04_eval/balanced40_re08/<batch>/<case_id>.json` 的 `repair_plan` 字段")
out.append("")
out.append("## 0. 一屏总览")
out.append("")
out.append("| 维度 | 数值 |")
out.append("|---|---:|")
n_fail = sum(1 for c in cases if c["status"] == "fail")
n_weak = sum(1 for c in cases if c["status"] == "weak")
out.append(f"| fail cases (含 repair_plan) | {n_fail} |")
out.append(f"| weak cases (含 repair_plan) | {n_weak} |")
total_queries = 0
for c in cases:
    for entry in (c.get("repair_plan", {}).get("repair_plan") or []):
        total_queries += len(entry.get("queries", []))
out.append(f"| 总定向 query 数 | {total_queries} |")
out.append("")

for c in cases:
    cid = c["case_id"]
    title = c.get("title", "")
    status = c["status"]
    reason = c.get("reason", "")[:240]
    out.append("---")
    out.append("")
    out.append(f"## {cid} — `{status}`")
    out.append("")
    out.append(f"**Title**: {title}")
    out.append("")
    out.append(f"**Reason**: {reason}")
    out.append("")
    rp = c.get("repair_plan", {})
    plan = rp.get("repair_plan", [])
    if not plan:
        out.append("**(no repair plan — case passes without gap)**")
        out.append("")
        continue
    for entry in plan:
        gap = entry.get("gap", "")
        target = entry.get("target_role", "")
        out.append(f"### gap: `{gap}`  →  target_role: `{target}`")
        out.append("")
        for q in entry.get("queries", []):
            tool = q.get("tool", "?")
            query = q.get("query", "")
            why = q.get("why", "")
            out.append(f"- **[{tool}]** `{query}`")
            out.append(f"  - *why*: {why}")
        out.append("")
    ur = rp.get("unrepairable_reason", "")
    if ur:
        out.append(f"**Unrepairable**: {ur}")
        out.append("")

OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"wrote {len(out)} lines for {len(cases)} cases ({n_fail} fail + {n_weak} weak), {total_queries} total queries")