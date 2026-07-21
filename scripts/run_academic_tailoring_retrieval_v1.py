from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from paperagent.benchmark_input import BenchmarkInput
from paperagent.benchmark_leakage_audit import audit_benchmark_execution_boundary
from paperagent.claw_benchmark_runtime import (
    build_benchmark_search_runtime,
    execute_benchmark_case,
)
from paperagent.claw_runtime_evidence import (
    allocate_case_budgets,
    provider_config_for_case,
)
from paperagent.literature.factory import LiteratureProviderSettings
from paperagent.pricing import load_price_table
from paperagent.providers.base import LLMProvider
from paperagent.providers.config import load_provider_config
from paperagent.providers.runtime import ProviderError, ProviderErrorCode
from paperagent.providers.runtime_factory import build_llm_provider
from paperagent.schemas import Message

PUBLIC_SCHEMA = "paperagent.academic-tailoring-retrieval.public.v1"
FORBIDDEN_KEYS = {
    "gold",
    "expected_assets",
    "baseline_decision",
    "reference_hypothesis",
    "compatibility_judgment",
    "minimal_method",
    "experiments",
    "stop_conditions",
    "allowed_alternatives",
    "hard_failures",
    "cases_sha256",
}
T = TypeVar("T", bound=BaseModel)
_FATAL_PROVIDER_ERROR_CODES = frozenset(
    {
        "LLM_AUTHENTICATION",
        "LLM_CONFIGURATION",
        "LLM_PERMISSION",
        "LLM_RATE_LIMITED",
        "LLM_PROVIDER_HTTP_ERROR",
        "LLM_PROVIDER_5XX",
        "LLM_CONNECT",
        "LLM_TIMEOUT",
        "LLM_INVALID_REQUEST",
        "LLM_RESPONSE_FORMAT_UNSUPPORTED",
        "LLM_RESPONSE_JSON_INVALID",
        "LLM_RESPONSE_SCHEMA_INVALID",
    }
)


def _normalize_provider_error_code(value: object) -> str | None:
    if isinstance(value, ProviderErrorCode):
        return f"LLM_{value.value.upper()}"
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    upper = normalized.upper()
    if upper.startswith("LLM_"):
        return upper
    try:
        code = ProviderErrorCode(normalized.casefold())
    except ValueError:
        return None
    return f"LLM_{code.value.upper()}"


def _fatal_provider_error_code_from_trace(trace_payload: dict[str, object]) -> str | None:
    candidates: list[object] = [trace_payload.get("module_defer_reason")]
    trace_codes = trace_payload.get("trace_error_codes")
    if isinstance(trace_codes, list):
        candidates.extend(trace_codes)
    for candidate in candidates:
        normalized = _normalize_provider_error_code(candidate)
        if normalized in _FATAL_PROVIDER_ERROR_CODES:
            return normalized
    return None


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _build_runtime_summary(
    *,
    cases: list[dict[str, object]],
    dataset: dict[str, Any],
    attempted_case_ids: list[str],
    completed_case_count: int,
    traces: list[dict[str, object]],
    errors: list[dict[str, str]],
    fatal_provider_error: dict[str, str] | None,
    prompt_records: int,
    leakage_passed: bool,
    leakage_findings: list[str],
    allow_gold_in_workspace: bool,
) -> dict[str, object]:
    attempted = set(attempted_case_ids)
    return {
        "schema": "paperagent.academic-tailoring-retrieval.runtime-summary.v1",
        "source_sha": os.getenv("PAPERAGENT_SOURCE_SHA") or os.getenv("GITHUB_SHA"),
        "public_dataset_sha256": dataset.get("public_sha256"),
        "selected_case_ids": [str(case["case_id"]) for case in cases],
        "selected_case_count": len(cases),
        "attempted_case_ids": list(attempted_case_ids),
        "not_run_case_ids": [
            str(case["case_id"]) for case in cases if str(case["case_id"]) not in attempted
        ],
        "recorded_traces": len(traces),
        "completed": completed_case_count,
        "fatal_provider_error": fatal_provider_error,
        "errors": list(errors),
        "static_leakage_audit": {
            "passed": leakage_passed,
            "findings": list(leakage_findings),
        },
        "prompt_records": prompt_records,
        "gold_absent_from_candidate_workspace": not allow_gold_in_workspace,
        "passed": (
            completed_case_count == len(cases) and fatal_provider_error is None and not errors
        ),
    }


def _write_runtime_outputs(
    *,
    output_dir: Path,
    states: list[dict[str, object]],
    traces: list[dict[str, object]],
    summary: dict[str, object],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "states.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in states),
        encoding="utf-8",
    )
    (output_dir / "run-traces.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in traces),
        encoding="utf-8",
    )
    _write_json(output_dir / "execution-summary.json", summary)


def _assert_no_forbidden_keys(value: object, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                raise ValueError(f"forbidden key {key!r} present at {path}")
            _assert_no_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, path=f"{path}[{index}]")


def _load_public_dataset(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema") != PUBLIC_SCHEMA:
        raise ValueError("unexpected public dataset schema")
    _assert_no_forbidden_keys(raw)
    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("public dataset must contain cases")
    return raw


def _assert_gold_absent(root: Path) -> None:
    matches = sorted(root.rglob("dataset-authoring.json"))
    if matches:
        raise RuntimeError(f"candidate workspace contains Gold authoring data: {matches}")


class AuditedLLMProvider:
    def __init__(self, delegate: LLMProvider, *, prompt_log: Path, case_id: str) -> None:
        self._delegate = delegate
        self._prompt_log = prompt_log
        self._case_id = case_id

    def __getattr__(self, name: str) -> object:
        return getattr(self._delegate, name)

    async def generate_structured(
        self,
        *,
        task: str,
        scenario: str,
        call_index: int,
        fixture_version: str,
        schema: type[T],
        messages: list[Message],
    ) -> T:
        _append_jsonl(
            self._prompt_log,
            {
                "case_id": self._case_id,
                "task": task,
                "scenario": scenario,
                "call_index": call_index,
                "fixture_version": fixture_version,
                "response_schema": schema.__name__,
                "messages": [message.model_dump(mode="json") for message in messages],
            },
        )
        return await self._delegate.generate_structured(
            task=task,
            scenario=scenario,
            call_index=call_index,
            fixture_version=fixture_version,
            schema=schema,
            messages=messages,
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Gold-free academic tailoring retrieval set"
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--max-cases", type=int, default=10)
    parser.add_argument("--max-llm-calls", type=int, default=10)
    parser.add_argument("--provider-call-budget", type=int, default=80)
    parser.add_argument("--llm-provider", default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument("--llm-price-table", type=Path, default=None)
    parser.add_argument("--enable-web-search", action="store_true")
    parser.add_argument("--allow-gold-in-workspace", action="store_true")
    return parser


async def _run(args: argparse.Namespace) -> int:
    if not args.allow_gold_in_workspace:
        _assert_gold_absent(Path.cwd())
    dataset = _load_public_dataset(args.dataset)
    cases = list(dataset["cases"])
    selected = set(args.case_id)
    if selected:
        cases = [case for case in cases if case.get("case_id") in selected]
        missing = selected - {str(case.get("case_id")) for case in cases}
        if missing:
            raise ValueError(f"unknown case IDs: {sorted(missing)}")
    if not 1 <= args.max_cases <= 10:
        raise ValueError("--max-cases must be between 1 and 10")
    if args.max_llm_calls < 1 or args.provider_call_budget < 1:
        raise ValueError("LLM and provider budgets must be positive")
    cases = cases[: args.max_cases]

    leakage_audit = audit_benchmark_execution_boundary()
    if not leakage_audit.passed:
        raise RuntimeError(f"static leakage audit failed: {leakage_audit.findings}")

    output_dir: Path = args.output_dir
    prompt_log = output_dir / "prompt-log.jsonl"
    prompt_log.parent.mkdir(parents=True, exist_ok=True)
    prompt_log.write_text("", encoding="utf-8")

    provider_config = load_provider_config(
        provider=args.llm_provider,
        model=args.llm_model,
        base_url=args.llm_base_url,
    )
    price_table_path = args.llm_price_table
    if price_table_path is None and os.getenv("PAPERAGENT_LLM_PRICE_TABLE"):
        price_table_path = Path(os.environ["PAPERAGENT_LLM_PRICE_TABLE"])
    price_table = load_price_table(price_table_path) if price_table_path else None
    budgets = allocate_case_budgets(args.provider_call_budget, len(cases))
    case_provider_config = provider_config_for_case(
        provider_config,
        selected_case_count=len(cases),
    )

    states: list[dict[str, object]] = []
    traces: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    attempted_case_ids: list[str] = []
    completed_case_count = 0
    fatal_provider_error: dict[str, str] | None = None

    def persist_checkpoint() -> dict[str, object]:
        summary = _build_runtime_summary(
            cases=cases,
            dataset=dataset,
            attempted_case_ids=attempted_case_ids,
            completed_case_count=completed_case_count,
            traces=traces,
            errors=errors,
            fatal_provider_error=fatal_provider_error,
            prompt_records=sum(
                1 for line in prompt_log.read_text(encoding="utf-8").splitlines() if line
            ),
            leakage_passed=leakage_audit.passed,
            leakage_findings=list(leakage_audit.findings),
            allow_gold_in_workspace=args.allow_gold_in_workspace,
        )
        _write_runtime_outputs(
            output_dir=output_dir,
            states=states,
            traces=traces,
            summary=summary,
        )
        return summary

    persist_checkpoint()
    for index, (case, search_budget) in enumerate(zip(cases, budgets, strict=True), start=1):
        case_id = str(case["case_id"])
        attempted_case_ids.append(case_id)
        persist_checkpoint()
        search_runtime = build_benchmark_search_runtime(
            "literature",
            settings=LiteratureProviderSettings(
                contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
                semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
                tavily_api_key=os.getenv("TAVILY_API_KEY"),
                enable_web_search=bool(args.enable_web_search),
                max_provider_calls_total=search_budget,
            ),
        )
        try:
            llm = AuditedLLMProvider(
                build_llm_provider(case_provider_config, price_table),
                prompt_log=prompt_log,
                case_id=case_id,
            )
            benchmark_input = BenchmarkInput.model_validate(case["benchmark_input"])
            state, trace = await execute_benchmark_case(
                benchmark_input=benchmark_input,
                case_id=case_id,
                llm=llm,
                search=search_runtime.adapter,
                max_llm_calls=args.max_llm_calls,
                task_id=f"atr-v1-{index:02d}",
            )
            trace_payload = trace.model_dump(mode="json", by_alias=True)
            states.append({"case_id": case_id, "state": state})
            traces.append(trace_payload)
            fatal_code = _fatal_provider_error_code_from_trace(trace_payload)
            if fatal_code is not None:
                fatal_provider_error = {
                    "case_id": case_id,
                    "code": fatal_code,
                    "message": "fatal LLM provider failure surfaced in the case trace",
                }
                errors.append(
                    {
                        "case_id": case_id,
                        "error_type": "FatalLLMProviderError",
                        "message": fatal_code,
                    }
                )
                break
            execution = state.get("execution")
            execution_status = execution.get("status") if isinstance(execution, dict) else None
            if execution_status != "completed":
                errors.append(
                    {
                        "case_id": case_id,
                        "error_type": "CaseExecutionIncomplete",
                        "message": f"execution status was {execution_status!r}",
                    }
                )
                continue
            completed_case_count += 1
        except ProviderError as exc:
            normalized = _normalize_provider_error_code(exc.error_code) or exc.code
            errors.append(
                {
                    "case_id": case_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            if normalized in _FATAL_PROVIDER_ERROR_CODES:
                fatal_provider_error = {
                    "case_id": case_id,
                    "code": normalized,
                    "message": "fatal LLM provider failure raised before case completion",
                }
                break
        except Exception as exc:
            normalized = _normalize_provider_error_code(getattr(exc, "code", None))
            errors.append(
                {
                    "case_id": case_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            if normalized in _FATAL_PROVIDER_ERROR_CODES:
                fatal_provider_error = {
                    "case_id": case_id,
                    "code": normalized,
                    "message": "fatal LLM provider failure raised before case completion",
                }
                break
        finally:
            await search_runtime.aclose()
            checkpoint = persist_checkpoint()
            print(
                json.dumps(
                    {
                        "case_id": case_id,
                        "attempted": len(attempted_case_ids),
                        "completed": completed_case_count,
                        "errors": len(errors),
                        "fatal_provider_error": fatal_provider_error,
                        "passed_so_far": checkpoint["passed"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                flush=True,
            )

    summary = persist_checkpoint()
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


def main() -> int:
    return asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
