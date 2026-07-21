from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"expected patch marker missing in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: Path, marker: str, addition: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + addition.strip() + "\n", encoding="utf-8")


def patch_openai_provider() -> None:
    path = Path("src/paperagent/providers/openai_llm.py")
    replace_once(
        path,
        '_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (0.5, 1.0, 2.0)\n',
        '_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (0.5, 1.0, 2.0)\n'
        '_RATE_LIMIT_BACKOFF_SECONDS: tuple[float, ...] = (15.0, 30.0, 60.0)\n'
        '_MAX_RETRY_AFTER_SECONDS = 300.0\n',
    )
    replace_once(
        path,
        '''                code, retryable = self._classify_http_status(status)
                if retryable and attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
''',
        '''                code, retryable = self._classify_http_status(status)
                if retryable and attempt < self._max_retries:
                    await asyncio.sleep(self._http_retry_delay(exc.response, attempt))
                    continue
''',
    )
    replace_once(
        path,
        '''    @staticmethod
    def _classify_http_status(status: int) -> tuple[str, bool]:
''',
        '''    @classmethod
    def _http_retry_delay(cls, response: httpx.Response, attempt: int) -> float:
        if response.status_code != 429:
            return cls._retry_delay(attempt)
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                parsed = float(retry_after)
            except ValueError:
                parsed = -1.0
            if parsed >= 0:
                return min(parsed, _MAX_RETRY_AFTER_SECONDS)
        return _RATE_LIMIT_BACKOFF_SECONDS[
            min(attempt, len(_RATE_LIMIT_BACKOFF_SECONDS) - 1)
        ]

    @staticmethod
    def _classify_http_status(status: int) -> tuple[str, bool]:
''',
    )


def patch_runtime_runner() -> None:
    path = Path("scripts/run_academic_tailoring_retrieval_v1.py")
    replace_once(
        path,
        '''_FATAL_PROVIDER_ERROR_CODES = frozenset(
    {
        "LLM_AUTHENTICATION",
        "LLM_CONFIGURATION",
        "LLM_PERMISSION",
    }
)
''',
        '''_FATAL_PROVIDER_ERROR_CODES = frozenset(
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
''',
    )
    replace_once(
        path,
        '''                )
                break
            completed_case_count += 1
''',
        '''                )
                break
            execution = state.get("execution")
            execution_status = (
                execution.get("status") if isinstance(execution, dict) else None
            )
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
''',
    )


def patch_provider_tests() -> None:
    path = Path("tests/providers/test_openai_llm_runtime_limits.py")
    append_once(
        path,
        "def test_retry_after_header_controls_rate_limit_backoff(",
        '''
def test_retry_after_header_controls_rate_limit_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    responses = iter(
        [
            httpx.Response(
                429,
                json={"error": {"message": "rate limited"}},
                headers={"Retry-After": "17"},
                request=httpx.Request(
                    "POST", "https://example.test/v1/chat/completions"
                ),
            ),
            _response(
                200,
                {"choices": [{"message": {"content": '{"status":"ok"}'}}]},
            ),
        ]
    )
    _install_fake_client(monkeypatch, responses, captured)
    provider = OpenAILLMProvider(
        api_key="test-key",
        model="z-ai/glm-5.2",
        base_url="https://example.test/v1",
        max_retries=1,
    )

    reply = _generate(provider)

    assert reply.status == "ok"
    assert sleeps == [17.0]


def test_rate_limit_without_header_uses_long_backoff() -> None:
    response = httpx.Response(
        429,
        request=httpx.Request("POST", "https://example.test/v1/chat/completions"),
    )

    assert OpenAILLMProvider._http_retry_delay(response, 0) == 15.0
    assert OpenAILLMProvider._http_retry_delay(response, 1) == 30.0
    assert OpenAILLMProvider._http_retry_delay(response, 9) == 60.0
''',
    )


def patch_fail_fast_tests() -> None:
    path = Path("tests/evals/test_academic_tailoring_runtime_fail_fast.py")
    replace_once(
        path,
        '''def test_transient_and_scientific_codes_do_not_abort_the_suite() -> None:
    module = _load_script()
    assert (
        module._fatal_provider_error_code_from_trace(
            {
                "module_defer_reason": "LLM_RATE_LIMITED",
                "trace_error_codes": ["NOT_EVALUATED", "FINAL_OUTCOME_AND_REPORT_PRESENT"],
            }
        )
        is None
    )
''',
        '''def test_exhausted_rate_limit_trace_aborts_the_suite() -> None:
    module = _load_script()
    assert (
        module._fatal_provider_error_code_from_trace(
            {
                "module_defer_reason": "LLM_RATE_LIMITED",
                "trace_error_codes": ["NOT_EVALUATED", "FINAL_OUTCOME_AND_REPORT_PRESENT"],
            }
        )
        == "LLM_RATE_LIMITED"
    )


def test_scientific_trace_codes_do_not_abort_the_suite() -> None:
    module = _load_script()
    assert (
        module._fatal_provider_error_code_from_trace(
            {
                "module_defer_reason": None,
                "trace_error_codes": ["NOT_EVALUATED", "FINAL_OUTCOME_AND_REPORT_PRESENT"],
            }
        )
        is None
    )
''',
    )


def patch_workflows() -> None:
    live = Path(".github/workflows/academic-tailoring-retrieval-v1-live-test.yml")
    replace_once(
        live,
        '''  candidate-live-run:
    needs: prepare-public-inputs
    runs-on: ubuntu-24.04
    timeout-minutes: 300
''',
        '''  candidate-live-run:
    needs: prepare-public-inputs
    concurrency:
      group: paperagent-nvidia-glm52
      cancel-in-progress: false
    runs-on: ubuntu-24.04
    timeout-minutes: 300
''',
    )
    replace_once(
        live,
        '      PAPERAGENT_LLM_MAX_ATTEMPTS: "2"\n',
        '      PAPERAGENT_LLM_MAX_ATTEMPTS: "4"\n',
    )

    hardening = Path(".github/workflows/glm52-runtime-hardening.yml")
    replace_once(
        hardening,
        '''  live-structured-smoke:
    needs: offline-runtime-contract
    if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-24.04
''',
        '''  live-structured-smoke:
    needs: offline-runtime-contract
    if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository
    concurrency:
      group: paperagent-nvidia-glm52
      cancel-in-progress: false
    runs-on: ubuntu-24.04
''',
    )
    replace_once(
        hardening,
        '      PAPERAGENT_LLM_MAX_ATTEMPTS: "1"\n',
        '      PAPERAGENT_LLM_MAX_ATTEMPTS: "4"\n',
    )
    replace_once(
        hardening,
        '      PAPERAGENT_LLM_MAX_OUTPUT_TOKENS_PER_CALL: "64"\n',
        '      PAPERAGENT_LLM_MAX_OUTPUT_TOKENS_PER_CALL: "512"\n',
    )
    replace_once(
        hardening,
        '      PAPERAGENT_LLM_MAX_OUTPUT_TOKENS_PER_TASK: "128"\n',
        '      PAPERAGENT_LLM_MAX_OUTPUT_TOKENS_PER_TASK: "1024"\n',
    )


def main() -> None:
    patch_openai_provider()
    patch_runtime_runner()
    patch_provider_tests()
    patch_fail_fast_tests()
    patch_workflows()
    diagnostic = Path(".github/workflows/glm52-smoke-diagnostic.yml")
    if diagnostic.exists():
        diagnostic.unlink()


if __name__ == "__main__":
    main()
