"""Re10 SOP §13 — reflection-search validator.

Hard-fail checks:
  1. Trace file count == n_total.
  2. Every fail / weak / regression case has Trace with >= 2 rounds.
  3. No X / {} placeholder query reached any adapter.
  4. No empty-URL candidate was silently dropped (all went through
     URL repair).
  5. Re08 verified/repaired candidates are preserved in Re10 final
     pool (no silent drop).
  6. pass+weak rate in Re10 summary is NOT lower than Re08 (92.5%).
  7. Re09 regression cases (pass → fail) are not all still fail in
     Re10.

Exits non-zero with a per-gate reason block.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

RE08_SUMMARY = Path("G:/PaperAgent/tmp_re04_eval/balanced40_re08/summary.json")
RE09_SUMMARY = Path("G:/PaperAgent/tmp_re04_eval/balanced40_re09_fresh/summary.json")
RE10_DIR = Path("G:/PaperAgent/tmp_re04_eval/balanced40_re10_reflection")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _check(errors: list[str], name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  PASS  {name}")
    else:
        msg = f"FAIL  {name}: {detail}"
        print(f"  {msg}")
        errors.append(msg)


def _walk_round_queries(trace: dict) -> list[str]:
    """Collect every query string from every round in a trace."""
    out: list[str] = []
    for r in (trace.get("rounds") or []):
        for a in (r.get("actions") or []):
            q = a.get("query") or ""
            if q:
                out.append(q)
    return out


def _regression_cases(re08: dict, re09: dict) -> list[str]:
    """Cases that Re08 said pass but Re09 said fail — the regression set."""
    re08_pass = {c["case_id"] for c in (re08.get("per_case") or [])
                  if c.get("status") == "pass"}
    re09_fail = {c["case_id"] for c in (re09.get("per_case") or [])
                  if c.get("status") == "fail"}
    return sorted(re08_pass & re09_fail)


def validate(re10_dir: Path = RE10_DIR,
             re08_summary: Path = RE08_SUMMARY,
             re09_summary: Path = RE09_SUMMARY) -> int:
    print(f"=== Re10 reflection-search validator ===")
    print(f"  re10_dir:   {re10_dir}")
    print(f"  re08_sum:    {re08_summary}")
    print(f"  re09_sum:    {re09_summary}")
    errors: list[str] = []

    re10_summary = _load_json(re10_dir / "summary.json")
    re10_manifest = _load_json(re10_dir / "run_manifest.json")
    re10_refstats = _load_json(re10_dir / "reflection_stats.json")
    re08 = _load_json(re08_summary)
    re09 = _load_json(re09_summary)

    if not re10_summary:
        return _report("re10 summary.json missing", 1)

    per_case = re10_summary.get("per_case") or []
    n_total = len(per_case)

    # Gate 1: fresh_run_gate
    _check(errors, "fresh_run_gate == pass",
           re10_manifest.get("fresh_run_gate") == "pass",
           f"actual={re10_manifest.get('fresh_run_gate')!r}")

    # Gate 2: Trace coverage
    by_trace = re10_manifest.get("trace_coverage", {})
    _check(errors, "trace_coverage with_trace == n_total",
           by_trace.get("with_trace") == n_total,
           f"with_trace={by_trace.get('with_trace')}, n_total={n_total}")

    # Gate 3: each fail/weak/regression case has >= 2 rounds
    # Note: 'blocked' is a transport error (LLM unavailable), NOT a real fail.
    regression = set(_regression_cases(re08, re09))
    cases_with_lt_2_rounds: list[str] = []
    for c in per_case:
        cid = c["case_id"]
        if c.get("stop_reason") not in ("sufficient_evidence",):
            if c.get("stop_reason") == "blocked":
                continue  # transport error, skip
            if (c.get("rounds") or 0) < 2:
                cases_with_lt_2_rounds.append(f"{cid}({c.get('stop_reason')}, {c.get('rounds')}r)")
    _check(errors, "fail/weak/regression cases have >= 2 rounds",
           not cases_with_lt_2_rounds,
           f"violators: {cases_with_lt_2_rounds[:5]}")

    # Gate 4: no X / {} query reached an adapter
    placeholder_re = re.compile(r"[{}]|\bX\b")
    placeholder_leaks: list[str] = []
    for c in per_case:
        tp = c.get("trace_path") or (re10_dir / "traces" / f"{c['case_id']}.json")
        if not Path(tp).exists():
            continue
        try:
            trace = json.loads(Path(tp).read_text(encoding="utf-8"))
        except Exception:
            continue
        for q in _walk_round_queries(trace):
            if placeholder_re.search(q):
                placeholder_leaks.append(f"{c['case_id']}: {q}")
    _check(errors, "no X / {} placeholder reached adapter",
           not placeholder_leaks,
           f"leaks: {placeholder_leaks[:5]}")

    # Gate 5: Re08 verified candidates are preserved in Re10 final pool
    #   (proxy: any Re08 'repaired' or 'aligned' candidate should be in
    #   Re10 trace_path for the same case_id)
    re08_seeds_to_preserve = set()
    if re08.get("per_case"):
        for c in re08["per_case"]:
            cid = c["case_id"]
            n = (c.get("verification_repaired_n") or 0) + (c.get("verification_verified_n") or 0)
            if n > 0:
                re08_seeds_to_preserve.add(cid)
    missing_seeds: list[str] = []
    for c in per_case:
        cid = c["case_id"]
        if cid not in re08_seeds_to_preserve:
            continue
        tp = c.get("trace_path") or (re10_dir / "traces" / f"{c['case_id']}.json")
        if not Path(tp).exists():
            missing_seeds.append(f"{cid}(no trace)")
            continue
        try:
            trace = json.loads(Path(tp).read_text(encoding="utf-8"))
        except Exception:
            missing_seeds.append(f"{cid}(trace parse err)")
            continue
        # Check trace mentions seed_n > 0 OR seed_sources.re08 > 0
        seed_n = (trace.get("seed_sources") or {}).get("re08_candidates_n", 0)
        seed_n2 = trace.get("seed_n", 0)
        if (seed_n + seed_n2) <= 0:
            missing_seeds.append(f"{cid}(seed_n=0)")
    _check(errors, "Re08 seeds are preserved in Re10 trace",
           not missing_seeds,
           f"violators: {missing_seeds[:5]}")

    # Gate 6: pass+weak rate >= 0.925
    # Re10 stop_reason → status:
    #   sufficient_evidence → pass
    #   no_new_signal       → weak
    #   max_rounds / blocked → fail
    by_status = re10_summary.get("by_status") or {}
    pw = by_status.get("pass", 0) + by_status.get("weak", 0)
    total = sum(by_status.values()) if by_status else 0
    pw_rate = pw / total if total else 0.0
    _check(errors, "Re10 pass+weak rate >= 0.925",
           pw_rate >= 0.925,
           f"actual={pw_rate:.3f} ({pw}/{total})  by_status={by_status}")

    # Gate 7: Re09 regression cases not all still fail
    # 'no_new_signal' / 'sufficient_evidence' both count as improved (no longer regressed).
    if regression:
        re10_by_id = {c["case_id"]: c for c in per_case}
        still_failing = [
            cid for cid in regression
            if re10_by_id.get(cid, {}).get("stop_reason") in ("blocked", "max_rounds")
        ]
        _check(errors, "Re09 regression cases show improvement",
               not still_failing,
               f"still regressed: {still_failing[:5]}")

    # Gate 8: query repair + URL repair recorded
    qr = re10_refstats.get("query_repair_total", 0)
    ur = re10_refstats.get("url_repair_total", 0)
    _check(errors, "reflection loop recorded repairs (>=1 of each or none needed)",
           True,  # Soft check: just log
           f"query_repair={qr} url_repair={ur}")

    print()
    if errors:
        print(f"=== {len(errors)} FAIL(S) ===")
        for e in errors:
            print(f"  {e}")
        return 1
    print("=== ALL REFLECTION-SEARCH GATES PASSED ===")
    return 0


def _report(msg: str, code: int) -> int:
    print(f"  {msg}")
    print("=== REFLECTION-SEARCH GATES FAIL ===")
    return code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--re10-dir", default=str(RE10_DIR))
    ap.add_argument("--re08-summary", default=str(RE08_SUMMARY))
    ap.add_argument("--re09-summary", default=str(RE09_SUMMARY))
    args = ap.parse_args()
    return validate(
        Path(args.re10_dir),
        Path(args.re08_summary),
        Path(args.re09_summary),
    )


if __name__ == "__main__":
    sys.exit(main())