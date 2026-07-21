from __future__ import annotations

from pathlib import Path

RUNNER = Path("scripts/run_academic_tailoring_retrieval_v1.py")
OPENAI = Path("src/paperagent/providers/openai_llm.py")
RUNNER_TEST = Path("tests/evals/test_academic_tailoring_runtime_checkpoint.py")
OPENAI_TEST = Path("tests/providers/test_openai_llm_http_errors.py")


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
        '''def _append_jsonl(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\\n")


def _assert_no_forbidden_keys(value: object, *, path: str = "$") -> None:
''',
        '''def _append_jsonl(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\\n")


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
            str(case["case_id"])
            for case in cases
            if str(case["case_id"]) not in attempted
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
            completed_case_count == len(cases)
            and fatal_provider_error is None
            and not errors
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
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\\n"
            for item in states
        ),
        encoding="utf-8",
    )
    (output_dir / "run-traces.jsonl").write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\\n"
            for item in traces
        ),
        encoding="utf-8",
    )
    _write_json(output_dir / "execution-summary.json", summary)


def _assert_no_forbidden_keys(value: object, *, path: str = "$") -> None:
''',
        "runtime checkpoint helpers",
    )
    replace_once(
        RUNNER,
        '''    fatal_provider_error: dict[str, str] | None = None
    for index, (case, search_budget) in enumerate(zip(cases, budgets, strict=True), start=1):
''',
        '''    fatal_provider_error: dict[str, str] | None = None

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
''',
        "checkpoint closure",
    )
    replace_once(
        RUNNER,
        '''        finally:
            await search_runtime.aclose()

    states_path = output_dir / "states.jsonl"
''',
        '''        finally:
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

    states_path = output_dir / "states.jsonl"
''',
        "per-case checkpoint",
    )
    start = '''    states_path = output_dir / "states.jsonl"
    traces_path = output_dir / "run-traces.jsonl"
    states_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\\n" for item in states),
        encoding="utf-8",
    )
    traces_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\\n" for item in traces),
        encoding="utf-8",
    )
    summary = {
        "schema": "paperagent.academic-tailoring-retrieval.runtime-summary.v1",
        "source_sha": os.getenv("PAPERAGENT_SOURCE_SHA") or os.getenv("GITHUB_SHA"),
        "public_dataset_sha256": dataset.get("public_sha256"),
        "selected_case_ids": [str(case["case_id"]) for case in cases],
        "selected_case_count": len(cases),
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
        "static_leakage_audit": {
            "passed": leakage_audit.passed,
            "findings": list(leakage_audit.findings),
        },
        "prompt_records": sum(
            1 for line in prompt_log.read_text(encoding="utf-8").splitlines() if line
        ),
        "gold_absent_from_candidate_workspace": not args.allow_gold_in_workspace,
        "passed": (
            completed_case_count == len(cases) and fatal_provider_error is None and not errors
        ),
    }
    _write_json(output_dir / "execution-summary.json", summary)
'''
    replace_once(
        RUNNER,
        start,
        '''    summary = persist_checkpoint()
''',
        "deduplicate final outputs",
    )


def patch_openai() -> None:
    replace_once(
        OPENAI,
        '''from paperagent.providers.runtime import TaskBudget, UsageRecord
''',
        '''from paperagent.providers.runtime import ProviderErrorCode, TaskBudget, UsageRecord
''',
        "provider error code import",
    )
    replace_once(
        OPENAI,
        '''def _strip_markdown_fence(text: str) -> str:
''',
        '''def _classify_http_status(status_code: int) -> tuple[ProviderErrorCode, bool]:
    if status_code == 401:
        return ProviderErrorCode.AUTHENTICATION, False
    if status_code == 403:
        return ProviderErrorCode.PERMISSION, False
    if status_code == 429:
        return ProviderErrorCode.RATE_LIMITED, True
    if 500 <= status_code <= 599:
        return ProviderErrorCode.PROVIDER_5XX, True
    return ProviderErrorCode.INVALID_REQUEST, False


def _strip_markdown_fence(text: str) -> str:
''',
        "HTTP classification helper",
    )
    replace_once(
        OPENAI,
        '''            except HTTPError as exc:
                raise ProviderError(
                    f"OpenAI-compatible HTTP {exc.code}",
                    provider=self.provider_name,
                    task=task,
                    retryable=False,
                    code="LLM_PROVIDER_HTTP_ERROR",
                ) from exc
''',
        '''            except HTTPError as exc:
                error_code, retryable = _classify_http_status(exc.code)
                raise ProviderError(
                    f"OpenAI-compatible HTTP {exc.code}",
                    provider=self.provider_name,
                    task=task,
                    retryable=retryable,
                    code=f"LLM_{error_code.value.upper()}",
                    error_code=error_code,
                ) from exc
''',
        "precise HTTP provider errors",
    )


def write_tests() -> None:
    write(
        RUNNER_TEST,
        '''from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).parents[2] / "scripts" / "run_academic_tailoring_retrieval_v1.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("runtime_checkpoint_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_summary_tracks_partial_progress_without_false_pass() -> None:
    module = _load_script()
    summary = module._build_runtime_summary(
        cases=[{"case_id": "a"}, {"case_id": "b"}],
        dataset={"public_sha256": "sha256:test"},
        attempted_case_ids=["a"],
        completed_case_count=1,
        traces=[{"case_id": "a"}],
        errors=[],
        fatal_provider_error=None,
        prompt_records=4,
        leakage_passed=True,
        leakage_findings=[],
        allow_gold_in_workspace=False,
    )
    assert summary["completed"] == 1
    assert summary["not_run_case_ids"] == ["b"]
    assert summary["passed"] is False


def test_runtime_outputs_are_rewritten_as_valid_checkpoints(tmp_path: Path) -> None:
    module = _load_script()
    summary = {"schema": "runtime", "completed": 1, "passed": False}
    module._write_runtime_outputs(
        output_dir=tmp_path,
        states=[{"case_id": "a", "state": {"status": "done"}}],
        traces=[{"case_id": "a", "terminal_status": "completed"}],
        summary=summary,
    )
    states = [json.loads(line) for line in (tmp_path / "states.jsonl").read_text().splitlines()]
    traces = [
        json.loads(line) for line in (tmp_path / "run-traces.jsonl").read_text().splitlines()
    ]
    persisted_summary = json.loads((tmp_path / "execution-summary.json").read_text())
    assert states[0]["case_id"] == "a"
    assert traces[0]["case_id"] == "a"
    assert persisted_summary == summary
''',
    )
    write(
        OPENAI_TEST,
        '''from __future__ import annotations

from paperagent.providers.openai_llm import _classify_http_status
from paperagent.providers.runtime import ProviderErrorCode


def test_openai_http_status_classification_preserves_retry_semantics() -> None:
    assert _classify_http_status(401) == (ProviderErrorCode.AUTHENTICATION, False)
    assert _classify_http_status(403) == (ProviderErrorCode.PERMISSION, False)
    assert _classify_http_status(429) == (ProviderErrorCode.RATE_LIMITED, True)
    assert _classify_http_status(500) == (ProviderErrorCode.PROVIDER_5XX, True)
    assert _classify_http_status(503) == (ProviderErrorCode.PROVIDER_5XX, True)
    assert _classify_http_status(400) == (ProviderErrorCode.INVALID_REQUEST, False)
    assert _classify_http_status(404) == (ProviderErrorCode.INVALID_REQUEST, False)
''',
    )


def main() -> int:
    patch_runner()
    patch_openai()
    write_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
