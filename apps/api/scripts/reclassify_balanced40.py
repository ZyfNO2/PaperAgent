"""Re07 re-classify Balanced40 raw dumps with Re07 eval.

Reads ``tmp_re04_eval/balanced40/`` (Re05 LLM-online raw dumps) and
re-classifies each case with the new Re07 scoring rules.  Outputs:

  tmp_re04_eval/balanced40_re07/<batch>/<case>.json  per-case audit
  tmp_re04_eval/balanced40_re07/<batch>/summary.json  per-batch aggregate
  tmp_re04_eval/balanced40_re07/summary.json          40-case aggregate
  tmp_re04_eval/balanced40_re07/report.md             per-case table

Usage:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \\
        apps/api/scripts/reclassify_balanced40.py \\
        --in-dir tmp_re04_eval/balanced40 \\
        --out-dir tmp_re04_eval/balanced40_re07
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.agents.eval import (  # noqa: E402
    aggregate_metrics,
    compute_resource_status,
    write_markdown_report,
)


def _coerce(o):
    if hasattr(o, "to_dict"):
        return o.to_dict()
    if hasattr(o, "as_list"):
        return o.as_list()
    if isinstance(o, dict):
        return {k: _coerce(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_coerce(x) for x in o]
    return o


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", default="tmp_re04_eval/balanced40")
    ap.add_argument("--out-dir", default="tmp_re04_eval/balanced40_re07")
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case: list[dict] = []
    batches = sorted([d for d in in_dir.iterdir()
                      if d.is_dir() and (d.name.startswith("r") or
                                          d.name.startswith("batch"))])
    print(f"Found {len(batches)} batches: {[b.name for b in batches]}")

    for batch in batches:
        out_batch = out_dir / batch.name
        out_batch.mkdir(parents=True, exist_ok=True)
        batch_per_case: list[dict] = []
        for raw_path in sorted(batch.glob("ENG-THESIS-*.json")):
            case_id = raw_path.stem
            try:
                result = json.loads(raw_path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"  [skip] {case_id}: cannot parse ({exc})")
                continue
            try:
                status = compute_resource_status(result)
            except Exception as exc:
                print(f"  [skip] {case_id}: compute_resource_status failed ({exc})")
                continue
            title = result.get("title") or result.get("raw_topic") or case_id
            status["case_id"] = case_id
            status["title"] = title
            status["source_batch"] = batch.name
            (out_batch / f"{case_id}.json").write_text(
                json.dumps(status, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            batch_per_case.append(status)
            per_case.append(status)
            print(
                f"  [{batch.name}] {case_id}: {status.get('status')} "
                f"paper={status.get('paper_n')} "
                f"eff_baseline={status.get('effective_baseline_n')} "
                f"topic_ds={status.get('topic_dataset_n')} "
                f"quarantined={status.get('quarantined_baseline_n', 0)} "
                f"axis={status.get('axis_status')}"
            )

        (out_batch / "summary.json").write_text(
            json.dumps({
                "batch": batch.name,
                "n": len(batch_per_case),
                "per_case": [{
                    "case_id": c.get("case_id"),
                    "title": c.get("title"),
                    "status": c.get("status"),
                    "paper_n": c.get("paper_n"),
                    "effective_baseline_n": c.get("effective_baseline_n"),
                    "effective_parallel_n": c.get("effective_parallel_n"),
                    "effective_core_n": c.get("effective_core_n"),
                    "quarantined_total": (
                        c.get("quarantined_baseline_n", 0)
                        + c.get("quarantined_parallel_n", 0)
                        + c.get("quarantined_core_n", 0)
                    ),
                    "axis_status": c.get("axis_status"),
                    "reason": c.get("reason"),
                } for c in batch_per_case],
            }, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    agg = aggregate_metrics(per_case)
    summary = {
        "audit_version": "Re07",
        "input_dir": str(in_dir),
        "n_total": len(per_case),
        "by_status": agg["by_status"],
        "pass_rate": agg["pass_rate"],
        "pass_plus_weak_rate": agg["weak_or_pass_rate"],
        "quarantined_total": agg["quarantined_total"],
        "axis_not_evaluable_cases": agg["axis_not_evaluable_cases"],
        "critical_consistency_error_cases": agg["critical_consistency_error_cases"],
        "metadata_mismatch_cases": agg["metadata_mismatch_cases"],
        "core_zero_pass_cases": agg["core_zero_pass_cases"],
        "sop_5_3_pass": (
            agg["weak_or_pass_rate"] >= 0.90
            and agg["core_zero_pass_cases"] == 0
        ),
        "per_case": [{
            "case_id": c.get("case_id"),
            "title": c.get("title"),
            "status": c.get("status"),
            "paper_n": c.get("paper_n"),
            "effective_baseline_n": c.get("effective_baseline_n"),
            "effective_parallel_n": c.get("effective_parallel_n"),
            "effective_core_n": c.get("effective_core_n"),
            "topic_dataset_n": c.get("topic_dataset_n"),
            "quarantined_total": (
                c.get("quarantined_baseline_n", 0)
                + c.get("quarantined_parallel_n", 0)
                + c.get("quarantined_core_n", 0)
            ),
            "axis_status": c.get("axis_status"),
            "source_batch": c.get("source_batch"),
            "reason": c.get("reason"),
        } for c in per_case],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    write_markdown_report(
        per_case, str(out_dir / "report.md"),
        source_url=f"{in_dir} (Re05 LLM-online raw dumps, Re07 re-audit)",
    )

    print("\n=== Re07 Balanced40 re-audit done ===")
    print(f"  pass:       {agg['by_status'].get('pass', 0)}/{len(per_case)}")
    print(f"  weak:       {agg['by_status'].get('weak', 0)}")
    print(f"  fail:       {agg['by_status'].get('fail', 0)}")
    print(f"  blocked:    {agg['by_status'].get('blocked', 0)}")
    print(f"  pass+weak:  {agg['weak_or_pass_rate']:.1%}")
    print(f"  quarantined_total cases: {agg['quarantined_total']}")
    print(f"  axis_not_evaluable cases: {agg['axis_not_evaluable_cases']}")
    print(f"  SOP §5.3 pass: {summary['sop_5_3_pass']}")
    print(f"\n  summary: {out_dir}/summary.json")
    print(f"  report:  {out_dir}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())