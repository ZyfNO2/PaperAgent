from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match in {path}, found {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"updated {path}")


def append_once(path: Path, marker: str, addition: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"already present in {path}: {marker}")
        return
    path.write_text(text.rstrip() + "\n\n\n" + addition.strip() + "\n", encoding="utf-8")
    print(f"appended tests to {path}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    openai = root / "src/paperagent/providers/openai_llm.py"
    replace_once(
        openai,
        """    ) -> T:\n        del scenario, call_index, fixture_version\n        headers = _request_headers(self._api_key)\n""",
        """    ) -> T:\n        del scenario, fixture_version\n        budget_task = f\"{task}:invocation-{call_index}\"\n        headers = _request_headers(self._api_key)\n""",
    )
    replace_once(
        openai,
        """                    schema=schema,\n                    task=task,\n                )\n""",
        """                    schema=schema,\n                    task=task,\n                    budget_task=budget_task,\n                )\n""",
    )
    replace_once(
        openai,
        """                schema=schema,\n                task=task,\n            )\n        except _StructuredProviderError as fallback_error:\n""",
        """                schema=scheme,\n                task=task,\n                budget_task=budget_task,\n            )\n        except _StructuredProviderError as fallback_error:\n""",
    )
    replace_once(
        openai,
        """                schema=schema,\n                task=f\"{task}:schema-repair\",\n            )\n""",
        """                schema=scheme,\n                task=f\"{task}:schema-repair\",\n                budget_task=f\"{budget_task}:schema-repair\",\n            )\n""",
    )
    replace_once(
        openai,
        """        schema: type[T],\n        task: str,\n    ) -> T:\n""",
        """        schema: type[T],\n        task: str,\n        budget_task: str,\n    ) -> T:\n""",
    )
    replace_once(
        openai,
        """            if self._budget is not None:\n                self._budget.reserve_call(task=task)\n""",
        """            if self._budget is not None:\n                self._budget.reserve_call(task=budget_task)\n""",
    )
    replace_once(
        openai,
        """                        ),\n                        task=task,\n                    )\n                return self._parse_response(response, schema, task)\n""",
        """                        ),\n                        task=budget_task,\n                    )\n                return self._parse_response(response, schema, task)\n""",
    )

    mistral = root / "src/paperagent/providers/mistral.py"
    replace_once(
        mistral,
        """        logical_call_id = uuid4().hex\n        key = FixtureKey(\n""",
        """        logical_call_id = uuid4().hex\n        budget_task = f\"{task}:invocation-{call_index}\"\n        key = FixtureKey(\n""",
    )
    replace_once(
        mistral,
        """        for attempt in range(1, self._config.max_attempts + 1):\n            self._budget.reserve_call(task=task)\n""",
        """        for attempt in range(1, self._config.max_attempts + 1):\n            self._budget.reserve_call(task=budget_task)\n""",
    )
    replace_once(
        mistral,
        """                self._budget.record_usage(usage, task=task)\n""",
        """                self._budget.record_usage(usage, task=budget_task)\n""",
    )

    reporting = root / "src/paperagent/eval_runtime_reporting.py"
    replace_once(
        reporting,
        """_FATAL_BUDGET_CODES = frozenset(\n    {\n        \"LLM_BUDGET_EXHAUSTED\",\n        \"MAX_LLM_CALLS_EXCEEDED\",\n        \"MAX_RETRIEVAL_ROUNDS_EXCEEDED\",\n        \"TASK_BUDGET_EXHAUSTED\",\n    }\n)\n""",
        """_FATAL_BUDGET_CODES = frozenset(\n    {\n        \"GLOBAL_BUDGET_EXHAUSTED\",\n        \"PROVIDER_CALL_BUDGET_EXHAUSTED\",\n        \"RUN_BUDGET_EXHAUSTED\",\n    }\n)\n""",
    )

    openai_tests = root / "tests/providers/test_openai_llm_runtime_limits.py"
    replace_once(
        openai_tests,
        """from paperagent.providers.runtime import LLMProviderName, ProviderRuntimeConfig\n""",
        """from paperagent.providers.runtime import (\n    LLMProviderName,\n    ProviderRuntimeConfig,\n    TaskBudget,\n)\n""",
    )
    replace_once(
        openai_tests,
        """def _generate(provider: OpenAILLMProvider) -> _Reply:\n    return asyncio.run(\n        provider.generate_structured(\n            task=\"runtime-hardening-test\",\n            scenario=\"unit\",\n            call_index=1,\n""",
        """def _generate(provider: OpenAILLMProvider, *, call_index: int = 1) -> _Reply:\n    return asyncio.run(\n        provider.generate_structured(\n            task=\"runtime-hardening-test\",\n            scenario=\"unit\",\n            call_index=call_index,\n""",
    )
    append_once(
        openai_tests,
        "test_repeated_logical_invocations_receive_independent_task_budgets",
        r'''
def test_repeated_logical_invocations_receive_independent_task_budgets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    responses = iter(
        [
            _response(
                200,
                {
                    "choices": [{"message": {"content": '{"status":"ok"}'}}],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 1},
                },
            ),
            _response(
                200,
                {
                    "choices": [{"message": {"content": '{"status":"ok"}'}}],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 1},
                },
            ),
        ]
    )
    _install_fake_client(monkeypatch, responses, captured)
    config = ProviderRuntimeConfig(
        provider=LLMProviderName.OPENAI,
        model="z-ai/glm-5.2",
        api_key=SecretStr("test-key"),
        base_url="https://example.test/v1",
        max_attempts=1,
        max_input_tokens_per_task=25,
        max_output_tokens_per_call=8,
        max_output_tokens_per_task=8,
        max_llm_calls_per_task=1,
    )
    budget = TaskBudget(config)
    provider = OpenAILLMProvider(
        api_key="test-key",
        model="z-ai/glm-5.2",
        base_url="https://example.test/v1",
        max_retries=0,
        max_output_tokens=8,
        budget=budget,
    )

    assert _generate(provider, call_index=1).status == "ok"
    assert _generate(provider, call_index=2).status == "ok"
    assert budget.calls == 2


def test_physical_fallbacks_share_one_logical_invocation_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    responses = iter(
        [
            _response(
                400,
                {
                    "error": {
                        "type": "invalid_request_error",
                        "message": "response_format json_schema is unsupported",
                    }
                },
            )
        ]
    )
    _install_fake_client(monkeypatch, responses, captured)
    config = ProviderRuntimeConfig(
        provider=LLMProviderName.OPENAI,
        model="z-ai/glm-5.2",
        api_key=SecretStr("test-key"),
        base_url="https://example.test/v1",
        max_attempts=1,
        max_output_tokens_per_call=8,
        max_output_tokens_per_task=8,
        max_llm_calls_per_task=1,
    )
    provider = OpenAILLMProvider(
        api_key="test-key",
        model="z-ai/glm-5.2",
        base_url="https://example.test/v1",
        max_retries=0,
        max_output_tokens=8,
        budget=TaskBudget(config),
    )

    with pytest.raises(ProviderError) as error:
        _generate(provider, call_index=7)

    assert error.value.code == "LLM_BUDGET_EXHAUSTED"
    assert len(captured["requests"]) == 1
''',
    )

    reporting_tests = root / "tests/evals/test_eval_runtime_reporting.py"
    replace_once(
        reporting_tests,
        """    assert authentication[\"error_category\"] == RunErrorCategory.FATAL_PROVIDER\n    assert budget[\"error_category\"] == RunErrorCategory.FATAL_BUDGET\n    assert timeout[\"error_category\"] == RunErrorCategory.RETRYABLE\n    assert should_stop_run(str(authentication[\"error_category\"])) is True\n    assert should_stop_run(str(timeout[\"error_category\"])) is False\n""",
        """    global_budget = build_error_record(\n        case_id=\"case-4\",\n        error_code=\"RUN_BUDGET_EXHAUSTED\",\n        message=\"global budget\",\n        retryable=False,\n    )\n\n    assert authentication[\"error_category\"] == RunErrorCategory.FATAL_PROVIDER\n    assert budget[\"error_category\"] == RunErrorCategory.CASE_ERROR\n    assert global_budget[\"error_category\"] == RunErrorCategory.FATAL_BUDGET\n    assert timeout[\"error_category\"] == RunErrorCategory.RETRYABLE\n    assert should_stop_run(str(authentication[\"error_category\"])) is True\n    assert should_stop_run(str(budget[\"error_category\"])) is False\n    assert should_stop_run(str(global_budget[\"error_category\"])) is True\n    assert should_stop_run(str(timeout[\"error_category\"])) is False\n""",
    )
    replace_once(
        reporting_tests,
        """        \"LLM_PROVIDER_5XX\",\n        \"LLM_UNKNOWN\",\n""",
        """        \"LLM_PROVIDER_5XX\",\n        \"LLM_BUDGET_EXHAUSTED\",\n        \"LLM_UNKNOWN\",\n""",
    )


if __name__ == "__main__":
    main()
