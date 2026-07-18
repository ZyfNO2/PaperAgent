"""Execute a frozen Gate L v2 holdout against a real configured provider.

Formal runs require a frozen manifest, all 16 cases, exact per-case budgets, complete token/cost
accounting, immutable digests, and reviewer-visible outputs separated from provider identity.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gate_l_v2_acceptance import verify_manifest
from paperagent.api.real_executor import build_real_task_executor
from paperagent.literature.factory import LiteratureProviderSettings
from paperagent.pricing import load_price_table
from paperagent.prompts import get_prompt
from paperagent.providers.config import load_provider_config
from paperagent.schemas.request import ResearchRequest

OUTPUT_DIR = Path("build/gate-l-v2-evidence")
DEFAULT_PRICE_TABLE = Path("config/price-table-mistral.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalized_terminal(raw_terminal: str) -> str:
    if raw_terminal == "completed":
        return "succeeded"
    if raw_terminal in {"blocked", "failed"}:
        return raw_terminal
    return "failed"


def _review_output(result: dict[str, Any] | None) -> dict[str, Any]:
    if not result:
        return {"error": "no terminal workflow result"}
    payload: dict[str, Any] = {}
    for key in ("report", "method", "synthesis", "quality"):
        value = result.get(key)
        if isinstance(value, dict):
            payload[key] = value
    evidence = result.get("evidence")
    if isinstance(evidence, dict):
        accepted = set(evidence.get("accepted_ids", []))
        items = evidence.get("items", [])
        if isinstance(items, list):
            payload["accepted_evidence"] = [
                item
                for item in items
                if isinstance(item, dict) and item.get("evidence_id") in accepted
            ]
    return payload


def _scientific_trace(result: dict[str, Any] | None) -> dict[str, Any]:
    if not result:
        return {}
    plan = result.get("plan") if isinstance(result.get("plan"), dict) else {}
    retrieval = result.get("retrieval") if isinstance(result.get("retrieval"), dict) else {}
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    quality = result.get("quality") if isinstance(result.get("quality"), dict) else {}
    items = evidence.get("items") if isinstance(evidence.get("items"), list) else []
    verification_counts = Counter(
        item.get("verification_status", "unknown") for item in items if isinstance(item, dict)
    )
    return {
        "plan_status": plan.get("status"),
        "retrieval_round": retrieval.get("round"),
        "retrieval_max_rounds": retrieval.get("max_rounds"),
        "retrieval_budget_exhausted": retrieval.get("budget_exhausted"),
        "completed_query_ids": retrieval.get("completed_query_ids", []),
        "tool_errors": retrieval.get("tool_errors", []),
        "coverage_by_gap": evidence.get("coverage_by_gap", {}),
        "verification_counts": dict(verification_counts),
        "accepted_evidence_count": len(evidence.get("accepted_ids", [])),
        "quality_verdict": quality.get("verdict"),
        "quality_reason_codes": quality.get("reason_codes", []),
        "quality_missing_gap_ids": quality.get("missing_gap_ids", []),
    }


async def _execute_case(
    case: dict[str, Any],
    executor: Any,
    case_index: int,
    execution_identity: dict[str, Any],
) -> dict[str, Any]:
    case_id = case["case_id"]
    budget = case["budget"]
    trace_records: list[dict[str, Any]] = []

    async def emit(event_type: str, data: dict[str, Any]) -> None:
        trace_records.append({"event": event_type, "data": data})

    def should_cancel() -> bool:
        return False

    request = ResearchRequest(
        question=case["task_input"],
        domain_hint=case.get("title"),
        required_constraints=case.get("allowed_constraints", []),
    )
    started = time.monotonic()
    started_utc = datetime.now(tz=UTC).isoformat()
    result: dict[str, Any] | None = None
    error: str | None = None
    timeout_seconds = float(budget["max_wall_seconds"])
    try:
        result = await asyncio.wait_for(
            executor.execute(
                task_id=f"gate-l-v2-{case_id}",
                request=request,
                emit=emit,
                should_cancel=should_cancel,
            ),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        error = f"TIMEOUT: exceeded exact case wall limit {timeout_seconds}s"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    wall_seconds = round(time.monotonic() - started, 3)
    raw_terminal = (
        str(result.get("execution", {}).get("status", "failed")) if result is not None else "failed"
    )
    terminal_class = _normalized_terminal(raw_terminal)

    llm_events = [event for event in trace_records if event.get("event") == "llm.invocation"]
    calls = len(llm_events)
    input_tokens = 0
    output_tokens = 0
    estimated_cost = 0.0
    accounting_errors: list[str] = []
    retries = 0
    repairs = 0
    provider_errors = 0

    for index, event in enumerate(llm_events, start=1):
        data = event.get("data", {})
        usage = data.get("usage")
        if not isinstance(usage, dict):
            accounting_errors.append(f"call {index}: missing usage")
            continue
        for token_field in ("input_tokens", "output_tokens"):
            value = usage.get(token_field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                accounting_errors.append(f"call {index}: invalid {token_field}")
        cost = usage.get("estimated_cost_usd")
        if not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0:
            accounting_errors.append(f"call {index}: invalid estimated_cost_usd")
        input_tokens += int(usage.get("input_tokens", 0) or 0)
        output_tokens += int(usage.get("output_tokens", 0) or 0)
        estimated_cost += float(usage.get("estimated_cost_usd", 0.0) or 0.0)
        attempt = data.get("attempt", 1)
        if isinstance(attempt, int) and attempt > 1:
            retries += attempt - 1
        if data.get("error_code"):
            provider_errors += 1
            if isinstance(attempt, int) and attempt > 1:
                repairs += 1

    total_tokens = input_tokens + output_tokens
    violations: list[str] = []
    if calls > budget["max_calls"]:
        violations.append(f"calls {calls}>{budget['max_calls']}")
    if total_tokens > budget["max_total_tokens"]:
        violations.append(f"tokens {total_tokens}>{budget['max_total_tokens']}")
    if wall_seconds > budget["max_wall_seconds"]:
        violations.append(f"wall {wall_seconds}>{budget['max_wall_seconds']}")
    if estimated_cost > budget["max_cost_usd"]:
        violations.append(f"cost {estimated_cost:.6f}>{budget['max_cost_usd']}")
    if accounting_errors:
        violations.append("incomplete_usage_accounting")
    if error:
        violations.append("execution_error")

    output_digest = _sha256_json(result or {})
    trace_digest = _sha256_json(trace_records)
    return {
        "case_id": case_id,
        "case_index": case_index,
        "category": case["category"],
        "version": case["version"],
        "terminal": terminal_class,
        "raw_terminal": raw_terminal,
        "expected_terminal": case["expected_terminal"],
        "started_utc": started_utc,
        "wall_seconds": wall_seconds,
        "error": error,
        "execution_identity": execution_identity,
        "telemetry": {
            "calls": calls,
            "retries": retries,
            "repairs": repairs,
            "provider_errors": provider_errors,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(estimated_cost, 8),
            "accounting_complete": not accounting_errors,
            "accounting_errors": accounting_errors,
        },
        "budget": budget,
        "budget_violations": violations,
        "budget_compliance": not violations,
        "scientific_trace": _scientific_trace(result),
        "deterministic_checks": case["deterministic_checks"],
        "reference_evidence": case.get("reference_evidence", []),
        "review_output": _review_output(result),
        "output_digest": output_digest,
        "trace_digest": trace_digest,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a frozen Gate L v2 holdout")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--price-table", type=Path, default=DEFAULT_PRICE_TABLE)
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    manifest, all_cases = verify_manifest(args.manifest)
    prompt = get_prompt("planning")
    if prompt.version != manifest.get("planning_prompt_version"):
        raise SystemExit(
            "Frozen manifest prompt version does not match runtime planning prompt: "
            f"{manifest.get('planning_prompt_version')} != {prompt.version}"
        )

    requested = set(args.case_id)
    cases = all_cases
    if requested:
        cases = [case for case in all_cases if case["case_id"] in requested]
        missing = requested - {case["case_id"] for case in cases}
        if missing:
            raise SystemExit(f"Unknown case IDs: {', '.join(sorted(missing))}")

    formal_run = not requested and len(cases) == 16
    provider_config = load_provider_config()
    price_table = load_price_table(args.price_table)
    executor = build_real_task_executor(
        provider_config,
        literature_settings=LiteratureProviderSettings(
            contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
            semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
            enable_arxiv_fallback=True,
        ),
        price_table=price_table,
    )
    execution_identity = {
        "repo_sha": os.environ.get("GITHUB_SHA", "local"),
        "scientific_behavior_cutoff_sha": manifest["scientific_behavior_cutoff_sha"],
        "planning_prompt_version": prompt.version,
        "provider": provider_config.provider.value,
        "model": provider_config.model,
        "base_url": provider_config.base_url,
        "price_table_path": args.price_table.as_posix(),
        "price_table_sha256": _sha256(args.price_table),
        "manifest_path": args.manifest.as_posix(),
        "manifest_sha256": _sha256(args.manifest),
        "case_file_sha256": manifest["case_file_sha256"],
    }

    evidence_dir = args.output_dir / "per-case"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['case_id']}...", flush=True)
        evidence = await _execute_case(case, executor, index, execution_identity)
        results.append(evidence)
        (evidence_dir / f"{case['case_id']}.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"  terminal={evidence['terminal']} calls={evidence['telemetry']['calls']} "
            f"tokens={evidence['telemetry']['total_tokens']} "
            f"cost=${evidence['telemetry']['estimated_cost_usd']:.6f} "
            f"budget={'PASS' if evidence['budget_compliance'] else 'FAIL'}"
        )

    hard_failures = [
        {"case_id": item["case_id"], "violations": item["budget_violations"]}
        for item in results
        if item["budget_violations"]
    ]
    run_record = {
        "gate": "L",
        "holdout_version": manifest["version"],
        "formal_run": formal_run,
        "formal_execution_eligible": formal_run and not hard_failures,
        "selected_case_ids": sorted(requested),
        "execution_identity": execution_identity,
        "started_utc": min((item["started_utc"] for item in results), default=None),
        "finished_utc": datetime.now(tz=UTC).isoformat(),
        "case_count": len(results),
        "terminal_summary": dict(Counter(item["terminal"] for item in results)),
        "hard_failures": hard_failures,
        "cases": [
            {
                "case_id": item["case_id"],
                "category": item["category"],
                "terminal": item["terminal"],
                "expected_terminal": item["expected_terminal"],
                "budget_compliance": item["budget_compliance"],
                "output_digest": item["output_digest"],
                "trace_digest": item["trace_digest"],
            }
            for item in results
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "run-record.json").write_text(
        json.dumps(run_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if formal_run and hard_failures:
        print(f"Formal Gate L v2 execution failed closed: {len(hard_failures)} case(s) invalid")
        return 2
    if not formal_run:
        print("Targeted execution is diagnostic-only and cannot establish final Gate L acceptance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
