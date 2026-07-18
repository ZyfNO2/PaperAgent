"""Execute the frozen Gate L v1 diagnostic corpus against a configured provider.

This legacy runner is diagnostic-only. Formal v3 strategy execution uses
``scripts/run_gate_l_variant.py``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from paperagent.api.real_executor import build_real_task_executor
from paperagent.literature.factory import LiteratureProviderSettings
from paperagent.pricing import load_price_table
from paperagent.providers.config import load_provider_config
from paperagent.schemas.request import ResearchRequest


def _load_dotenv_if_available() -> None:
    try:
        import dotenv
    except ModuleNotFoundError:
        return
    dotenv.load_dotenv()


_load_dotenv_if_available()

HOLDOUT_CASES = Path("evals/v0_6/holdout_cases.v1.jsonl")
OUTPUT_DIR = Path("build/gate-l-evidence")
REPO_SHA = os.environ.get("GITHUB_SHA", "local")


def load_holdout_cases() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in HOLDOUT_CASES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_request(case: dict[str, Any]) -> ResearchRequest:
    return ResearchRequest(
        question=case["task_input"],
        domain_hint=case.get("title"),
        required_constraints=case.get("allowed_constraints", []),
    )


async def execute_case(
    case: dict[str, Any],
    executor: Any,
    case_index: int,
    *,
    price_table_path: Path,
) -> dict[str, Any]:
    case_id = case["case_id"]
    budget = case["budget"]
    trace_records: list[dict[str, Any]] = []

    async def emit(event_type: str, data: dict[str, Any]) -> None:
        trace_records.append({"event": event_type, "data": data})

    def should_cancel() -> bool:
        return False

    started = time.monotonic()
    started_utc = datetime.now(tz=UTC).isoformat()
    try:
        result = await asyncio.wait_for(
            executor.execute(
                task_id=f"gate-l-{case_id}",
                request=build_request(case),
                emit=emit,
                should_cancel=should_cancel,
            ),
            timeout=float(budget["max_wall_seconds"]),
        )
        terminal_status = result.get("execution", {}).get("status", "unknown")
        error = None
    except TimeoutError:
        result = {"error": "case wall-clock budget exhausted"}
        terminal_status = "timeout"
        error = "TIMEOUT"
    except Exception as exc:
        result = {"error": str(exc)}
        terminal_status = "error"
        error = f"{type(exc).__name__}: {exc}"

    wall_seconds = round(time.monotonic() - started, 3)
    llm_events = [record for record in trace_records if record["event"] == "llm.invocation"]
    calls_count = len(llm_events)
    total_input_tokens = sum(
        record["data"].get("usage", {}).get("input_tokens", 0) or 0
        for record in llm_events
    )
    total_output_tokens = sum(
        record["data"].get("usage", {}).get("output_tokens", 0) or 0
        for record in llm_events
    )
    retries = sum(max(int(record["data"].get("attempt", 1)) - 1, 0) for record in llm_events)
    repairs = sum(
        1
        for record in llm_events
        if record["data"].get("error_code")
        and int(record["data"].get("attempt", 1)) > 1
    )
    errors = sum(1 for record in llm_events if record["data"].get("error_code"))
    estimated_cost_usd = round(
        sum(
            record["data"].get("usage", {}).get("estimated_cost_usd", 0.0) or 0.0
            for record in llm_events
        ),
        8,
    )

    total_tokens = total_input_tokens + total_output_tokens
    calls_within = calls_count <= budget["max_calls"]
    tokens_within = total_tokens <= budget["max_total_tokens"]
    time_within = wall_seconds <= budget["max_wall_seconds"]
    cost_within = estimated_cost_usd <= budget["max_cost_usd"]
    budget_compliance = {
        "calls": {
            "used": calls_count,
            "limit": budget["max_calls"],
            "within": calls_within,
        },
        "tokens": {
            "used": total_tokens,
            "limit": budget["max_total_tokens"],
            "within": tokens_within,
        },
        "time_seconds": {
            "used": wall_seconds,
            "limit": budget["max_wall_seconds"],
            "within": time_within,
        },
        "cost_usd": {
            "used": estimated_cost_usd,
            "limit": budget["max_cost_usd"],
            "within": cost_within,
        },
        "all_within": (
            calls_within
            and tokens_within
            and time_within
            and cost_within
            and errors == 0
        ),
    }

    output_dump = json.dumps(result, ensure_ascii=False, sort_keys=True)
    trace_dump = json.dumps(trace_records, ensure_ascii=False, sort_keys=True)
    return {
        "case_id": case_id,
        "case_index": case_index,
        "category": case["category"],
        "case_version": case["version"],
        "execution": {
            "repo_sha": REPO_SHA,
            "provider": os.environ.get("PAPERAGENT_LLM_PROVIDER", "unknown"),
            "model": os.environ.get("PAPERAGENT_LLM_MODEL", "unknown"),
            "base_url": os.environ.get("PAPERAGENT_LLM_BASE_URL", ""),
            "price_table_path": price_table_path.as_posix(),
            "price_table_sha256": sha256_file(price_table_path),
            "started_utc": started_utc,
            "wall_seconds": wall_seconds,
            "terminal_status": terminal_status,
            "error": error,
        },
        "telemetry": {
            "calls": calls_count,
            "retries": retries,
            "repairs": repairs,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "errors": errors,
        },
        "budget_compliance": budget_compliance,
        "output_digest": sha256_text(output_dump),
        "trace_digest": sha256_text(trace_dump),
        "reference_evidence": case.get("reference_evidence", []),
        "deterministic_checks": case.get("deterministic_checks", []),
    }


async def main() -> int:
    cases = load_holdout_cases()
    print(f"Running all {len(cases)} frozen v1 diagnostic cases")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    provider_config = load_provider_config()
    price_table_path = Path(
        os.environ.get("PAPERAGENT_PRICE_TABLE", "config/price-table-mistral.json")
    )
    price_table = load_price_table(price_table_path)
    executor = build_real_task_executor(
        provider_config,
        literature_settings=LiteratureProviderSettings(
            contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
            semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
            enable_arxiv_fallback=True,
        ),
        price_table=price_table,
    )

    evidence_dir = OUTPUT_DIR / "per-case"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    run_record: dict[str, Any] = {
        "gate": "L",
        "version": "v1",
        "formal_run": False,
        "diagnostic_only": True,
        "repo_sha": REPO_SHA,
        "holdout_digest": sha256_file(HOLDOUT_CASES),
        "provider": provider_config.provider.value,
        "model": provider_config.model,
        "price_table_path": price_table_path.as_posix(),
        "price_table_sha256": sha256_file(price_table_path),
        "started_utc": datetime.now(tz=UTC).isoformat(),
        "sample_strategy": "all_cases",
        "cases": [],
    }

    for index, case in enumerate(cases, start=1):
        case_id = case["case_id"]
        print(f"[{index}/{len(cases)}] Executing {case_id}...", flush=True)
        evidence = await execute_case(
            case,
            executor,
            index,
            price_table_path=price_table_path,
        )
        case_path = evidence_dir / f"{case_id}.json"
        case_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        run_record["cases"].append(
            {
                "case_id": case_id,
                "category": case["category"],
                "terminal_status": evidence["execution"]["terminal_status"],
                "wall_seconds": evidence["execution"]["wall_seconds"],
                "calls": evidence["telemetry"]["calls"],
                "budget_compliance": evidence["budget_compliance"]["all_within"],
                "output_digest": evidence["output_digest"],
            }
        )

    run_record["finished_utc"] = datetime.now(tz=UTC).isoformat()
    run_path = OUTPUT_DIR / "run-record.json"
    run_path.write_text(
        json.dumps(run_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Run record saved: {run_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
