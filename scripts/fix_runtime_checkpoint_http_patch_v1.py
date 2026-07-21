from __future__ import annotations

from pathlib import Path

PATCH = Path("scripts/apply_runtime_checkpoint_http_errors_v1.py")


def main() -> int:
    source = PATCH.read_text(encoding="utf-8")
    start = source.index("def patch_openai() -> None:\n")
    end = source.index("\n\ndef write_tests() -> None:\n", start)
    replacement = '''def patch_openai() -> None:
    replace_once(
        OPENAI,
        "from paperagent.providers.runtime import TaskBudget, UsageRecord\\n",
        (
            "from paperagent.providers.runtime import "
            "ProviderErrorCode, TaskBudget, UsageRecord\\n"
        ),
        "provider error code import",
    )
    replace_once(
        OPENAI,
        "class OpenAILLMProvider:\\n",
        ''' + '"""' + '''def _classify_http_status(status_code: int) -> tuple[ProviderErrorCode, bool]:
    if status_code == 401:
        return ProviderErrorCode.AUTHENTICATION, False
    if status_code == 403:
        return ProviderErrorCode.PERMISSION, False
    if status_code == 429:
        return ProviderErrorCode.RATE_LIMITED, True
    if 500 <= status_code <= 599:
        return ProviderErrorCode.PROVIDER_5XX, True
    return ProviderErrorCode.INVALID_REQUEST, False


class OpenAILLMProvider:
''' + '"""' + ''',
        "HTTP classification helper",
    )
    replace_once(
        OPENAI,
        ''' + '"""' + '''                raise ProviderError(
                    f"HTTP {status} from {self.provider_name}",
                    provider=self.provider_name,
                    task=task,
                    retryable=retryable_status,
                    code="LLM_PROVIDER_HTTP_ERROR",
                ) from exc
''' + '"""' + ''',
        ''' + '"""' + '''                error_code, retryable = _classify_http_status(status)
                raise ProviderError(
                    f"HTTP {status} from {self.provider_name}",
                    provider=self.provider_name,
                    task=task,
                    retryable=retryable,
                    code=f"LLM_{error_code.value.upper()}",
                    error_code=error_code,
                ) from exc
''' + '"""' + ''',
        "precise HTTP provider errors",
    )
'''
    source = source[:start] + replacement + source[end:]
    PATCH.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
