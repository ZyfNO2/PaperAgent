"""Compare independently executed Gate L variants and propose provisional routing."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from gate_l_acceptance_v3 import verify_manifest


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _load_variant(entry: dict[str, Any]) -> dict[str, Any]:
    strategy_id = entry.get("strategy_id")
    if not isinstance(strategy_id, str) or not strategy_id.strip():
        raise ValueError("every variant needs strategy_id")
    decision_path = Path(str(entry.get("decision")))
    manifest_path = Path(str(entry.get("manifest")))
    run_record_path = Path(str(entry.get("run_record")))
    evidence_dir = Path(str(entry.get("evidence_dir")))
    decision = _read(decision_path)
    manifest, cases = verify_manifest(manifest_path)
    run_record = _read(run_record_path)
    identity = run_record.get("execution_identity")
    if not isinstance(identity, dict):
        identity = {}
    cases_by_id = {case["case_id"]: case for case in cases}
    decision_cases = decision.get("cases")
    if not isinstance(decision_cases, list):
        raise ValueError(f"{strategy_id}: decision.cases missing")
    if {item.get("case_id") for item in decision_cases if isinstance(item, dict)} != set(
        cases_by_id
    ):
        raise ValueError(f"{strategy_id}: decision does not cover frozen cases")

    total_cost = 0.0
    cost_complete = True
    for case_id in cases_by_id:
        path = evidence_dir / f"{case_id}.json"
        if not path.exists():
            cost_complete = False
            continue
        telemetry = _read(path).get("telemetry")
        cost = telemetry.get("estimated_cost_usd") if isinstance(telemetry, dict) else None
        if not isinstance(cost, int | float) or isinstance(cost, bool):
            cost_complete = False
            continue
        total_cost += float(cost)

    formal_evidence = (
        run_record.get("formal_run") is True
        and run_record.get("case_count") == len(cases)
        and run_record.get("selected_case_ids") in ([], None)
        and identity.get("clean_tree") is True
        and decision.get("contract_version") == "gate-l.acceptance.v3"
        and decision.get("deterministic_summary", {}).get("audit_complete") is True
        and not decision.get("required_adjudications")
    )
    return {
        "strategy_id": strategy_id,
        "decision": decision,
        "manifest": manifest,
        "cases_by_id": cases_by_id,
        "run_record": run_record,
        "identity": {
            "provider": identity.get("provider"),
            "model": identity.get("model"),
            "base_url": identity.get("base_url"),
            "repo_sha": identity.get("repo_sha"),
            "strategy_profile": identity.get("strategy_profile"),
        },
        "formal_evidence": formal_evidence,
        "total_cost_usd": round(total_cost, 8) if cost_complete else None,
    }


def _segment_metrics(variant: dict[str, Any], case_ids: set[str]) -> dict[str, Any]:
    rows = [row for row in variant["decision"]["cases"] if row.get("case_id") in case_ids]
    if not rows:
        return {
            "case_count": 0,
            "accepted_rate": None,
            "deterministic_rate": None,
            "human_rate": None,
            "mean_human_score": None,
        }
    return {
        "case_count": len(rows),
        "accepted_rate": sum(bool(row.get("accepted")) for row in rows) / len(rows),
        "deterministic_rate": sum(bool(row.get("deterministic_accepted")) for row in rows)
        / len(rows),
        "human_rate": sum(bool(row.get("human_accepted")) for row in rows) / len(rows),
        "mean_human_score": _mean(
            [
                float(row["mean_score"])
                for row in rows
                if isinstance(row.get("mean_score"), int | float)
            ]
        ),
    }


def _rank_key(item: dict[str, Any]) -> tuple[float, float, float, float]:
    metrics = item["metrics"]
    cost = item.get("total_cost_usd")
    return (
        float(metrics.get("accepted_rate") or 0.0),
        float(metrics.get("deterministic_rate") or 0.0),
        float(metrics.get("mean_human_score") or 0.0),
        -float(cost) if isinstance(cost, int | float) else float("-inf"),
    )


def compare(matrix_path: Path) -> dict[str, Any]:
    matrix = _read(matrix_path)
    raw_variants = matrix.get("variants")
    if not isinstance(raw_variants, list) or len(raw_variants) < 2:
        raise ValueError("matrix requires at least two variants")
    variants = [_load_variant(entry) for entry in raw_variants if isinstance(entry, dict)]
    strategy_ids = [variant["strategy_id"] for variant in variants]
    if len(strategy_ids) != len(set(strategy_ids)):
        raise ValueError("strategy_id values must be unique")

    holdout_keys = {
        (
            variant["manifest"]["version"],
            variant["manifest"]["case_file_sha256"],
        )
        for variant in variants
    }
    same_holdout = len(holdout_keys) == 1
    categories = ("in_domain", "ood", "insufficient_evidence", "adversarial")
    tag_cases: dict[str, set[str]] = defaultdict(set)
    reference_cases = variants[0]["cases_by_id"]
    for case_id, case in reference_cases.items():
        for tag in case.get("acceptance_tags", []):
            if isinstance(tag, str) and tag:
                tag_cases[tag].add(case_id)

    per_variant: list[dict[str, Any]] = []
    for variant in variants:
        all_ids = set(variant["cases_by_id"])
        per_variant.append(
            {
                "strategy_id": variant["strategy_id"],
                "identity": variant["identity"],
                "formal_evidence": variant["formal_evidence"],
                "decision": variant["decision"].get("decision"),
                "total_cost_usd": variant["total_cost_usd"],
                "overall": _segment_metrics(variant, all_ids),
                "by_category": {
                    category: _segment_metrics(
                        variant,
                        {
                            case_id
                            for case_id, case in variant["cases_by_id"].items()
                            if case.get("category") == category
                        },
                    )
                    for category in categories
                },
                "by_tag": {
                    tag: _segment_metrics(variant, ids) for tag, ids in sorted(tag_cases.items())
                },
            }
        )

    eligible = {item["strategy_id"]: item for item in per_variant if item["formal_evidence"]}

    def winner_for(segment: str, name: str) -> dict[str, Any] | None:
        candidates: list[dict[str, Any]] = []
        for item in eligible.values():
            metrics = item[segment][name] if segment != "overall" else item["overall"]
            if metrics.get("case_count", 0) < 2:
                continue
            candidates.append(
                {
                    "strategy_id": item["strategy_id"],
                    "metrics": metrics,
                    "total_cost_usd": item["total_cost_usd"],
                }
            )
        if not candidates:
            return None
        return max(candidates, key=_rank_key)

    global_candidates = [
        {
            "strategy_id": item["strategy_id"],
            "metrics": item["overall"],
            "total_cost_usd": item["total_cost_usd"],
        }
        for item in eligible.values()
    ]
    global_ranking = sorted(global_candidates, key=_rank_key, reverse=True)
    routing_ready = same_holdout and len(eligible) >= 2
    return {
        "comparison_version": "gate-l.variant-comparison.v1",
        "same_frozen_holdout": same_holdout,
        "eligible_variant_count": len(eligible),
        "routing_status": (
            "PROVISIONAL_REQUIRES_FRESH_CONFIRMATION"
            if routing_ready
            else "INSUFFICIENT_FORMAL_VARIANTS"
        ),
        "warning": (
            "Selections are exploratory. Freeze routing rules before evaluating them "
            "on a fresh confirmation holdout. Do not report same-holdout selection "
            "as final acceptance."
        ),
        "global_ranking": global_ranking,
        "best_by_category": {
            category: winner_for("by_category", category) for category in categories
        },
        "best_by_tag": {tag: winner_for("by_tag", tag) for tag in sorted(tag_cases)},
        "variants": per_variant,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compare(args.matrix)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Gate L variant comparison error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
