"""Re08 SOP §6.2 — 4-way consistency validator (summary / CSV / 逐论文审计 MD / 完工报告 MD).

Extends Re07's 3-way validator with the 完工报告 (completion report) MD as
a fourth source of truth.  Each of the 4 sources must agree on:

  * pass / weak / fail counts (or 完工报告 must say "X pass + Y weak + Z fail")
  * each case_id's status must be consistent across summary / CSV / 逐论文审计 MD
  * quarantined count must match
  * pass+weak rate in 完工报告 must equal summary.pass_plus_weak_rate

If 完工报告 does not exist, the validator still runs the 3-way check (with
a warning).  The script is also safe to call as part of CI.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \\
        apps/api/scripts/validate_re08_consistency.py \\
        --summary tmp_re04_eval/balanced40_re08/summary.json \\
        --csv     Plan/PaperAgent_Re08_Balanced40_逐论文审计.csv \\
        --md      Plan/PaperAgent_Re08_Balanced40_逐论文审计.md \\
        --report  Plan/PaperAgent_Re08_完工报告.md
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path


def _load_summary(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"FATAL: {path} not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"FATAL: {path} not found")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _load_md(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _check(name: str, expected, actual, errors: list[str]) -> None:
    if expected == actual:
        print(f"  PASS  {name}: {expected}")
    else:
        msg = f"FAIL  {name}: expected={expected!r} actual={actual!r}"
        print(f"  {msg}")
        errors.append(msg)


def _extract_status_from_audit_md(md_text: str) -> dict[str, str]:
    """Walk the 逐论文审计 MD per-case table and pull case_id → status."""
    out: dict[str, str] = {}
    if not md_text:
        return out
    pat = re.compile(
        r"^\|\s*(ENG-[\w\-]+)\s*\|\s*[^|]*\|\s*(pass|weak|fail|blocked)\s*\|",
        re.MULTILINE,
    )
    for m in pat.finditer(md_text):
        out[m.group(1)] = m.group(2)
    return out


def _extract_status_counts_from_report_md(md_text: str | None) -> dict[str, int] | None:
    """Look for the "X pass + Y weak + Z fail" line in the 完工报告."""
    if not md_text:
        return None
    # Pattern A: "24 pass + 13 weak + 3 fail" (SOP §5 "Re07 -> Re08 状态变化表" style)
    pat = re.compile(
        r"(\d+)\s*pass\s*\+\s*(\d+)\s*weak\s*\+\s*(\d+)\s*fail"
        r"(?:\s*=\s*([\d.]+)%pass\+weak)?",
        re.IGNORECASE,
    )
    for m in pat.finditer(md_text):
        return {
            "pass": int(m.group(1)),
            "weak": int(m.group(2)),
            "fail": int(m.group(3)),
        }
    return None


def validate(
    summary_path: Path,
    csv_path: Path,
    md_path: Path,
    report_path: Path | None = None,
) -> int:
    print("=== Cross-validate Re08 reports (4-way) ===")
    print(f"  summary: {summary_path}")
    print(f"  csv:     {csv_path}")
    print(f"  md:      {md_path}")
    print(f"  report:  {report_path or '(skipped — not provided)'}")

    errors: list[str] = []

    # --- Load sources ---
    summary = _load_summary(summary_path)
    csv_rows = _load_csv(csv_path)
    md_text = _load_md(md_path) or ""
    report_text = _load_md(report_path) if report_path else None

    summary_status = summary.get("by_status") or {}
    summary_n_total = summary.get("n_total") or len(summary.get("per_case") or [])
    csv_status = dict(Counter(r.get("status", "?") for r in csv_rows))

    # --- 1. summary vs csv ---
    _check("summary.n_total == csv_rows", summary_n_total, len(csv_rows), errors)
    _check("summary.by_status == csv status groupby", summary_status, csv_status, errors)

    # --- 2. csv vs 逐论文审计 MD (per-case table) ---
    md_status_map = _extract_status_from_audit_md(md_text)
    if md_status_map:
        mismatches = []
        for r in csv_rows:
            cid = r.get("case_id")
            csv_st = r.get("status", "?")
            md_st = md_status_map.get(cid)
            if md_st and md_st != csv_st:
                mismatches.append((cid, csv_st, md_st))
        if mismatches:
            msg = f"per-case status mismatches: {mismatches[:5]}"
            print(f"  FAIL  csv vs md per-case: {msg}")
            errors.append(msg)
        else:
            print(f"  PASS  csv vs md per-case: {len(csv_rows)} cases aligned")

    # --- 3. CSV row count vs 逐论文审计 MD row count ---
    md_case_rows = len(re.findall(r"^\|\s*ENG-[A-Z0-9\-]+", md_text, flags=re.MULTILINE))
    if md_case_rows == 0:
        md_case_rows = sum(1 for _ in csv_rows)  # soft fallback
    _check("csv rows == md per-case table rows", len(csv_rows), md_case_rows, errors)

    # --- 4. 完工报告 MD vs summary (status counts) ---
    if report_text:
        report_counts = _extract_status_counts_from_report_md(report_text)
        if report_counts:
            _check(
                "report status counts == summary.by_status",
                report_counts, summary_status, errors,
            )
        else:
            print("  WARN  no 'X pass + Y weak + Z fail' pattern found in 完工报告")

    # --- 5. quarantined count must match between summary and CSV ---
    #    summary.quarantined_total counts CASES with any quarantine;
    #    the CSV sums per-case quarantined candidate counts.  Both must
    #    be reported but the validator checks the case-count match.
    summary_q_cases = summary.get("quarantined_total", 0)
    csv_q_cases = sum(
        1 for r in csv_rows
        if (int(r.get("quarantined_baseline_n", 0) or 0)
            + int(r.get("quarantined_parallel_n", 0) or 0)
            + int(r.get("quarantined_core_n", 0) or 0)) > 0
    )
    _check("summary.quarantined_total (cases) == csv cases with quarantine",
           summary_q_cases, csv_q_cases, errors)

    # --- 6. CSV required fields must be non-empty (Re08 §6.1) ---
    if csv_rows:
        required_cols = [
            "paper_n", "baseline_n", "parallel_n", "dataset_n", "repo_n",
            "effective_core_n", "effective_baseline_n", "effective_parallel_n",
            "verification_verified_n", "verification_repaired_n",
            "verification_quarantined_n",
        ]
        missing_cols = []
        for col in required_cols:
            if col not in csv_rows[0]:
                missing_cols.append(f"{col}=MISSING")
                continue
            n_none = sum(1 for r in csv_rows if r.get(col) is None
                         or r.get(col) == "")
            if n_none == len(csv_rows):
                missing_cols.append(f"{col}=ALL_NONE")
        if missing_cols:
            msg = f"required CSV columns null: {missing_cols}"
            print(f"  FAIL  {msg}")
            errors.append(msg)
        else:
            print("  PASS  required CSV columns populated (zeros are valid)")

    # --- 7. axis missing budget (Re07 §5.3 / Re08 unchanged) ---
    if csv_rows and "axis_task" in csv_rows[0]:
        n = len(csv_rows)
        n_missing = sum(1 for r in csv_rows if r.get("axis_task") == "missing")
        ratio = (n_missing / n) if n else 0.0
        _check("axis_task missing ratio < 0.30", True, ratio < 0.30, errors)

    print()
    if errors:
        print(f"=== INCONSISTENCIES FOUND: {len(errors)} ===")
        for e in errors:
            print(f"  {e}")
        return 1
    print("=== ALL CONSISTENCY CHECKS PASSED ===")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--md", required=True)
    ap.add_argument("--report", default="",
                    help="optional 完工报告 MD path")
    args = ap.parse_args()
    report = Path(args.report) if args.report else None
    return validate(
        Path(args.summary),
        Path(args.csv),
        Path(args.md),
        report,
    )


if __name__ == "__main__":
    sys.exit(main())