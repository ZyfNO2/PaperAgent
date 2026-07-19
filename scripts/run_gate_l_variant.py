"""Run one predeclared Gate L strategy against a frozen v3 holdout."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gate_l_acceptance_v3 import allowed_terminals, verify_manifest
from run_gate_l_v2 import (
    _git_clean,
    _normalized_terminal,
    _review_output,
    _scientific_trace,
    _sha256,
    _sha256_json,
)

from paperagent.api.real_executor import build_real_task_executor
from paperagent.literature.factory import LiteratureProviderSettings
from paperagent.pricing import load_price_table
from paperagent.prompts import get_prompt
from paperagent.providers.config import load_provider_config
from paperagent.schemas.request import ResearchRequest

ALLOWED_ENV_PREFIXES = ("PAPERAGENT_", "SEMANTIC_SCHOLAR_")


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _profile(path: Path) -> dict[str, Any]:
    profile = _read(path)
    for field in ("strategy_id", "provider", "model", "base_url", "price_table"):
        value = profile.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"strategy profile requires {field}")
    if "api_key" in profile or "secret" in profile:
        raise ValueError("strategy profiles must not contain credentials")
    environment = profile.get("environment", {})
    if not isinstance(environment, dict):
        raise ValueError("strategy environment must be an object")
    for key, value in environment.items():
        if not isinstance(key, str) or not key.startswith(ALLOWED_ENV_PREFIXES):
            raise ValueError(f"unsupported environment override: {key}")
        if not isinstance(value, str):
            raise ValueError(f"environment override {key} must be a string")
    literature = profile.get("literature", {})
    if not isinstance(literature, dict):
        raise ValueError("strategy literature settings must be an object")
    allowed_literature = {
        "provider_timeout_seconds",
        "round_deadline_seconds",
        "enable_arxiv_fallback",
    }
    unknown = set(literature) - allowed_literature
    if unknown:
        raise ValueError(f"unsupported literature settings: {sorted(unknown)}")
    return profile


def _apply_environment(profile: dict[str, Any]) -> None:
    for key, value in profile.get("environment", {}).items():
        os.environ[key] = value


async def _execute_case_with_payload(
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
                task_id=f"gate-l-v3-{case_id}",
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
        str(result.get("execution", {}).get("status", "failed"))
        if result is not None
        else "failed"
    )
    terminal_class = _normalized_terminal(raw_terminal)
    llm_events = [
        event for event in trace_records if event.get("event") == "llm.invocation"
    ]
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
        if not isinstance(cost, int | float) or isinstance(cost, bool) or cost < 0:
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

    output_payload = result or {}
    trace_payload = trace_records
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
        "skipped_checks": [],
        "excluded_checks": [],
        "review_output": _review_output(result),
        "output_payload": output_payload,
        "trace_payload": trace_payload,
        "output_digest": _sha256_json(output_payload),
        "trace_digest": _sha256_json(trace_payload),
    }


def _case_failures(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for item in results:
        violations = item.get("budget_violations")
        if not isinstance(violations, list):
            violations = ["invalid_budget_violations"]
        if item.get("budget_compliance") is not True and not violations:
            violations = ["budget_noncompliance_without_reason"]
        if violations:
            failures.append(
                {
                    "case_id": item["case_id"],
                    "violations": sorted(str(value) for value in violations),
                }
            )
    return failures


async def run(args: argparse.Namespace) -> int:
    profile = _profile(args.strategy)
    _apply_environment(profile)
    manifest, all_cases = verify_manifest(args.manifest)
    prompt = get_prompt("planning")
    if prompt.version != manifest.get("planning_prompt_version"):
        raise ValueError("runtime planning prompt does not match frozen manifest")

    requested = set(args.case_id)
    cases = all_cases
    if requested:
        cases = [case for case in all_cases if case["case_id"] in requested]
        missing = requested - {case["case_id"] for case in cases}
        if missing:
            raise ValueError(f"unknown case IDs: {sorted(missing)}")
    formal_run = not requested and len(cases) == len(all_cases) == 16
    clean_tree = _git_clean()

    provider_config = load_provider_config(
        provider=profile["provider"],
        model=profile["model"],
        base_url=profile["base_url"],
    )
    price_table_path = Path(profile["price_table"])
    price_table = load_price_table(price_table_path)
    literature = profile.get("literature", {})
    executor = build_real_task_executor(
        provider_config,
        literature_settings=LiteratureProviderSettings(
            contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
            semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
            provider_timeout_seconds=float(
                literature.get("provider_timeout_seconds", 10.0)
            ),
            round_deadline_seconds=float(
                literature.get("round_deadline_seconds", 25.0)
            ),
            enable_arxiv_fallback=bool(literature.get("enable_arxiv_fallback", True)),
        ),
        price_table=price_table,
    )
    identity = {
        "repo_sha": os.environ.get("GITHUB_SHA", "local"),
        "clean_tree": clean_tree,
        "scientific_behavior_cutoff_sha": manifest["scientific_behavior_cutoff_sha"],
        "planning_prompt_version": prompt.version,
        "provider": provider_config.provider.value,
        "model": provider_config.model,
        "base_url": str(provider_config.base_url),
        "strategy_profile": profile["strategy_id"],
        "strategy_profile_sha256": _digest(args.strategy),
        "price_table_path": price_table_path.as_posix(),
        "price_table_sha256": _sha256(price_table_path),
        "manifest_path": args.manifest.as_posix(),
        "manifest_sha256": _sha256(args.manifest),
        "case_file_sha256": manifest["case_file_sha256"],
        "python_version": sys.version,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_workflow": os.environ.get("GITHUB_WORKFLOW"),
    }

    evidence_dir = args.output_dir / "per-case"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        runtime_case = dict(case)
        runtime_case["expected_terminal"] = sorted(allowed_terminals(case))[0]
        evidence = await _execute_case_with_payload(
            runtime_case,
            executor,
            index,
            identity,
        )
        evidence.pop("expected_terminal", None)
        evidence["expected_terminals"] = sorted(allowed_terminals(case))
        evidence["strategy_profile"] = profile["strategy_id"]
        results.append(evidence)
        (evidence_dir / f"{case['case_id']}.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    global_failures: list[str] = []
    if formal_run and clean_tree is not True:
        global_failures.append("clean_tree_not_verified")
    case_failures = _case_failures(results)
    formal_eligible = formal_run and not global_failures and not case_failures
    run_record = {
        "gate": "L",
        "contract_version": manifest["contract_version"],
        "holdout_version": manifest["version"],
        "strategy_id": profile["strategy_id"],
        "formal_run": formal_run,
        "formal_execution_eligible": formal_eligible,
        "selected_case_ids": sorted(requested),
        "execution_identity": identity,
        "started_utc": min(
            (item["started_utc"] for item in results),
            default=None,
        ),
        "finished_utc": datetime.now(tz=UTC).isoformat(),
        "case_count": len(results),
        "terminal_summary": dict(Counter(item["terminal"] for item in results)),
        "global_failures": global_failures,
        "case_failures": case_failures,
        "cases": [
            {
                "case_id": item["case_id"],
                "category": item["category"],
                "terminal": item["terminal"],
                "expected_terminals": item["expected_terminals"],
                "budget_compliance": item["budget_compliance"],
                "budget_violations": item.get("budget_violations", []),
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
    if not formal_run:
        print("Targeted execution is diagnostic-only.")
    failures = global_failures + [
        f"{item['case_id']}:{','.join(item['violations'])}" for item in case_failures
    ]
    if failures:
        print(f"Formal execution failed closed: {failures}")
        return 2
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--strategy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case-id", action="append", default=[])
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        return asyncio.run(run(args))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Gate L variant run error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
