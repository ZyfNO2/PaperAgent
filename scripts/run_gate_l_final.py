"""Execute frozen holdout cases against real Mistral for Gate L diagnostic evidence.

Hard timeout: 120s/case. Strict budget compliance. SHA-256 digests for immutability.

After any prompt/rule change, the frozen v1 corpus is diagnostic-only and must not be used as
final scientific acceptance evidence. Freeze a fresh holdout version before a release decision.
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

import dotenv

from paperagent.api.real_executor import build_real_task_executor
from paperagent.literature.factory import LiteratureProviderSettings
from paperagent.pricing import load_price_table
from paperagent.providers.config import load_provider_config
from paperagent.schemas.request import ResearchRequest


dotenv.load_dotenv()

HOLDOUT_CASES = Path("evals/v0_6/holdout_cases.v1.jsonl")
OUTPUT_DIR = Path("build/gate-l-evidence")
PER_CASE_TIMEOUT = 120


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Gate L frozen holdout diagnostics")
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Run only the selected case ID. Repeat to select multiple cases.",
    )
    return parser.parse_args()


def load_holdout_cases() -> list[dict]:
    return [
        json.loads(line) for line in HOLDOUT_CASES.read_text(encoding="utf-8").strip().splitlines()
    ]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _scientific_trace(result: dict | None) -> dict[str, object]:
    if not result:
        return {}

    plan = result.get("plan") if isinstance(result.get("plan"), dict) else {}
    retrieval = result.get("retrieval") if isinstance(result.get("retrieval"), dict) else {}
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    quality = result.get("quality") if isinstance(result.get("quality"), dict) else {}

    search_queries = (
        plan.get("search_queries") if isinstance(plan.get("search_queries"), list) else []
    )
    query_ids_by_gap: dict[str, list[str]] = {}
    for query in search_queries:
        if not isinstance(query, dict):
            continue
        gap_id = query.get("gap_id")
        query_id = query.get("query_id")
        if isinstance(gap_id, str) and isinstance(query_id, str):
            query_ids_by_gap.setdefault(gap_id, []).append(query_id)

    evidence_gaps = plan.get("evidence_gaps") if isinstance(plan.get("evidence_gaps"), list) else []
    required_gaps: list[dict[str, object]] = []
    for gap in evidence_gaps:
        if not isinstance(gap, dict) or not gap.get("required"):
            continue
        gap_id = gap.get("gap_id")
        required_gaps.append(
            {
                "gap_id": gap_id,
                "minimum_accepted_items": gap.get("minimum_accepted_items"),
                "query_ids": query_ids_by_gap.get(gap_id, []) if isinstance(gap_id, str) else [],
            }
        )

    items = evidence.get("items") if isinstance(evidence.get("items"), list) else []
    verification_counts = Counter(
        item.get("verification_status", "unknown") for item in items if isinstance(item, dict)
    )

    tool_errors = retrieval.get("tool_errors")
    if not isinstance(tool_errors, list):
        tool_errors = []

    return {
        "plan_status": plan.get("status"),
        "required_gap_count": len(required_gaps),
        "required_gaps": required_gaps,
        "search_query_count": len(search_queries),
        "retrieval_round": retrieval.get("round"),
        "retrieval_max_rounds": retrieval.get("max_rounds"),
        "retrieval_budget_exhausted": retrieval.get("budget_exhausted"),
        "completed_query_ids": retrieval.get("completed_query_ids", []),
        "tool_errors": tool_errors,
        "coverage_by_gap": evidence.get("coverage_by_gap", {}),
        "verification_counts": dict(verification_counts),
        "accepted_evidence_count": len(evidence.get("accepted_ids", [])),
        "quality_verdict": quality.get("verdict"),
        "quality_reason_codes": quality.get("reason_codes", []),
        "quality_missing_gap_ids": quality.get("missing_gap_ids", []),
    }


async def execute_case(case: dict, executor, idx: int) -> dict:
    case_id = case["case_id"]
    budget = case["budget"]
    request = ResearchRequest(
        question=case["task_input"],
        domain_hint=case.get("title"),
        required_constraints=case.get("allowed_constraints", []),
    )

    trace_records: list[dict] = []

    async def emit(event_type: str, data: dict) -> None:
        trace_records.append({"event": event_type, "data": data})

    def should_cancel() -> bool:
        return False

    started = time.monotonic()
    started_utc = datetime.now(tz=UTC).isoformat()
    error = None
    result = None

    try:
        result = await asyncio.wait_for(
            executor.execute(
                task_id=f"gate-l-{case_id}",
                request=request,
                emit=emit,
                should_cancel=should_cancel,
            ),
            timeout=PER_CASE_TIMEOUT,
        )
    except TimeoutError:
        error = f"TIMEOUT: exceeded {PER_CASE_TIMEOUT}s wall-clock limit"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    wall = round(time.monotonic() - started, 2)
    terminal = result.get("execution", {}).get("status", "unknown") if result else "error"

    llm_events = [r for r in trace_records if r["event"] == "llm.invocation"]
    by_task: dict[str, dict[str, float | int]] = {}
    for ev in llm_events:
        task = ev["data"].get("task", "unknown")
        by_task.setdefault(
            task,
            {"calls": 0, "latency": 0.0, "errors": 0, "toks_in": 0, "toks_out": 0},
        )
        by_task[task]["calls"] += 1
        by_task[task]["latency"] += ev["data"].get("latency_seconds", 0) or 0
        if ev["data"].get("error_code"):
            by_task[task]["errors"] += 1
        usage = ev["data"].get("usage", {})
        by_task[task]["toks_in"] += usage.get("input_tokens", 0) or 0
        by_task[task]["toks_out"] += usage.get("output_tokens", 0) or 0

    total_calls = int(sum(t["calls"] for t in by_task.values()))
    total_toks = int(sum(t["toks_in"] + t["toks_out"] for t in by_task.values()))

    violations = []
    if total_calls > budget["max_calls"]:
        violations.append(f"calls {total_calls}>{budget['max_calls']}")
    if total_toks > budget["max_total_tokens"]:
        violations.append(f"tokens {total_toks}>{budget['max_total_tokens']}")
    if wall > budget["max_wall_seconds"]:
        violations.append(f"wall {wall}s>{budget['max_wall_seconds']}s")

    first_err = None
    for ev in llm_events:
        if ev["data"].get("error_code"):
            first_err = {
                "task": ev["data"].get("task"),
                "code": ev["data"].get("error_code"),
                "lat": ev["data"].get("latency_seconds"),
            }
            break

    output_dump = json.dumps(result, ensure_ascii=False, sort_keys=True) if result else "{}"
    trace_dump = json.dumps(trace_records, ensure_ascii=False, sort_keys=True)

    return {
        "case_id": case_id,
        "case_index": idx,
        "category": case["category"],
        "version": case["version"],
        "terminal": terminal,
        "wall_seconds": wall,
        "error": error,
        "budget_violations": violations,
        "first_llm_error": first_err,
        "total_calls": total_calls,
        "tokens_in": int(sum(t["toks_in"] for t in by_task.values())),
        "tokens_out": int(sum(t["toks_out"] for t in by_task.values())),
        "by_task": {
            key: {
                "calls": int(value["calls"]),
                "latency": round(float(value["latency"]), 1),
                "errors": int(value["errors"]),
                "tokens": int(value["toks_in"] + value["toks_out"]),
            }
            for key, value in by_task.items()
        },
        "scientific_trace": _scientific_trace(result),
        "output_digest": sha256_text(output_dump),
        "trace_digest": sha256_text(trace_dump),
        "started_utc": started_utc,
    }


async def main() -> int:
    args = parse_args()
    cases = load_holdout_cases()
    requested_case_ids = set(args.case_id)
    if requested_case_ids:
        cases = [case for case in cases if case["case_id"] in requested_case_ids]
        missing = requested_case_ids - {case["case_id"] for case in cases}
        if missing:
            raise SystemExit(f"Unknown case IDs: {', '.join(sorted(missing))}")

    config = load_provider_config()
    print(f"Model: {config.model} | Cases: {len(cases)} | Timeout: {PER_CASE_TIMEOUT}s/case")
    if requested_case_ids:
        print(f"Targeted diagnostic cases: {', '.join(sorted(requested_case_ids))}")

    price_table = load_price_table(Path("config/price-table-mistral.json"))
    executor = build_real_task_executor(
        config,
        literature_settings=LiteratureProviderSettings(
            contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
            semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
            enable_arxiv_fallback=True,
        ),
        price_table=price_table,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    evidence_dir = OUTPUT_DIR / "per-case"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, case in enumerate(cases):
        result = await execute_case(case, executor, i + 1)
        results.append(result)

        case_path = evidence_dir / f"{result['case_id']}.json"
        case_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        violations = (
            " | VIOLATIONS: " + ", ".join(result["budget_violations"])
            if result["budget_violations"]
            else ""
        )
        llm_error = (
            f" | ERR: {result['first_llm_error']['code']}" if result["first_llm_error"] else ""
        )
        runtime_error = f" | {result['error']}" if result["error"] else ""
        trace = result["scientific_trace"]
        print(
            f"[{i + 1:2d}/{len(cases)}] {result['case_id']:35s} | "
            f"{result['terminal']:10s} | {result['wall_seconds']:6.1f}s | "
            f"calls={result['total_calls']} | required={trace.get('required_gap_count')} | "
            f"accepted={trace.get('accepted_evidence_count')} | "
            f"quality={trace.get('quality_reason_codes')}{violations}{llm_error}{runtime_error}"
        )

    all_tasks = set()
    for result in results:
        all_tasks.update(result["by_task"].keys())

    print(f"\n=== NODE SUMMARY ({config.model}) ===")
    for task in sorted(all_tasks):
        task_data = [result["by_task"][task] for result in results if task in result["by_task"]]
        calls = sum(item["calls"] for item in task_data)
        latency = sum(item["latency"] for item in task_data)
        print(
            f"  {task:25s} calls={calls:3d} lat={latency:7.1f}s "
            f"avg={latency / max(calls, 1):5.1f}s "
            f"errs={sum(item['errors'] for item in task_data)} "
            f"toks={sum(item['tokens'] for item in task_data)}"
        )

    violated = [result for result in results if result["budget_violations"]]
    timeouts = [result for result in results if result["error"] and "TIMEOUT" in result["error"]]
    print("\n=== ISSUES ===")
    print(f"  Budget violations: {len(violated)}/{len(cases)}")
    print(f"  Hard timeouts: {len(timeouts)}/{len(cases)}")
    for result in violated:
        print(f"    {result['case_id']}: {', '.join(result['budget_violations'])}")
    for result in timeouts:
        print(f"    {result['case_id']}: {result['error']}")

    term_counts = Counter(result["terminal"] for result in results)
    print("\n=== TERMINAL STATUSES ===")
    for status, count in term_counts.most_common():
        print(f"  {status}: {count}/{len(cases)}")

    run_record = {
        "gate": "L",
        "holdout_version": "v1",
        "acceptance_use": "diagnostic_only_after_prompt_change",
        "final_acceptance_requires_new_holdout": True,
        "provider": config.provider.value,
        "model": config.model,
        "holdout_digest": sha256_file(HOLDOUT_CASES),
        "repo_sha": os.environ.get("GITHUB_SHA", "local"),
        "per_case_timeout": PER_CASE_TIMEOUT,
        "arxiv_fallback_enabled": True,
        "selected_case_ids": sorted(requested_case_ids),
        "started_utc": datetime.now(tz=UTC).isoformat(),
        "terminal_summary": dict(term_counts),
        "issues": {"budget_violations": len(violated), "timeouts": len(timeouts)},
        "results": results,
    }
    run_path = OUTPUT_DIR / "run-record.json"
    run_path.write_text(
        json.dumps(run_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\nRun record: {run_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
