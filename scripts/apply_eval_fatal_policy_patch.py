from __future__ import annotations

from pathlib import Path

RUNNER = Path("scripts/run_academic_tailoring_retrieval_v1.py")
TEST = Path("tests/evals/test_eval_runtime_reporting.py")


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match, found {count}: {old[:120]!r}")
    return text.replace(old, new, 1)


def main() -> int:
    runner = RUNNER.read_text(encoding="utf-8")
    runner = replace_once(
        runner,
        """from paperagent.eval_runtime_reporting import (
    build_error_record,
""",
        """from paperagent.eval_runtime_reporting import (
    build_error_record,
    classify_error,
""",
    )
    runner = replace_once(
        runner,
        """_FATAL_PROVIDER_ERROR_CODES = frozenset(
    {
        *(
            f"LLM_{code.value.upper()}"
            for code in (
                ProviderErrorCode.CONFIGURATION,
                ProviderErrorCode.AUTHENTICATION,
                ProviderErrorCode.PERMISSION,
                ProviderErrorCode.RATE_LIMITED,
                ProviderErrorCode.READ_TIMEOUT,
                ProviderErrorCode.CANCELLED,
                ProviderErrorCode.UNKNOWN,
            )
        ),
        "LLM_PROVIDER_HTTP_ERROR",
        "LLM_TIMEOUT",
        "LLM_INVALID_REQUEST",
        "LLM_RESPONSE_FORMAT_UNSUPPORTED",
    }
)


""",
        "",
    )
    runner = replace_once(
        runner,
        """        if normalized in _FATAL_PROVIDER_ERROR_CODES:
            return normalized
""",
        """        if normalized is not None and should_stop_run(
            classify_error(error_code=normalized, retryable=False)
        ):
            return normalized
""",
    )
    RUNNER.write_text(runner, encoding="utf-8")

    test = TEST.read_text(encoding="utf-8")
    marker = "def test_runner_trace_fatal_policy_uses_shared_classifier() -> None:"
    if marker not in test:
        test += """


def test_runner_trace_fatal_policy_uses_shared_classifier() -> None:
    import importlib.util

    script = Path(__file__).parents[2] / "scripts" / "run_academic_tailoring_retrieval_v1.py"
    spec = importlib.util.spec_from_file_location("academic_tailoring_runtime_runner", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module._fatal_provider_error_code_from_trace(
        {"trace_error_codes": ["LLM_AUTHENTICATION"]}
    ) == "LLM_AUTHENTICATION"
    for code in (
        "LLM_RATE_LIMITED",
        "LLM_READ_TIMEOUT",
        "LLM_PROVIDER_5XX",
        "LLM_UNKNOWN",
    ):
        assert module._fatal_provider_error_code_from_trace(
            {"trace_error_codes": [code]}
        ) is None
"""
    TEST.write_text(test, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
