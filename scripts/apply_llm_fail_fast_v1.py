from __future__ import annotations

from pathlib import Path

RUNNER = Path("scripts/run_academic_tailoring_retrieval_v1.py")
WORKFLOW = Path(".github/workflows/academic-tailoring-retrieval-v1-live-test.yml")
HEALTH_SCRIPT = Path("scripts/check_llm_provider_health.py")
RUNTIME_TEST = Path("tests/evals/test_academic_tailoring_runtime_fail_fast.py")
HEALTH_TEST = Path("tests/scripts/test_check_llm_provider_health.py")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = path.read_text(encoding="utf-8")
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise RuntimeError(f"{path}: missing {label}")
    path.write_text(source, encoding="utf-8")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def patch_runner() -> None:
    replace_once(
        RUNNER,
        "from paperagent.providers.runtime_factory import build_llm_provider\n",
        "from paperagent.providers.runtime import ProviderError, ProviderErrorCode\n"
        "from paperagent.providers.runtime_factory import build_llm_provider\n",
        "provider error imports",
    )
    replace_once(
        RUNNER,
        'T = TypeVar("T", bound=BaseModel)\n',
        '''T = TypeVar("T", bound=BaseModel)
_FATAL_PROVIDER_ERROR_CODES = frozenset(
    {
        "LLM_AUTHENTICATION",
        "LLM_CONFIGURATION",
        "LLM_PERMISSION",
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
''',
        "fatal provider policy",
    )
    replace_once(
        RUNNER,
        '''    states: list[dict[str, object]] = []
    traces: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    for index, (case, search_budget) in enumerate(zip(cases, budgets, strict=True), start=1):
        case_id = str(case["case_id"])
''',
        '''    states: list[dict[str, object]] = []
    traces: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    attempted_case_ids: list[str] = []
    completed_case_count = 0
    fatal_provider_error: dict[str, str] | None = None
    for index, (case, search_budget) in enumerate(zip(cases, budgets, strict=True), start=1):
        case_id = str(case["case_id"])
        attempted_case_ids.append(case_id)
''',
        "runtime counters",
    )
    replace_once(
        RUNNER,
        '''        llm = AuditedLLMProvider(
            build_llm_provider(case_provider_config, price_table),
            prompt_log=prompt_log,
            case_id=case_id,
        )
        try:
            benchmark_input = BenchmarkInput.model_validate(case["benchmark_input"])
''',
        '''        try:
            llm = AuditedLLMProvider(
                build_llm_provider(case_provider_config, price_table),
                prompt_log=prompt_log,
                case_id=case_id,
            )
            benchmark_input = BenchmarkInput.model_validate(case["benchmark_input"])
''',
        "provider construction inside error boundary",
    )
    replace_once(
        RUNNER,
        '''            states.append({"case_id": case_id, "state": state})
            traces.append(trace.model_dump(mode="json", by_alias=True))
        except Exception as exc:
            errors.append(
                {
                    "case_id": case_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
        finally:
            await search_runtime.aclose()
''',
        '''            trace_payload = trace.model_dump(mode="json", by_alias=True)
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
''',
        "fatal provider short circuit",
    )
    replace_once(
        RUNNER,
        '''        "selected_case_count": len(cases),
        "completed": len(traces),
        "errors": errors,
''',
        '''        "selected_case_count": len(cases),
        "attempted_case_ids": attempted_case_ids,
        "not_run_case_ids": [
            str(case["case_id"])
            for case in cases
            if str(case["case_id"]) not in set(attempted_case_ids)
        ],
        "recorded_traces": len(traces),
        "completed": completed_case_count,
        "fatal_provider_error": fatal_provider_error,
        "errors": errors,
''',
        "runtime summary failure fields",
    )
    replace_once(
        RUNNER,
        '        "passed": len(traces) == len(cases) and not errors,\n',
        '''        "passed": (
            completed_case_count == len(cases)
            and fatal_provider_error is None
            and not errors
        ),
''',
        "runtime pass semantics",
    )


def write_health_script() -> None:
    write(
        HEALTH_SCRIPT,
        '''from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

SCHEMA = "paperagent.llm-provider-health.v1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a redacted LLM credential health check")
    parser.add_argument("--provider", choices=["mistral"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-env", default="MISTRAL_API_KEY")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    return parser


def _status_name(status_code: int) -> str:
    if status_code == 401:
        return "authentication"
    if status_code == 403:
        return "permission"
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code <= 599:
        return "provider_5xx"
    if status_code >= 400:
        return "invalid_request"
    return "ok"


def _model_ids(payload: object) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    data = payload.get("data")
    if not isinstance(data, list):
        return set()
    identifiers: set[str] = set()
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            identifiers.add(item["id"])
    return identifiers


def _write_result(path: Path | None, result: dict[str, Any]) -> None:
    serialized = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(serialized, end="")
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialized, encoding="utf-8")


def _result(
    *,
    provider: str,
    model: str,
    base_url: str,
    status: str,
    http_status: int | None = None,
    model_accessible: bool | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "provider": provider,
        "model": model,
        "base_url_host": urlsplit(base_url).hostname,
        "status": status,
        "http_status": http_status,
        "model_accessible": model_accessible,
        "credential_present": True,
    }


def main() -> int:
    args = _parser().parse_args()
    api_key = os.getenv(args.api_key_env, "").strip()
    if not api_key:
        result = _result(
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            status="configuration",
        )
        result["credential_present"] = False
        _write_result(args.output, result)
        return 2

    request = Request(
        f"{args.base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=args.timeout_seconds) as response:
            status_code = response.status
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        result = _result(
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            status=_status_name(exc.code),
            http_status=exc.code,
        )
        _write_result(args.output, result)
        return 3
    except (URLError, TimeoutError, OSError):
        result = _result(
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            status="connect",
        )
        _write_result(args.output, result)
        return 4
    except (UnicodeDecodeError, json.JSONDecodeError):
        result = _result(
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            status="malformed_response",
        )
        _write_result(args.output, result)
        return 5

    if status_code >= 400:
        result = _result(
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            status=_status_name(status_code),
            http_status=status_code,
        )
        _write_result(args.output, result)
        return 3

    identifiers = _model_ids(payload)
    model_accessible = args.model in identifiers
    result = _result(
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        status="ok" if model_accessible else "model_unavailable",
        http_status=status_code,
        model_accessible=model_accessible,
    )
    _write_result(args.output, result)
    return 0 if model_accessible else 6


if __name__ == "__main__":
    raise SystemExit(main())
''',
    )


def patch_workflow() -> None:
    replace_once(
        WORKFLOW,
        '      - "scripts/run_academic_tailoring_retrieval_v1.py"\n',
        '      - "scripts/run_academic_tailoring_retrieval_v1.py"\n'
        '      - "scripts/check_llm_provider_health.py"\n',
        "push health script trigger",
    )
    source = WORKFLOW.read_text(encoding="utf-8")
    second = '      - "scripts/run_academic_tailoring_retrieval_v1.py"\n'
    first_index = source.find(second)
    second_index = source.find(second, first_index + len(second))
    if second_index >= 0 and '      - "scripts/check_llm_provider_health.py"\n' not in source[
        second_index : second_index + 150
    ]:
        source = source[: second_index + len(second)] + (
            '      - "scripts/check_llm_provider_health.py"\n'
        ) + source[second_index + len(second) :]
        WORKFLOW.write_text(source, encoding="utf-8")
    replace_once(
        WORKFLOW,
        '''          ruff format --check \\
            scripts/project_academic_tailoring_retrieval_v1.py \\
            scripts/run_academic_tailoring_retrieval_v1.py \\
            scripts/score_academic_tailoring_retrieval_v1.py \\
''',
        '''          ruff format --check \\
            scripts/check_llm_provider_health.py \\
            scripts/project_academic_tailoring_retrieval_v1.py \\
            scripts/run_academic_tailoring_retrieval_v1.py \\
            scripts/score_academic_tailoring_retrieval_v1.py \\
''',
        "format health script",
    )
    replace_once(
        WORKFLOW,
        '''          ruff check \\
            scripts/project_academic_tailoring_retrieval_v1.py \\
            scripts/run_academic_tailoring_retrieval_v1.py \\
            scripts/score_academic_tailoring_retrieval_v1.py \\
''',
        '''          ruff check \\
            scripts/check_llm_provider_health.py \\
            scripts/project_academic_tailoring_retrieval_v1.py \\
            scripts/run_academic_tailoring_retrieval_v1.py \\
            scripts/score_academic_tailoring_retrieval_v1.py \\
''',
        "lint health script",
    )
    replace_once(
        WORKFLOW,
        '''      - name: Require real LLM credential
        run: test -n "$MISTRAL_API_KEY"
      - name: Build isolated candidate workspace
''',
        '''      - name: Require non-empty real LLM credential
        run: test -n "$MISTRAL_API_KEY"
      - name: Probe real LLM credential and model access
        id: llm_health
        shell: bash
        run: |
          set +e
          python scripts/check_llm_provider_health.py \\
            --provider mistral \\
            --model mistral-small-latest \\
            --base-url https://api.mistral.ai/v1 \\
            --output build/academic-tailoring-retrieval-v1/llm-health.json
          status=$?
          echo "status=$status" >> "$GITHUB_OUTPUT"
          exit 0
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: academic-tailoring-retrieval-v1-llm-health
          path: build/academic-tailoring-retrieval-v1/llm-health.json
          if-no-files-found: error
          retention-days: 7
      - name: Enforce real LLM health
        run: test "${{ steps.llm_health.outputs.status }}" = "0"
      - name: Build isolated candidate workspace
''',
        "workflow provider preflight",
    )
    replace_once(
        WORKFLOW,
        '''  score-and-audit:
    needs: candidate-live-run
    if: always()
''',
        '''  score-and-audit:
    needs: candidate-live-run
    if: needs.candidate-live-run.result == 'success'
''',
        "skip scoring after runtime failure",
    )


def write_tests() -> None:
    write(
        RUNTIME_TEST,
        '''from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).parents[2] / "scripts" / "run_academic_tailoring_retrieval_v1.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_academic_tailoring_retrieval_v1", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fatal_authentication_trace_is_detected() -> None:
    module = _load_script()
    assert module._fatal_provider_error_code_from_trace(
        {"module_defer_reason": "LLM_AUTHENTICATION", "trace_error_codes": []}
    ) == "LLM_AUTHENTICATION"


def test_fatal_permission_code_is_detected_from_trace_errors() -> None:
    module = _load_script()
    assert module._fatal_provider_error_code_from_trace(
        {"module_defer_reason": None, "trace_error_codes": ["LLM_PERMISSION"]}
    ) == "LLM_PERMISSION"


def test_transient_and_scientific_codes_do_not_abort_the_suite() -> None:
    module = _load_script()
    assert module._fatal_provider_error_code_from_trace(
        {
            "module_defer_reason": "LLM_RATE_LIMITED",
            "trace_error_codes": ["NOT_EVALUATED", "FINAL_OUTCOME_AND_REPORT_PRESENT"],
        }
    ) is None
''',
    )
    write(
        HEALTH_TEST,
        '''from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).parents[2] / "scripts" / "check_llm_provider_health.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_llm_provider_health", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_health_status_classification_is_precise() -> None:
    module = _load_script()
    assert module._status_name(401) == "authentication"
    assert module._status_name(403) == "permission"
    assert module._status_name(429) == "rate_limited"
    assert module._status_name(503) == "provider_5xx"
    assert module._status_name(400) == "invalid_request"
    assert module._status_name(200) == "ok"


def test_model_ids_ignore_malformed_entries() -> None:
    module = _load_script()
    assert module._model_ids(
        {"data": [{"id": "mistral-small-latest"}, {"name": "missing-id"}, "bad"]}
    ) == {"mistral-small-latest"}


def test_redacted_result_never_contains_credential_material() -> None:
    module = _load_script()
    result = module._result(
        provider="mistral",
        model="mistral-small-latest",
        base_url="https://api.mistral.ai/v1",
        status="authentication",
        http_status=401,
    )
    assert result["base_url_host"] == "api.mistral.ai"
    assert "api_key" not in result
    assert "authorization" not in result
''',
    )


def main() -> int:
    patch_runner()
    write_health_script()
    patch_workflow()
    write_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
