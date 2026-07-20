from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from paperagent.claw_academic_benchmark import evaluate_case, load_gold_dataset
from paperagent.claw_benchmark_runtime import execute_benchmark_case
from paperagent.literature.factory import LiteratureProviderSettings, build_literature_runtime
from paperagent.providers.config import load_provider_config
from paperagent.providers.runtime_factory import build_llm_provider


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run exactly one CLAW case through the real PaperAgent workflow."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("evals/claw_academic_tailoring_v1"),
    )
    parser.add_argument(
        "--case-id",
        default="at-001-uav-small-object-lightweight",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--minimum-score", type=int, default=80)
    parser.add_argument("--max-llm-calls", type=int, default=12)
    parser.add_argument("--provider-call-budget", type=int, default=8)
    parser.add_argument("--verification-call-budget", type=int, default=16)
    return parser


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _select_case(root: Path, case_id: str) -> Any:
    dataset = load_gold_dataset(root)
    for case in dataset.cases:
        if case.case_id == case_id:
            return case
    raise ValueError(f"unknown case ID: {case_id}")


def _verification_budget(service: object) -> dict[str, int | None] | None:
    verifier = getattr(service, "_verifier", None)
    reader = getattr(verifier, "verification_budget", None)
    if not callable(reader):
        return None
    value = reader()
    return value if isinstance(value, dict) else None


def _candidate_query_audit(
    state: dict[str, Any],
) -> tuple[dict[str, str], dict[str, int]]:
    retrieval = state.get("retrieval")
    if not isinstance(retrieval, dict):
        return {}, {}
    raw_candidates = retrieval.get("raw_candidates")
    if not isinstance(raw_candidates, list):
        return {}, {}
    queries: dict[str, str] = {}
    counts: dict[str, int] = {}
    for candidate in raw_candidates:
        if not isinstance(candidate, dict):
            continue
        query_id = candidate.get("query_id")
        if not isinstance(query_id, str):
            continue
        counts[query_id] = counts.get(query_id, 0) + 1
        metadata = candidate.get("metadata")
        if not isinstance(metadata, dict):
            continue
        query_text = metadata.get("query_text")
        if isinstance(query_text, str) and query_text.strip():
            queries.setdefault(query_id, query_text.strip())
    return queries, counts


def _provider_result_audit(result: object) -> dict[str, object]:
    return {
        "provider": getattr(result, "provider", None),
        "status": getattr(result, "status", None),
        "cache_status": getattr(result, "cache_status", None),
        "error_code": getattr(result, "error_code", None),
        "retry_count": getattr(result, "retry_count", 0),
    }


def _search_diagnostics(state: dict[str, Any], adapter: object) -> list[dict[str, object]]:
    retrieval = state.get("retrieval")
    if not isinstance(retrieval, dict):
        return []
    completed = retrieval.get("completed_query_ids")
    if not isinstance(completed, list):
        return []
    reader = getattr(adapter, "last_query_diagnostics", None)
    if not callable(reader):
        return []
    provider_reader = getattr(adapter, "last_provider_results", None)
    executed_queries, candidate_counts = _candidate_query_audit(state)
    output: list[dict[str, object]] = []
    for query_id in completed:
        if not isinstance(query_id, str):
            continue
        value = reader(query_id)
        if not isinstance(value, dict):
            continue
        provider_results = provider_reader(query_id) if callable(provider_reader) else []
        audits = [_provider_result_audit(result) for result in provider_results]
        uncached = sum(
            audit["cache_status"] in {"miss", "bypass"}
            and audit["error_code"] != "PROVIDER_CALL_BUDGET_EXHAUSTED"
            for audit in audits
        )
        diagnostic = dict(value)
        diagnostic.update(
            {
                "executed_query": executed_queries.get(query_id),
                "returned_candidate_count": candidate_counts.get(query_id, 0),
                "uncached_provider_call_count": uncached,
                "cache_hit_count": sum(audit["cache_status"] == "hit" for audit in audits),
                "coalesced_provider_call_count": sum(
                    audit["cache_status"] == "coalesced" for audit in audits
                ),
                "budget_exhausted_call_count": sum(
                    audit["error_code"] == "PROVIDER_CALL_BUDGET_EXHAUSTED" for audit in audits
                ),
                "provider_results": audits,
            }
        )
        output.append(diagnostic)
    return output


def _evidence_items(state: dict[str, Any]) -> dict[str, dict[str, object]]:
    evidence = state.get("evidence")
    if not isinstance(evidence, dict):
        return {}
    items = evidence.get("items")
    if not isinstance(items, list):
        return {}
    return {
        evidence_id: item
        for item in items
        if isinstance(item, dict) and isinstance((evidence_id := item.get("evidence_id")), str)
    }


def _accepted_evidence(state: dict[str, Any]) -> list[dict[str, object]]:
    evidence = state.get("evidence")
    if not isinstance(evidence, dict):
        return []
    accepted = evidence.get("accepted_ids")
    items = evidence.get("items")
    if not isinstance(accepted, list) or not isinstance(items, list):
        return []
    accepted_ids = {value for value in accepted if isinstance(value, str)}
    output: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("evidence_id") not in accepted_ids:
            continue
        output.append(
            {
                "evidence_id": item.get("evidence_id"),
                "title": item.get("title"),
                "locator": item.get("locator"),
                "provider": item.get("provider"),
                "verification_status": item.get("verification_status"),
                "supports_gap_ids": item.get("supports_gap_ids", []),
            }
        )
    return output


def _evidence_review(state: dict[str, Any]) -> list[dict[str, object]]:
    ledger = state.get("evidence_ledger")
    if not isinstance(ledger, dict):
        return []
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        return []
    items = _evidence_items(state)
    output: list[dict[str, object]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        evidence_id = entry.get("evidence_id")
        item = items.get(evidence_id, {}) if isinstance(evidence_id, str) else {}
        supports = entry.get("gap_supports")
        support_summary: list[dict[str, object]] = []
        if isinstance(supports, list):
            for support in supports:
                if not isinstance(support, dict):
                    continue
                support_summary.append(
                    {
                        "gap_id": support.get("gap_id"),
                        "decision": support.get("decision"),
                        "support_type": support.get("support_type"),
                        "confidence": support.get("confidence"),
                        "checklist_results": support.get("checklist_results", {}),
                        "limitations": support.get("limitations", []),
                    }
                )
        output.append(
            {
                "evidence_id": evidence_id,
                "title": item.get("title"),
                "accepted": entry.get("accepted"),
                "rejection_reasons": entry.get("rejection_reasons", []),
                "gap_supports": support_summary,
            }
        )
    return output


async def _run(args: argparse.Namespace) -> int:
    if not 1 <= args.max_llm_calls <= 20:
        raise ValueError("--max-llm-calls must be between 1 and 20")
    if not 1 <= args.provider_call_budget <= 12:
        raise ValueError("--provider-call-budget must be between 1 and 12")
    if not 1 <= args.verification_call_budget <= 24:
        raise ValueError("--verification-call-budget must be between 1 and 24")

    output_dir: Path = args.output_dir
    case = _select_case(args.dataset_root, args.case_id)
    provider_config = load_provider_config()
    llm = build_llm_provider(provider_config, None)
    literature = build_literature_runtime(
        LiteratureProviderSettings(
            contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
            semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
            enable_web_search=False,
            results_per_provider_request=3,
            max_provider_calls_total=args.provider_call_budget,
            max_verification_calls_total=args.verification_call_budget,
        )
    )

    try:
        state, trace = await execute_benchmark_case(
            case=case,
            llm=llm,
            search=literature.adapter,
            max_llm_calls=args.max_llm_calls,
            task_id=f"single-case-{case.case_id}",
        )
        evaluation = evaluate_case(case, trace, minimum_score=args.minimum_score)
        execution = state.get("execution")
        report = state.get("report")
        summary: dict[str, object] = {
            "case_id": case.case_id,
            "status": evaluation.status,
            "passed": evaluation.status == "passed",
            "score": evaluation.score,
            "minimum_score": evaluation.minimum_score,
            "expected_decision": evaluation.expected_decision,
            "observed_decision": evaluation.observed_decision,
            "decision_matches": evaluation.decision_matches,
            "hard_failures": [
                failure.model_dump(mode="json") for failure in evaluation.hard_failures
            ],
            "failed_stages": [
                stage.model_dump(mode="json") for stage in evaluation.stages if not stage.passed
            ],
            "execution_status": (execution.get("status") if isinstance(execution, dict) else None),
            "report_status": report.get("status") if isinstance(report, dict) else None,
            "provider": provider_config.provider.value,
            "model": provider_config.model,
            "llm_call_budget": args.max_llm_calls,
            "provider_call_budget": literature.service.provider_call_budget(),
            "verification_call_budget": _verification_budget(literature.service),
            "search_diagnostics": _search_diagnostics(state, literature.adapter),
            "accepted_evidence": _accepted_evidence(state),
            "evidence_review": _evidence_review(state),
            "web_search_enabled": False,
        }
        _write_json(output_dir / "state.json", state)
        _write_json(
            output_dir / "trace.json",
            trace.model_dump(mode="json", by_alias=True),
        )
        _write_json(
            output_dir / "evaluation.json",
            evaluation.model_dump(mode="json"),
        )
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if summary["passed"] else 1
    except Exception as exc:
        summary = {
            "case_id": case.case_id,
            "status": "execution_error",
            "passed": False,
            "error_type": type(exc).__name__,
            "message": str(exc),
            "provider": provider_config.provider.value,
            "model": provider_config.model,
            "provider_call_budget": literature.service.provider_call_budget(),
            "verification_call_budget": _verification_budget(literature.service),
            "web_search_enabled": False,
        }
        _write_json(output_dir / "summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    finally:
        await literature.aclose()


def main() -> int:
    return asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
