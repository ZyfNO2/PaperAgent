from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

SCHEMA = "paperagent.llm-provider-health.v1"
_API_USER_AGENT = (
    "PaperAgent/0.9 (OpenAI-compatible API client; "
    "+https://github.com/ZyfNO2/PaperAgent)"
)
_TOKEN_LIKE_RE = re.compile(r"(?i)\b(?:sk|oc|key|token)[-_][A-Za-z0-9._-]{8,}\b")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a redacted LLM credential health check")
    parser.add_argument("--provider", choices=["mistral", "openai"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-env", default="MISTRAL_API_KEY")
    parser.add_argument("--probe-mode", choices=["models", "chat"], default="models")
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


def _chat_completion_accessible(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    choices = payload.get("choices")
    return isinstance(choices, list) and bool(choices) and isinstance(choices[0], dict)


def _credential_diagnostics(raw_value: str, env_name: str) -> dict[str, bool]:
    stripped = raw_value.strip()
    return {
        "credential_present": bool(stripped),
        "credential_had_outer_whitespace": raw_value != stripped,
        "credential_contains_env_assignment": stripped.startswith(f"{env_name}="),
    }


def _sanitize_provider_text(value: object, *, api_key: str, limit: int = 400) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text:
        return None
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
    text = _TOKEN_LIKE_RE.sub("[REDACTED]", text)
    return text[:limit]


def _http_error_details(exc: HTTPError, *, api_key: str) -> dict[str, str]:
    try:
        raw = exc.read()
    except OSError:
        return {}
    if not raw:
        return {}
    try:
        text = raw.decode("utf-8", errors="replace")
    except AttributeError:
        return {}

    payload: object
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        message = _sanitize_provider_text(text, api_key=api_key)
        return {"provider_error_message": message} if message else {}

    code: object = None
    message: object = None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            code = error.get("code") or error.get("type") or error.get("name")
            message = error.get("message") or error.get("detail")
        elif isinstance(error, str):
            message = error
        code = code or payload.get("code") or payload.get("type")
        message = message or payload.get("message") or payload.get("detail")

    details: dict[str, str] = {}
    safe_code = _sanitize_provider_text(code, api_key=api_key, limit=120)
    safe_message = _sanitize_provider_text(message, api_key=api_key)
    if safe_code:
        details["provider_error_code"] = safe_code
    if safe_message:
        details["provider_error_message"] = safe_message
    if not details:
        fallback = _sanitize_provider_text(text, api_key=api_key)
        if fallback:
            details["provider_error_message"] = fallback
    return details


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
    probe_mode: str = "models",
    http_status: int | None = None,
    model_accessible: bool | None = None,
    credential_diagnostics: dict[str, bool] | None = None,
    provider_error: dict[str, str] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "provider": provider,
        "model": model,
        "base_url_host": urlsplit(base_url).hostname,
        "probe_mode": probe_mode,
        "status": status,
        "http_status": http_status,
        "model_accessible": model_accessible,
        "credential_present": True,
    }
    if credential_diagnostics:
        result.update(credential_diagnostics)
    if provider_error:
        result.update(provider_error)
    return result


def _build_request(
    *,
    base_url: str,
    api_key: str,
    model: str,
    probe_mode: str,
) -> Request:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": _API_USER_AGENT,
    }
    if probe_mode == "models":
        return Request(f"{base_url.rstrip('/')}/models", headers=headers)
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "temperature": 0,
            "max_tokens": 64,
            "stream": False,
        }
    ).encode("utf-8")
    headers["Content-Type"] = "application/json"
    return Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers=headers,
        method="POST",
    )


def main() -> int:
    args = _parser().parse_args()
    raw_api_key = os.getenv(args.api_key_env, "")
    credential_diagnostics = _credential_diagnostics(raw_api_key, args.api_key_env)
    api_key = raw_api_key.strip()
    if not api_key:
        result = _result(
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            probe_mode=args.probe_mode,
            status="configuration",
            credential_diagnostics=credential_diagnostics,
        )
        _write_result(args.output, result)
        return 2

    request = _build_request(
        base_url=args.base_url,
        api_key=api_key,
        model=args.model,
        probe_mode=args.probe_mode,
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
            probe_mode=args.probe_mode,
            status=_status_name(exc.code),
            http_status=exc.code,
            credential_diagnostics=credential_diagnostics,
            provider_error=_http_error_details(exc, api_key=api_key),
        )
        _write_result(args.output, result)
        return 3
    except (URLError, TimeoutError, OSError):
        result = _result(
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            probe_mode=args.probe_mode,
            status="connect",
            credential_diagnostics=credential_diagnostics,
        )
        _write_result(args.output, result)
        return 4
    except (UnicodeDecodeError, json.JSONDecodeError):
        result = _result(
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            probe_mode=args.probe_mode,
            status="malformed_response",
            credential_diagnostics=credential_diagnostics,
        )
        _write_result(args.output, result)
        return 5

    if status_code >= 400:
        result = _result(
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            probe_mode=args.probe_mode,
            status=_status_name(status_code),
            http_status=status_code,
            credential_diagnostics=credential_diagnostics,
        )
        _write_result(args.output, result)
        return 3

    if args.probe_mode == "models":
        model_accessible = args.model in _model_ids(payload)
    else:
        model_accessible = _chat_completion_accessible(payload)
    result = _result(
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        probe_mode=args.probe_mode,
        status="ok" if model_accessible else "model_unavailable",
        http_status=status_code,
        model_accessible=model_accessible,
        credential_diagnostics=credential_diagnostics,
    )
    _write_result(args.output, result)
    return 0 if model_accessible else 6


if __name__ == "__main__":
    raise SystemExit(main())
