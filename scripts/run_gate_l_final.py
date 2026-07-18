"""Execute all 16 frozen holdout cases against real Mistral for Gate L evidence.

Hard timeout: 120s/case. Strict budget compliance. SHA-256 digests for immutability.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
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


def load_holdout_cases() -> list[dict]:
    return [json.loads(line) for line in HOLDOUT_CASES.read_text(encoding="utf-8").strip().splitlines()]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def execute_case(case: dict, executor, idx: int) -> dict:
    case_id = case["case_id"]
    budget = case["budget"]
    request = ResearchRequest(
        question=case["task_input"],
        domain_hint=case.get("title"),
        required_constraints=case.get("allowed_constraints", []),
    )

    trace_records = []
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
    except asyncio.TimeoutError:
        error = f"TIMEOUT: exceeded {PER_CASE_TIMEOUT}s wall-clock limit"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    wall = round(time.monotonic() - started, 2)
    terminal = result.get("execution", {}).get("status", "unknown") if result else "error"

    # Analyze LLM invocations
    llm_events = [r for r in trace_records if r["event"] == "llm.invocation"]
    by_task = {}
    for ev in llm_events:
        task = ev["data"].get("task", "unknown")
        by_task.setdefault(task, {"calls": 0, "latency": 0, "errors": 0, "toks_in": 0, "toks_out": 0})
        by_task[task]["calls"] += 1
        by_task[task]["latency"] += ev["data"].get("latency_seconds", 0)
        if ev["data"].get("error_code"):
            by_task[task]["errors"] += 1
        usage = ev["data"].get("usage", {})
        by_task[task]["toks_in"] += usage.get("input_tokens", 0) or 0
        by_task[task]["toks_out"] += usage.get("output_tokens", 0) or 0

    total_calls = sum(t["calls"] for t in by_task.values())
    total_toks = sum(t["toks_in"] + t["toks_out"] for t in by_task.values())

    # Strict budget compliance (no silent continuation)
    violations = []
    if total_calls > budget["max_calls"]:
        violations.append(f"calls {total_calls}>{budget['max_calls']}")
    if total_toks > budget["max_total_tokens"]:
        violations.append(f"tokens {total_toks}>{budget['max_total_tokens']}")
    if wall > budget["max_wall_seconds"]:
        violations.append(f"wall {wall}s>{budget['max_wall_seconds']}s")

    # First LLM error
    first_err = None
    for ev in llm_events:
        if ev["data"].get("error_code"):
            first_err = {"task": ev["data"].get("task"), "code": ev["data"].get("error_code"), "lat": ev["data"].get("latency_seconds")}
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
        "tokens_in": sum(t["toks_in"] for t in by_task.values()),
        "tokens_out": sum(t["toks_out"] for t in by_task.values()),
        "by_task": {k: {"calls": v["calls"], "latency": round(v["latency"], 1), "errors": v["errors"], "tokens": v["toks_in"] + v["toks_out"]} for k, v in by_task.items()},
        "output_digest": sha256_text(output_dump),
        "trace_digest": sha256_text(trace_dump),
        "started_utc": started_utc,
    }


async def main() -> int:
    cases = load_holdout_cases()
    print(f"Model: mistral-small-latest | Cases: {len(cases)} | Timeout: {PER_CASE_TIMEOUT}s/case")

    config = load_provider_config()
    price_table = load_price_table(Path("config/price-table-mistral.json"))
    executor = build_real_task_executor(
        config,
        literature_settings=LiteratureProviderSettings(contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL")),
        price_table=price_table,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    evidence_dir = OUTPUT_DIR / "per-case"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, case in enumerate(cases):
        r = await execute_case(case, executor, i + 1)
        results.append(r)

        # Save per-case evidence
        case_path = evidence_dir / f"{r['case_id']}.json"
        case_path.write_text(json.dumps(r, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        v = " | VIOLATIONS: " + ", ".join(r["budget_violations"]) if r["budget_violations"] else ""
        e = f" | ERR: {r['first_llm_error']['code']}" if r["first_llm_error"] else ""
        t = f" | {r['error']}" if r["error"] else ""
        print(f"[{i+1:2d}/{len(cases)}] {r['case_id']:35s} | {r['terminal']:10s} | {r['wall_seconds']:6.1f}s | calls={r['total_calls']}{v}{e}{t}")

    # Node summary
    all_tasks = set()
    for r in results:
        all_tasks.update(r["by_task"].keys())

    print(f"\n=== NODE SUMMARY (mistral-small-latest) ===")
    for task in sorted(all_tasks):
        td = [r["by_task"][task] for r in results if task in r["by_task"]]
        print(f"  {task:25s} calls={sum(t['calls'] for t in td):3d}  lat={sum(t['latency'] for t in td):7.1f}s  avg={sum(t['latency'] for t in td)/max(sum(t['calls'] for t in td),1):5.1f}s  errs={sum(t['errors'] for t in td)}  toks={sum(t['tokens'] for t in td)}")

    # Budget summary
    violated = [r for r in results if r["budget_violations"]]
    timeouts = [r for r in results if r["error"] and "TIMEOUT" in r["error"]]
    print(f"\n=== ISSUES ===")
    print(f"  Budget violations: {len(violated)}/{len(cases)}")
    print(f"  Hard timeouts: {len(timeouts)}/{len(cases)}")
    for r in violated:
        print(f"    {r['case_id']}: {', '.join(r['budget_violations'])}")
    for r in timeouts:
        print(f"    {r['case_id']}: {r['error']}")

    # Terminal status summary
    from collections import Counter
    term_counts = Counter(r["terminal"] for r in results)
    print(f"\n=== TERMINAL STATUSES ===")
    for status, count in term_counts.most_common():
        print(f"  {status}: {count}/{len(cases)}")

    # Save run record
    run_record = {
        "gate": "L",
        "version": "v1",
        "provider": config.provider.value,
        "model": config.model,
        "holdout_digest": sha256_file(HOLDOUT_CASES),
        "repo_sha": os.environ.get("GITHUB_SHA", "local"),
        "per_case_timeout": PER_CASE_TIMEOUT,
        "started_utc": datetime.now(tz=UTC).isoformat(),
        "terminal_summary": dict(term_counts),
        "issues": {"budget_violations": len(violated), "timeouts": len(timeouts)},
        "results": results,
    }
    run_path = OUTPUT_DIR / "run-record.json"
    run_path.write_text(json.dumps(run_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nRun record: {run_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
