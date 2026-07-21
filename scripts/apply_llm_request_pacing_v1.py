from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"missing patch marker in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: Path, marker: str, addition: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + addition.strip() + "\n", encoding="utf-8")


def patch_runtime_config_model() -> None:
    path = Path("src/paperagent/providers/runtime.py")
    replace_once(
        path,
        "    max_attempts: int = Field(default=2, ge=1, le=4)\n",
        "    max_attempts: int = Field(default=2, ge=1, le=4)\n"
        "    max_requests_per_minute: int | None = Field(default=None, ge=1)\n",
    )


def patch_env_config() -> None:
    path = Path("src/paperagent/providers/config.py")
    replace_once(
        path,
        '        max_attempts=int(values.get("PAPERAGENT_LLM_MAX_ATTEMPTS", "2")),\n',
        '        max_attempts=int(values.get("PAPERAGENT_LLM_MAX_ATTEMPTS", "2")),\n'
        '        max_requests_per_minute=(\n'
        '            int(values["PAPERAGENT_LLM_MAX_REQUESTS_PER_MINUTE"])\n'
        '            if values.get("PAPERAGENT_LLM_MAX_REQUESTS_PER_MINUTE")\n'
        '            else None\n'
        '        ),\n',
    )


def patch_factory() -> None:
    path = Path("src/paperagent/providers/runtime_factory.py")
    replace_once(
        path,
        "            max_retries=config.max_attempts - 1,\n",
        "            max_retries=config.max_attempts - 1,\n"
        "            max_requests_per_minute=config.max_requests_per_minute,\n",
    )


def patch_openai_provider() -> None:
    path = Path("src/paperagent/providers/openai_llm.py")
    replace_once(
        path,
        "from paperagent.providers.runtime import TaskBudget, UsageRecord\n",
        "from paperagent.providers.request_rate_limit import shared_request_rate_limiter\n"
        "from paperagent.providers.runtime import TaskBudget, UsageRecord\n",
    )
    replace_once(
        path,
        "        max_retries: int = 2,\n        temperature: float = 0.0,\n",
        "        max_retries: int = 2,\n"
        "        max_requests_per_minute: int | None = None,\n"
        "        temperature: float = 0.0,\n",
    )
    replace_once(
        path,
        "        if max_output_tokens is not None and max_output_tokens <= 0:\n"
        "            raise ValueError(\"max_output_tokens must be positive\")\n",
        "        if max_output_tokens is not None and max_output_tokens <= 0:\n"
        "            raise ValueError(\"max_output_tokens must be positive\")\n"
        "        if max_requests_per_minute is not None and max_requests_per_minute <= 0:\n"
        "            raise ValueError(\"max_requests_per_minute must be positive\")\n",
    )
    replace_once(
        path,
        "        self._max_retries = max_retries\n        self._temperature = temperature\n",
        "        self._max_retries = max_retries\n"
        "        self._max_requests_per_minute = max_requests_per_minute\n"
        "        self._temperature = temperature\n",
    )
    replace_once(
        path,
        "            started = time.perf_counter()\n            try:\n",
        "            if self._max_requests_per_minute is not None:\n"
        "                limiter = shared_request_rate_limiter(\n"
        "                    namespace=f\"{self._base_url}|{self._model}\",\n"
        "                    requests_per_minute=self._max_requests_per_minute,\n"
        "                )\n"
        "                await limiter.acquire()\n"
        "            started = time.perf_counter()\n"
        "            try:\n",
    )


def patch_tests() -> None:
    path = Path("tests/providers/test_openai_llm_runtime_limits.py")
    replace_once(
        path,
        "from paperagent.providers.openai_llm import OpenAILLMProvider\n",
        "from paperagent.providers.openai_llm import OpenAILLMProvider\n"
        "from paperagent.providers.request_rate_limit import AsyncRequestRateLimiter\n",
    )
    replace_once(
        path,
        "        max_attempts=1,\n        max_output_tokens_per_call=123,\n",
        "        max_attempts=1,\n"
        "        max_requests_per_minute=40,\n"
        "        max_output_tokens_per_call=123,\n",
    )
    replace_once(
        path,
        "    assert isinstance(provider, OpenAILLMProvider)\n    reply = _generate(provider)\n",
        "    assert isinstance(provider, OpenAILLMProvider)\n"
        "    assert provider._max_requests_per_minute == 40\n"
        "    reply = _generate(provider)\n",
    )
    replace_once(
        path,
        '            "PAPERAGENT_LLM_NATIVE_JSON_SCHEMA": "off",\n',
        '            "PAPERAGENT_LLM_NATIVE_JSON_SCHEMA": "off",\n'
        '            "PAPERAGENT_LLM_MAX_REQUESTS_PER_MINUTE": "40",\n',
    )
    replace_once(
        path,
        "    assert config.native_json_schema is False\n",
        "    assert config.native_json_schema is False\n"
        "    assert config.max_requests_per_minute == 40\n",
    )
    append_once(
        path,
        "def test_request_rate_limiter_smooths_forty_requests_per_minute(",
        '''
def test_request_rate_limiter_smooths_forty_requests_per_minute() -> None:
    now = [0.0]
    sleeps: list[float] = []

    def clock() -> float:
        return now[0]

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    async def scenario() -> None:
        limiter = AsyncRequestRateLimiter(40, clock=clock, sleep=sleep)
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()

    asyncio.run(scenario())

    assert sleeps == [1.5, 1.5]
''',
    )


def main() -> None:
    patch_runtime_config_model()
    patch_env_config()
    patch_factory()
    patch_openai_provider()
    patch_tests()


if __name__ == "__main__":
    main()
