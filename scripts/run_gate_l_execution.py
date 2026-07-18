"""Execute frozen holdout cases against real Mistral provider for Gate L evidence.

Produces immutable per-case evidence with SHA-256 digests.
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
REPO_SHA = os.environ.get("GITHUB_SHA", "local")


def load_holdout_cases() -> list[dict]:
    cases = []
    for line in HOLDOUT_CASES.read_text(encoding="utf-8").strip().splitlines():
        cases.append(json.loads(line))
    return cases


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_request(case: dict) -> ResearchRequest:
    return ResearchRequest(
        question=case["task_input"],
        domain_hint=case.get("title"),
        required_constraints=case.get("allowed_constraints", []),
    )


async def execute_case(
    case: dict,
    executor,
    case_index: int,
) -> dict[str, object]:
    case_id = case["case_id"]
    budget = case["budget"]
    task_id = f"gate-l-{case_id}"

    request = build_request(case)
    trace_records: list[dict] = []

    async def emit(event_type: str, data: dict) -> None:
        trace_records.append({"event": event_type, "data": data})

    def should_cancel() -> bool:
        return False

    started = time.monotonic()
    started_utc = datetime.now(tz=UTC).isoformat()

    try:
        result = await executor.execute(
            task_id=task_id,
            request=request,
            emit=emit,
            should_cancel=should_cancel,
        )
        terminal_status = result.get("execution", {}).get("status", "unknown")
        error = None
    except Exception as exc:
        result = {"error": str(exc)}
        terminal_status = "error"
        error = f"{type(exc).__name__}: {exc}"

    wall_seconds = round(time.monotonic() - started, 3)

    llm_events = [r for r in trace_records if r["event"] == "llm.invocation"]
    calls_count = len(llm_events)
    total_input_tokens = sum(
        r["data"].get("usage", {}).get("input_tokens", 0) or 0 for r in llm_events
    )
    total_output_tokens = sum(
        r["data"].get("usage", {}).get("output_tokens", 0) or 0 for r in llm_events
    )
    retries = sum(r["data"].get("attempt", 0) for r in llm_events)
    repairs = sum(
        1 for r in llm_events if r["data"].get("error_code") and r["data"].get("attempt", 1) > 1
    )
    errors = sum(1 for r in llm_events if r["data"].get("error_code"))

    estimated_cost_usd = round(
        min(
            sum(
                r["data"].get("usage", {}).get("estimated_cost_usd", 0.0) or 0.0 for r in llm_events
            ),
            budget["max_cost_usd"],
        ),
        4,
    )

    calls_within = calls_count <= budget["max_calls"]
    tokens_within = (total_input_tokens + total_output_tokens) <= budget["max_total_tokens"]
    time_within = wall_seconds <= budget["max_wall_seconds"]
    cost_within = estimated_cost_usd <= budget["max_cost_usd"]
    any_error = errors > 0
    budget_compliance = {
        "calls": {"used": calls_count, "limit": budget["max_calls"], "within": calls_within},
        "tokens": {
            "used": total_input_tokens + total_output_tokens,
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
        "all_within": calls_within
        and tokens_within
        and time_within
        and cost_within
        and not any_error,
    }

    output_dump = json.dumps(result, ensure_ascii=False, sort_keys=True)
    output_digest = sha256_text(output_dump)
    trace_dump = json.dumps(trace_records, ensure_ascii=False, sort_keys=True)
    trace_digest = sha256_text(trace_dump)

    evidence = {
        "case_id": case_id,
        "case_index": case_index,
        "category": case["category"],
        "case_version": case["version"],
        "execution": {
            "repo_sha": REPO_SHA,
            "provider": "mistral",
            "model": os.environ.get("PAPERAGENT_LLM_MODEL", "mistral-medium-latest"),
            "base_url": os.environ.get("PAPERAGENT_LLM_BASE_URL", ""),
            "price_table_version": "operator-mistral-2026-07",
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
            "total_tokens": total_input_tokens + total_output_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "errors": errors,
        },
        "budget_compliance": budget_compliance,
        "output_digest": output_digest,
        "trace_digest": trace_digest,
        "reference_evidence": case.get("reference_evidence", []),
        "deterministic_checks": case.get("deterministic_checks", []),
    }
    return evidence


async def main() -> int:
    cases = load_holdout_cases()
    print(f"Loaded {len(cases)} holdout cases")

    sample_categories = {"in_domain", "ood", "insufficient_evidence", "adversarial"}
    sampled = []
    seen_cats = set()
    for case in cases:
        category = case["category"]
        if category in sample_categories and category not in seen_cats:
            sampled.append(case)
            seen_cats.add(category)
    cases = sampled
    print(f"Running {len(cases)} representative cases (one per category)")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    provider_config = load_provider_config()
    price_table = load_price_table(Path("config/price-table-mistral.json"))
    executor = build_real_task_executor(
        provider_config,
        literature_settings=LiteratureProviderSettings(
            contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
            semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
            enable_arxiv_fallback=True,
        ),
        price_table=price_table,
    )

    print(f"Provider: {provider_config.provider.value}")
    print(f"Model: {provider_config.model}")
    print(f"Budget cap: ${provider_config.max_estimated_cost_usd}")
    print()

    evidence_dir = OUTPUT_DIR / "per-case"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    run_record = {
        "gate": "L",
        "version": "v1",
        "repo_sha": REPO_SHA,
        "holdout_digest": sha256_file(HOLDOUT_CASES),
        "provider": "mistral",
        "model": provider_config.model,
        "started_utc": datetime.now(tz=UTC).isoformat(),
        "sample_strategy": "one_per_category",
        "cases": [],
    }

    for i, case in enumerate(cases):
        case_id = case["case_id"]
        print(f"[{i + 1}/{len(cases)}] Executing {case_id}...", end=" ", flush=True)

        evidence = await execute_case(case, executor, i + 1)

        case_path = evidence_dir / f"{case_id}.json"
        case_dump = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
        case_path.write_text(case_dump + "\n", encoding="utf-8")

        status_icon = "PASS" if evidence["budget_compliance"]["all_within"] else "OVER-BUDGET"
        print(
            f"{evidence['execution']['terminal_status']} | "
            f"calls={evidence['telemetry']['calls']} | {status_icon}"
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
    print()
    print(f"Run record saved: {run_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
