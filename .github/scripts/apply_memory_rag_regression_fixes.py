from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    file.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "tests/providers/test_openai_llm_unit.py",
    "    assert sleeps == [0.5]\n",
    "    assert sleeps == [15.0]\n",
)
replace_once(
    "tests/providers/test_openai_llm_unit.py",
    '    assert exc_info.value.code == "LLM_PROVIDER_HTTP_ERROR"\n'
    "    assert exc_info.value.retryable is False\n",
    '    assert exc_info.value.code == "LLM_AUTHENTICATION"\n'
    "    assert exc_info.value.retryable is False\n",
)
replace_once(
    "tests/providers/test_openai_llm_unit.py",
    "    async def fake_sleep(delay: float) -> None:\n"
    "        assert delay == 0.5\n",
    "    async def fake_sleep(delay: float) -> None:\n"
    "        assert delay == 15.0\n",
)
replace_once(
    "tests/providers/test_openai_llm_unit.py",
    '    assert exc_info.value.code == "LLM_PROVIDER_HTTP_ERROR"\n'
    "    assert exc_info.value.retryable is True\n",
    '    assert exc_info.value.code == "LLM_CONNECT"\n'
    "    assert exc_info.value.retryable is True\n",
)
