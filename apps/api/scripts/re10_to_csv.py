"""Generate Re10 Balanced40 reports (4-way consistency + 6 files per SOP §11).

Re10 deliverables:
  1. Plan/PaperAgent_Re10_Balanced40_逐论文审计.md (per-case table, 40 rows)
  2. Plan/PaperAgent_Re10_Balanced40_逐论文审计.csv (case-level)
  3. Plan/PaperAgent_Re10_Balanced40_候选论文.csv (candidate-level)
  4. Plan/PaperAgent_Re10_SearchTrace_索引.md (trace index)
  5. Plan/PaperAgent_Re10_ReflectionLoop_统计.json (already in tmp/, copied)
  6. Plan/PaperAgent_Re10_完工报告.md (main report)

Re10 FIX (SOP §1.4) — case-level CSV/MD gain 11 evidence columns:
  re10_status, adapter_attempt_n, adapter_success_n, adapter_error_n,
  missing_client_n, new_candidates_n, accepted_candidates_n,
  query_repair_n, url_repair_n, llm_call_n, evidence_status
"""
from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path("G:/PaperAgent")
RE10 = ROOT / "tmp_re04_eval" / "balanced40_re10_reflection"
RE08 = ROOT / "tmp_re04_eval" / "balanced40_re08"
RE09 = ROOT / "tmp_re04_eval" / "balanced40_re09_fresh"
PLAN = ROOT / "Plan"


def _load(p: Path) -> dict:
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _aggregate_trace_evidence(trace: dict) -> dict:
    """Sum adapter/evidence stats across rounds from a trace file.

    Ponytail: a single linear pass — what else is there.
    """
    rounds = trace.get("rounds") or []
    actions: list[dict] = []
    for r in rounds:
        actions.extend(r.get("actions") or [])
    attempt = len(actions)
    success = sum(1 for a in actions if a.get("status") in {"success", "no_results"})
    error = sum(1 for a in actions if a.get("status") == "error")
    missing = sum(1 for a in actions if "missing client" in (a.get("error") or ""))
    new_c = sum(int(r.get("new_candidates_n") or 0) for r in rounds)
    accept_c = sum(int(r.get("accepted_candidates_n") or 0) for r in rounds)
    q_repair = sum(int(r.get("query_repair_n") or 0) for r in rounds)
    u_repair = sum(int(r.get("url_repair_n") or 0) for r in rounds)
    return {
        "adapter_attempt_n": attempt,
        "adapter_success_n": success,
        "adapter_error_n": error,
        "missing_client_n": missing,
        "new_candidates_n": new_c,
        "accepted_candidates_n": accept_c,
        "query_repair_n": q_repair,
        "url_repair_n": u_repair,
        "llm_call_n": 0,  # not tracked per-round in current schema
    }


def _derive_re10_status(stats: dict) -> str:
    """Map evidence counts to a 4-state label.

    - blocked_tooling: tooling failed (any missing client OR zero successful calls)
    - weak:           tooling worked, but produced no new candidates
    - pass:           tooling worked and produced new candidates
    """
    if stats["missing_client_n"] > 0 or stats["adapter_success_n"] == 0:
        return "blocked_tooling"
    if stats["new_candidates_n"] == 0:
        return "weak"
    return "pass"


def _derive_evidence_status(stats: dict, re10_status: str) -> str:
    """Text version of status for the validator gate."""
    if re10_status == "blocked_tooling":
        return "tooling_blocked"
    if re10_status == "pass":
        return "wired"
    # weak branch: distinguish no-signal vs weak-signal
    return "no_signal" if stats["new_candidates_n"] == 0 else "weak_signal"


def _case_evidence_row(c: dict) -> dict:
    """Compose one case-level row: summary fields + per-trace evidence + derived status."""
    trace_path = c.get("trace_path") or ""
    stats: dict = {
        "adapter_attempt_n": 0, "adapter_success_n": 0, "adapter_error_n": 0,
        "missing_client_n": 0, "new_candidates_n": 0, "accepted_candidates_n": 0,
        "query_repair_n": 0, "url_repair_n": 0, "llm_call_n": 0,
    }
    if trace_path:
        tp = Path(trace_path)
        if tp.exists():
            stats = _aggregate_trace_evidence(_load(tp))
    re10_status = _derive_re10_status(stats)
    return {
        **stats,
        "re10_status": re10_status,
        "evidence_status": _derive_evidence_status(stats, re10_status),
    }


def _emit_csv_case() -> int:
    """Re10 case-level CSV (per Re10 SOP §11 + §1.4 evidence columns)."""
    summary = _load(RE10 / "summary.json")
    per_case = summary.get("per_case") or []
    re08 = _load(RE08 / "summary.json")
    re09 = _load(RE09 / "summary.json")
    re08_by_id = {c["case_id"]: c for c in re08.get("per_case") or []}
    re09_by_id = {c["case_id"]: c for c in re09.get("per_case") or []}
    out = PLAN / "PaperAgent_Re10_Balanced40_逐论文审计.csv"
    cols = [
        "case_id", "title", "stop_reason", "rounds", "seed_n", "elapsed_s",
        "re08_status", "re09_status",
        "re10_status",
        "adapter_attempt_n", "adapter_success_n", "adapter_error_n", "missing_client_n",
        "new_candidates_n", "accepted_candidates_n",
        "query_repair_n", "url_repair_n", "llm_call_n",
        "evidence_status",
        "trace_path",
    ]
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for c in per_case:
            cid = c["case_id"]
            ev = _case_evidence_row(c)
            r8 = re08_by_id.get(cid, {}).get("status", "?")
            r9 = re09_by_id.get(cid, {}).get("status", "?")
            w.writerow({
                "case_id": cid,
                "title": c.get("title", ""),
                "stop_reason": c.get("stop_reason", ""),
                "rounds": c.get("rounds", 0),
                "seed_n": c.get("seed_n", 0),
                "elapsed_s": c.get("elapsed_s", 0),
                "re08_status": r8,
                "re09_status": r9,
                **ev,
                "trace_path": c.get("trace_path", ""),
            })
    return len(per_case)


def _emit_csv_candidate() -> int:
    """Re10 candidate-level CSV (one row per final-pool candidate).

    Reads from per-case batch1/*.json dumps which carry
    ``final_candidate_pool`` (traces/*.json carry only counts).
    """
    summary = _load(RE10 / "summary.json")
    per_case = summary.get("per_case") or []

    out = PLAN / "PaperAgent_Re10_Balanced40_候选论文.csv"
    cols = [
        "case_id", "case_title", "bucket", "candidate_id", "title",
        "source_run", "url", "doi", "year", "venue",
        "verification_status", "added_in_round", "trace_path",
    ]
    rows: list[dict] = []
    for c in per_case:
        cid = c["case_id"]
        case_title = c.get("title", "")
        batch1_dir = RE10 / "batch1"
        bp = batch1_dir / f"{cid}.json"
        if not bp.exists():
            continue
        try:
            dump = _load(bp)
        except Exception:
            continue
        final_pool = dump.get("final_candidate_pool") or []
        if not isinstance(final_pool, list):
            continue
        for c2 in final_pool:
            if not isinstance(c2, dict):
                continue
            # bucket = role_hint
            bucket = c2.get("role_hint") or c2.get("evidence_type") or "core"
            rows.append({
                "case_id": cid,
                "case_title": case_title,
                "bucket": bucket,
                "candidate_id": c2.get("candidate_id", ""),
                "title": c2.get("title", ""),
                "source_run": c2.get("source_run", "re10"),
                "url": c2.get("url", ""),
                "doi": c2.get("doi", ""),
                "year": c2.get("year", ""),
                "venue": c2.get("venue", ""),
                "verification_status": c2.get("verification_status", ""),
                "added_in_round": c2.get("added_in_round", ""),
                "trace_path": c.get("trace_path", ""),
            })
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        rows.sort(key=lambda r: (r["case_id"],
                                  {"core": 0, "baseline": 1, "parallel": 2,
                                   "dataset": 3, "repo": 4}.get(r["bucket"], 5),
                                  r["candidate_id"]))
        w.writerows(rows)
    return len(rows)


def _emit_md_percase() -> int:
    summary = _load(RE10 / "summary.json")
    per_case = summary.get("per_case") or []
    re08 = _load(RE08 / "summary.json")
    re09 = _load(RE09 / "summary.json")
    re08_by_id = {c["case_id"]: c for c in re08.get("per_case") or []}
    re09_by_id = {c["case_id"]: c for c in re09.get("per_case") or []}
    out = PLAN / "PaperAgent_Re10_Balanced40_逐论文审计.md"
    lines = []
    lines.append("# PaperAgent Re10 Multi-Loop Reflection 搜索收口 — Balanced40 逐论文审计")
    lines.append("")
    lines.append("> 起草日: 2026-07-03")
    lines.append("> 范围: Re10 SOP §11 + §1.4 (Re10 FIX evidence columns)")
    lines.append("> 配套: [PaperAgent_Re10_完工报告.md](PaperAgent_Re10_完工报告.md) - 总体报告")
    lines.append("**数据汇总**: [PaperAgent_Re10_Balanced40_逐论文审计.csv](PaperAgent_Re10_Balanced40_逐论文审计.csv) (case-level, 40 cases)")
    lines.append("**候选论文清单**: [PaperAgent_Re10_Balanced40_候选论文.csv](PaperAgent_Re10_Balanced40_候选论文.csv) (candidate-level)")
    lines.append("**Trace 索引**: [PaperAgent_Re10_SearchTrace_索引.md](PaperAgent_Re10_SearchTrace_索引.md)")
    lines.append("")

    lines.append("## 1. 全部 40 case 状态表 (含 evidence 列)")
    lines.append("")
    lines.append(
        "| case_id | re08 | re09 | re10_stop | re10_status | evidence_status | "
        "attempt | success | error | missing | new_cand | acc_cand | q_repair | u_repair | llm |"
    )
    lines.append("|---|---|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for c in per_case:
        cid = c["case_id"]
        r8 = re08_by_id.get(cid, {}).get("status", "?")
        r9 = re09_by_id.get(cid, {}).get("status", "?")
        ev = _case_evidence_row(c)
        lines.append(
            f"| {cid} | {r8} | {r9} | **{c.get('stop_reason','?')}** | "
            f"**{ev['re10_status']}** | {ev['evidence_status']} | "
            f"{ev['adapter_attempt_n']} | {ev['adapter_success_n']} | "
            f"{ev['adapter_error_n']} | {ev['missing_client_n']} | "
            f"{ev['new_candidates_n']} | {ev['accepted_candidates_n']} | "
            f"{ev['query_repair_n']} | {ev['url_repair_n']} | {ev['llm_call_n']} |"
        )
    lines.append("")

    # Evidence totals row (so the table is auditable from MD without re-opening CSV)
    totals = Counter()
    for c in per_case:
        ev = _case_evidence_row(c)
        for k, v in ev.items():
            if isinstance(v, int):
                totals[k] += v
    lines.append("**Totals**: "
                 f"attempt={totals['adapter_attempt_n']} "
                 f"success={totals['adapter_success_n']} "
                 f"error={totals['adapter_error_n']} "
                 f"missing={totals['missing_client_n']} "
                 f"new_cand={totals['new_candidates_n']} "
                 f"acc_cand={totals['accepted_candidates_n']} "
                 f"q_repair={totals['query_repair_n']} "
                 f"u_repair={totals['url_repair_n']} "
                 f"llm={totals['llm_call_n']}")
    lines.append("")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(per_case)


def _emit_trace_index() -> int:
    summary = _load(RE10 / "summary.json")
    per_case = summary.get("per_case") or []
    out = PLAN / "PaperAgent_Re10_SearchTrace_索引.md"
    lines = []
    lines.append("# PaperAgent Re10 SearchTrace 索引")
    lines.append("")
    lines.append("> 范围: Re10 SOP §5 + §11")
    lines.append("> 数据来源: tmp_re04_eval/balanced40_re10_reflection/traces/*.json")
    lines.append("")
    lines.append("## 1. Trace 概览")
    lines.append("")
    lines.append("| case_id | rounds | stop_reason | re10_status | adapter_attempt | adapter_success | missing_client | trace_path |")
    lines.append("|---|---:|---|:---:|:---:|---:|---:|---:|")
    for c in per_case:
        cid = c["case_id"]
        ev = _case_evidence_row(c)
        lines.append(
            f"| {cid} | {c.get('rounds',0)} | {c.get('stop_reason','?')} | "
            f"**{ev['re10_status']}** | {ev['adapter_attempt_n']} | "
            f"{ev['adapter_success_n']} | {ev['missing_client_n']} | "
            f"`{c.get('trace_path','')}` |"
        )
    lines.append("")
    lines.append("## 2. Per-case Trace 摘要 (R1 / R2 / R3)")
    lines.append("")
    for c in per_case:
        cid = c["case_id"]
        tp = c.get("trace_path", "")
        if not tp or not Path(tp).exists():
            lines.append(f"### {cid} (no trace file)")
            lines.append("")
            continue
        trace = _load(Path(tp))
        ev = _case_evidence_row(c)
        lines.append(f"### {cid} - stop={c.get('stop_reason')}, rounds={c.get('rounds',0)}, status={ev['re10_status']}")
        lines.append("")
        for r in (trace.get("rounds") or []):
            ri = r.get("round", 0)
            ag = r.get("agent", "")
            r.get("observations") or {}
            new = r.get("new_candidates_n", 0)
            acc = r.get("accepted_candidates_n", 0)
            ref = (r.get("reflection") or {}).get("next_round_focus") or []
            lines.append(f"**R{ri} {ag}**: new={new} accepted={acc} next_focus={ref[:2]}")
        lines.append("")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(per_case)


def main() -> int:
    if not RE10.exists():
        print(f"ERROR: {RE10} not found; run run_balanced40_reflection_re10.py first")
        return 1
    n_case = _emit_csv_case()
    n_cand = _emit_csv_candidate()
    _emit_md_percase()
    n_trace = _emit_trace_index()
    # Copy reflection_stats.json
    src = RE10 / "reflection_stats.json"
    if src.exists():
        dst = PLAN / "PaperAgent_Re10_ReflectionLoop_统计.json"
        shutil.copy(str(src), str(dst))
        print(f"Copied {src} -> {dst}")
    print(f"wrote {n_case} case rows; {n_cand} candidate rows; {n_trace} trace index rows")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
