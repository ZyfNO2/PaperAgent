from __future__ import annotations

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
