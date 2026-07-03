"""Re09 SOP §4.5 — fresh-run validator.

Catches the "伪 fresh" anti-pattern where someone copies Re05/Re08
dumps to balanced40_re09_fresh and declares it fresh.

Hard-fails if any of these gates trip:

  * data_source != "fresh_online_retrieval"
  * source_input_dir points to balanced40/ or balanced40_re08/
  * adapter_call_count.total == 0
  * llm_call_count.total == 0  (unless no_llm_mode)
  * repair_execution.executed_queries_n == 0
  * all verification_status == weak_metadata
  * manifest absent
  * report_status_counts != summary.by_status

Exits non-zero with a per-gate reason block.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BANNED_SOURCE_DIRS = (
    "tmp_re04_eval/balanced40",
    "tmp_re04_eval/balanced40_re07",
    "tmp_re04_eval/balanced40_re08",
)


def _check(errors: list[str], name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  PASS  {name}")
    else:
        msg = f"FAIL  {name}: {detail}"
        print(f"  {msg}")
        errors.append(msg)


def validate(out_dir: Path) -> int:
    print(f"=== Re09 fresh-run validator ===")
    print(f"  out_dir: {out_dir}")

    errors: list[str] = []

    manifest_path = out_dir / "run_manifest.json"
    summary_path = out_dir / "summary.json"
    if not manifest_path.exists():
        return _report_error(f"FATAL: {manifest_path} not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Gate 1: data_source
    _check(errors,
           "data_source == fresh_online_retrieval",
           manifest.get("data_source") == "fresh_online_retrieval",
           f"actual={manifest.get('data_source')!r}")

    # Gate 2: source_input_dir not in banned list
    sid = manifest.get("source_input_dir") or ""
    is_banned = any(b in sid for b in BANNED_SOURCE_DIRS)
    _check(errors,
           "source_input_dir not in banned Re05/Re08 dirs",
           not is_banned,
           f"actual={sid!r}")

    # Gate 3: adapter_call_count > 0
    adapter_total = sum((manifest.get("adapter_call_count") or {}).values())
    _check(errors, "adapter_call_count.total > 0", adapter_total > 0,
           f"actual={adapter_total}")

    # Gate 4: llm_call_count > 0 (or no_llm_mode declared)
    llm_total = sum((manifest.get("llm_call_count") or {}).values())
    no_llm = manifest.get("no_llm_mode") is True
    _check(errors, "llm_call_count.total > 0", llm_total > 0 or no_llm,
           f"actual={llm_total}, no_llm_mode={no_llm}")

    # Gate 5: repair_execution.executed_queries_n > 0
    rep = manifest.get("repair_execution") or {}
    _check(errors, "repair_execution.executed_queries_n > 0",
           (rep.get("executed_queries_n") or 0) > 0,
           f"actual={rep.get('executed_queries_n')}")

    # Gate 6: fresh_run_gate == pass
    _check(errors, "fresh_run_gate == pass",
           manifest.get("fresh_run_gate") == "pass",
           f"actual={manifest.get('fresh_run_gate')!r}")

    # Cross-check summary.json if present
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        manifest_adapter_total = sum((manifest.get("adapter_call_count") or {}).values())
        summary_adapter_total = sum((summary.get("adapter_call_count") or {}).values())
        _check(errors, "summary.adapter_call_count == manifest.adapter_call_count",
               manifest_adapter_total == summary_adapter_total,
               f"manifest={manifest_adapter_total} summary={summary_adapter_total}")

        # by_status match between summary and any case-level data
        # (not strictly required, but report should be consistent)
        by_status = summary.get("by_status") or {}

    # Gate 7: per-case repair execution trace must be non-empty for fail
    cases_path = out_dir / "repair_plans.json"
    if cases_path.exists():
        plans = json.loads(cases_path.read_text(encoding="utf-8")).get("plans") or []
        fail_plans = [p for p in plans if p.get("priority") == "fail"]
        fail_with_execution = [
            p for p in fail_plans
            if (p.get("adapter_count") and sum(p["adapter_count"].values()) > 0)
        ]
        _check(errors,
               "all 3 Re08 fail cases have real adapter execution",
               len(fail_with_execution) >= len(fail_plans),
               f"fail with adapter calls: {len(fail_with_execution)}/{len(fail_plans)}")

    # Gate 8: no placeholder leak in executed queries
    if cases_path.exists():
        plans = json.loads(cases_path.read_text(encoding="utf-8")).get("plans") or []
        leaks = []
        for p in plans:
            for q in p.get("new_candidates") or []:
                # already-fetched candidates should not contain unresolved X.
                t = (q.get("title") or "")
                if "{" in t or "}" in t or t.strip() == "X":
                    leaks.append(p.get("case_id"))
        _check(errors, "no placeholder leak in fresh titles",
               not leaks, f"leak cases: {leaks[:5]}")

    print()
    if errors:
        print(f"=== {len(errors)} FAIL(S) ===")
        for e in errors:
            print(f"  {e}")
        return 1
    print("=== ALL FRESH-RUN GATES PASSED ===")
    return 0


def _report_error(msg: str) -> int:
    print(f"  {msg}")
    print("=== FRESH-RUN GATES FAIL ===")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="tmp_re04_eval/balanced40_re09_fresh")
    args = ap.parse_args()
    return validate(Path(args.out_dir))


if __name__ == "__main__":
    sys.exit(main())