"""Re07 SOP §3.6 / §5.2 Task D — cross-validate summary.json / case CSV / md report.

Checks:
  1. summary.json by_status counts == case CSV status groupby counts.
  2. summary.json n_total == case CSV row count.
  3. case CSV row count == md report per-case row count.
  4. summary.json sop_pass flag (if present) matches the md report
     "PASS / FAIL" claim.

Exits non-zero on the first inconsistency so the Re07 acceptance gate
fails loudly.  The script is also safe to call as part of CI.

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \\
        apps/api/scripts/validate_re_report_consistency.py \\
        --summary tmp_re04_eval/balanced40_re07/summary.json \\
        --csv     Plan/PaperAgent_Re07_Balanced40_逐论文审计.csv \\
        --md      Plan/PaperAgent_Re07_Balanced40_逐论文审计.md
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


def _load_md(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"FATAL: {path} not found")
    return path.read_text(encoding="utf-8")


def _check(name: str, expected, actual, errors: list[str]) -> None:
    if expected == actual:
        print(f"  PASS  {name}: {expected}")
    else:
        msg = f"FAIL  {name}: expected={expected!r} actual={actual!r}"
        print(f"  {msg}")
        errors.append(msg)


def validate(summary_path: Path, csv_path: Path, md_path: Path) -> int:
    print(f"=== Cross-validate Re07 reports ===")
    print(f"  summary: {summary_path}")
    print(f"  csv:     {csv_path}")
    print(f"  md:      {md_path}")

    errors: list[str] = []
    summary = _load_summary(summary_path)
    csv_rows = _load_csv(csv_path)
    md_text = _load_md(md_path)

    # 1. by_status from summary vs CSV groupby
    summary_status = summary.get("by_status") or {}
    summary_n_total = summary.get("n_total") or len(summary.get("per_case") or [])
    csv_status = dict(Counter(r.get("status", "?") for r in csv_rows))

    _check(
        "summary.n_total == csv_rows",
        summary_n_total,
        len(csv_rows),
        errors,
    )
    _check(
        "summary.by_status == csv status groupby",
        summary_status,
        csv_status,
        errors,
    )

    # 2. csv row count == md per-case table row count.
    #    Heuristic: count markdown table rows that begin with "| ENG-" (the
    #    case_id prefix used in PaperAgent fixtures).
    md_case_rows = len(re.findall(r"^\|\s*ENG-[A-Z0-9\-]+", md_text, flags=re.MULTILINE))
    if md_case_rows == 0:
        # fall back: count any table row containing a status keyword
        md_case_rows = len(re.findall(
            r"^\|[^|]*?(?:pass|weak|fail|blocked)[^|]*?\|",
            md_text, flags=re.MULTILINE,
        ))
    _check(
        "csv rows == md per-case table rows",
        len(csv_rows),
        md_case_rows,
        errors,
    )

    # 3. summary.sop_pass (if present) matches the md narrative.
    sop_pass = summary.get("sop_pass")
    if sop_pass is not None:
        md_says_pass = "SOP §6.3 pass" in md_text or "SOP §5.3 pass" in md_text
        if sop_pass:
            _check(
                "summary.sop_pass=True implies md says SOP pass",
                True, md_says_pass, errors,
            )
        else:
            # md should NOT claim SOP pass.
            _check(
                "summary.sop_pass=False implies md does NOT claim SOP pass",
                False, md_says_pass, errors,
            )

    # 4. axis missing budget check (Re07 §5.3 — axis_task missing < 30%).
    #    If the candidate CSV is available we re-compute the axis_task
    #    missing ratio; otherwise this check is skipped.
    if csv_rows and "axis_task" in csv_rows[0]:
        n = len(csv_rows)
        n_missing = sum(1 for r in csv_rows if r.get("axis_task") == "missing")
        ratio = (n_missing / n) if n else 0.0
        _check(
            "axis_task missing ratio < 0.30 (Re07 §5.3)",
            True, ratio < 0.30, errors,
        )

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
    args = ap.parse_args()
    return validate(
        Path(args.summary),
        Path(args.csv),
        Path(args.md),
    )


if __name__ == "__main__":
    sys.exit(main())