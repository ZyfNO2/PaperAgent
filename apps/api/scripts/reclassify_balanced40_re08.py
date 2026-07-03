"""Re08 re-audit Balanced40 with verifier + repair + gap-planner.

Reads ``tmp_re04_eval/balanced40/`` (Re05 LLM-online raw dumps) and
re-classifies each case through the Re08 eval pipeline.  For fail / weak
cases, attaches a ``repair_plan`` and ``verification_summary`` derived
from the rule layer.

Outputs (per Re08 SOP §11):

  tmp_re04_eval/balanced40_re08/<batch>/<case>.json     per-case audit
  tmp_re04_eval/balanced40_re08/<batch>/summary.json    per-batch
  tmp_re04_eval/balanced40_re08/summary.json            40-case aggregate
  tmp_re04_eval/balanced40_re08/report.md               per-case table
  tmp_re04_eval/balanced40_re08/repair_plans.json       aggregated repair plans
  tmp_re04_eval/balanced40_re08/verification_stats.json aggregated verifier stats

Usage:
    PYTHONIOENCODING=utf-8 /g/PaperAgent/.venv/Scripts/python.exe \\
        /g/PaperAgent/apps/api/scripts/reclassify_balanced40_re08.py \\
        --in-dir tmp_re04_eval/balanced40 \\
        --out-dir tmp_re04_eval/balanced40_re08
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
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
from app.services.agents.gap_repair_planner import (  # noqa: E402
    build_repair_plan,
    rule_repair_plan,
)
from app.services.agents.candidate_verifier import (  # noqa: E402
    verify_bucket,
)


def _attach_repair_info(status: dict, raw: dict) -> dict:
    """Attach repair_plan + verification_stats to a per-case status."""
    # Pull the same topic_atoms _build_topic_atoms would compute.
    from app.services.agents.eval import _build_topic_atoms
    synthesis = raw.get("synthesis") or {}
    topic_atoms = _build_topic_atoms(synthesis, raw)
    gap_reasons = (
        list(status.get("evidence_gap_reasons") or [])
        + list(status.get("axis_missing_reasons") or [])
    )
    topic = raw.get("title") or raw.get("raw_topic") or status.get("case_id")
    plan = build_repair_plan(
        gap_reasons=gap_reasons,
        topic_atoms=topic_atoms,
        topic=topic,
        candidate_summary=f"paper_n={status.get('paper_n')}, "
                          f"baseline_n={status.get('baseline_n')}, "
                          f"dataset_n={status.get('dataset_n')}, "
                          f"repo_n={status.get('repo_n')}",
    )
    status["repair_plan"] = plan
    status["re08_topic_atoms_present"] = bool(topic_atoms)

    # Run the rule-layer verifier on each bucket.
    candidate_pool = synthesis.get("candidate_pool") or {}
    paper_groups = synthesis.get("paper_groups") or {}

    def _gather(bucket: str) -> list[dict]:
        items = []
        if isinstance(candidate_pool, dict):
            items.extend(candidate_pool.get(bucket) or [])
        if isinstance(paper_groups, dict):
            if bucket == "baseline":
                items.extend(paper_groups.get("baseline") or [])
            if bucket == "parallel":
                items.extend(paper_groups.get("parallel") or [])
        return items

    per_bucket_verifications: dict[str, list[dict]] = {}
    for bucket_name in ("core", "baseline", "parallel", "dataset", "repo"):
        members = _gather(bucket_name)
        if not members:
            per_bucket_verifications[bucket_name] = []
            continue
        results = verify_bucket(bucket_name, members, topic_atoms)
        per_bucket_verifications[bucket_name] = [r.to_dict() for r in results]

    verification_stats = Counter()
    for bn, rs in per_bucket_verifications.items():
        for r in rs:
            verification_stats[r.get("verification_status", "unknown")] += 1
    status["verification_stats_by_bucket"] = {
        bn: dict(Counter(r.get("verification_status", "unknown") for r in rs))
        for bn, rs in per_bucket_verifications.items()
    }
    status["verification_stats_total"] = dict(verification_stats)
    return status


async def _process_case(raw: dict, case_id: str, batch_name: str,
                        out_batch_dir: Path) -> dict | None:
    try:
        status = compute_resource_status(raw)
    except Exception as exc:
        print(f"  [skip] {case_id}: compute_resource_status failed ({exc})")
        return None
    status = _attach_repair_info(status, raw)
    title = raw.get("title") or raw.get("raw_topic") or case_id
    status["case_id"] = case_id
    status["title"] = title
    status["source_batch"] = batch_name
    status["re08_audit_version"] = "Re08"

    (out_batch_dir / f"{case_id}.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return status


async def main_async(args) -> int:
    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case: list[dict] = []
    batches = sorted([d for d in in_dir.iterdir()
                      if d.is_dir() and (d.name.startswith("r")
                                          or d.name.startswith("batch"))])
    print(f"Found {len(batches)} batches: {[b.name for b in batches]}")

    for batch in batches:
        out_batch = out_dir / batch.name
        out_batch.mkdir(parents=True, exist_ok=True)
        batch_per_case: list[dict] = []
        for raw_path in sorted(batch.glob("ENG-THESIS-*.json")):
            case_id = raw_path.stem
            try:
                raw = json.loads(raw_path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"  [skip] {case_id}: cannot parse ({exc})")
                continue
            status = await _process_case(raw, case_id, batch.name, out_batch)
            if status is None:
                continue
            batch_per_case.append(status)
            per_case.append(status)
            print(
                f"  [{batch.name}] {case_id}: {status.get('status')} "
                f"paper={status.get('paper_n')} "
                f"eff_baseline={status.get('effective_baseline_n')} "
                f"veri_verified={status.get('verification_verified_n')} "
                f"veri_repaired={status.get('verification_repaired_n')} "
                f"veri_quarantined={status.get('verification_quarantined_n')} "
                f"repair_plan_items={len(status.get('repair_plan', {}).get('repair_plan', []))}"
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
                    "verification_verified_n": c.get("verification_verified_n"),
                    "verification_repaired_n": c.get("verification_repaired_n"),
                    "verification_quarantined_n": c.get("verification_quarantined_n"),
                    "axis_status": c.get("axis_status"),
                    "reason": c.get("reason"),
                } for c in batch_per_case],
            }, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    agg = aggregate_metrics(per_case)
    summary = {
        "audit_version": "Re08",
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
        "sop_pass": (
            agg["weak_or_pass_rate"] >= 0.90
            and agg["core_zero_pass_cases"] == 0
        ),
        "per_case": [{
            "case_id": c.get("case_id"),
            "title": c.get("title"),
            "status": c.get("status"),
            "paper_n": c.get("paper_n"),
            "baseline_n": c.get("baseline_n"),
            "parallel_n": c.get("parallel_n"),
            "dataset_n": c.get("dataset_n"),
            "repo_n": c.get("repo_n"),
            "topic_dataset_n": c.get("topic_dataset_n"),
            "core_n": c.get("core_n"),
            "effective_core_n": c.get("effective_core_n"),
            "effective_baseline_n": c.get("effective_baseline_n"),
            "effective_parallel_n": c.get("effective_parallel_n"),
            "quarantined_baseline_n": c.get("quarantined_baseline_n"),
            "quarantined_parallel_n": c.get("quarantined_parallel_n"),
            "quarantined_core_n": c.get("quarantined_core_n"),
            "verification_verified_n": c.get("verification_verified_n"),
            "verification_repaired_n": c.get("verification_repaired_n"),
            "verification_quarantined_n": c.get("verification_quarantined_n"),
            "verification_not_found_n": c.get("verification_not_found_n"),
            "critical_consistency_error_n": c.get("critical_consistency_error_n"),
            "metadata_mismatch_n": c.get("metadata_mismatch_n"),
            "off_topic_core_n": c.get("off_topic_core_n"),
            "axis_status": c.get("axis_status"),
            "source_batch": c.get("source_batch"),
            "reason": c.get("reason"),
            "notes": c.get("notes"),
            "evidence_gap_reasons": c.get("evidence_gap_reasons"),
            "axis_missing_reasons": c.get("axis_missing_reasons"),
        } for c in per_case],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # Aggregated repair plans + verification stats.
    repair_plans = []
    verification_stats_total = Counter()
    for c in per_case:
        plan = c.get("repair_plan") or {}
        if plan.get("repair_plan"):
            repair_plans.append({
                "case_id": c.get("case_id"),
                "title": c.get("title"),
                "status": c.get("status"),
                "reason": c.get("reason"),
                "plan": plan,
            })
        for k, v in (c.get("verification_stats_total") or {}).items():
            verification_stats_total[k] += v
    (out_dir / "repair_plans.json").write_text(
        json.dumps({
            "n_with_plan": len(repair_plans),
            "plans": repair_plans,
        }, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (out_dir / "verification_stats.json").write_text(
        json.dumps({
            "total_verifications": sum(verification_stats_total.values()),
            "by_status": dict(verification_stats_total),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    write_markdown_report(
        per_case, str(out_dir / "report.md"),
        source_url=f"{in_dir} (Re05 LLM-online raw dumps, Re08 re-audit)",
    )

    print("\n=== Re08 Balanced40 re-audit done ===")
    print(f"  pass:       {agg['by_status'].get('pass', 0)}/{len(per_case)}")
    print(f"  weak:       {agg['by_status'].get('weak', 0)}")
    print(f"  fail:       {agg['by_status'].get('fail', 0)}")
    print(f"  blocked:    {agg['by_status'].get('blocked', 0)}")
    print(f"  pass+weak:  {agg['weak_or_pass_rate']:.1%}")
    print(f"  quarantined_total cases: {agg['quarantined_total']}")
    print(f"  axis_not_evaluable cases: {agg['axis_not_evaluable_cases']}")
    print(f"  SOP §8 pass: {summary['sop_pass']}")
    print(f"  repair_plans attached: {len(repair_plans)}")
    print(f"  verification_stats_total: {dict(verification_stats_total)}")
    print(f"\n  summary: {out_dir}/summary.json")
    print(f"  report:  {out_dir}/report.md")
    print(f"  repair_plans: {out_dir}/repair_plans.json")
    print(f"  verification_stats: {out_dir}/verification_stats.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", default="tmp_re04_eval/balanced40")
    ap.add_argument("--out-dir", default="tmp_re04_eval/balanced40_re08")
    args = ap.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())