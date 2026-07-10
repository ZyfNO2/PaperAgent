"""Protocol adapter: OpenAI-compatible chat completion.

Converts a standard request dict {messages, model, temperature, ...}
into an OpenAI-compatible HTTP request and normalises the response.

Re6.1 Provider Core — adapters only do protocol translation, not business logic.
Response normalization is handled by ResponseEnvelope in R6.2.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx  # type: ignore[import-untyped]

from ..errors import ProviderError, ProviderErrorType, classify_http_error
from ...security.url_safety import check_url_safety_with_resolve

logger = logging.getLogger(__name__)

# Default timeouts
_CONNECT_TIMEOUT_S = 10
_READ_TIMEOUT_S = 60
_TOTAL_TIMEOUT_S = 90


async def openai_chat(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    response_format: dict[str, Any] | None = None,
    stream: bool = False,
    timeout_s: float | None = None,
) -> dict[str, Any] | ProviderError:
    """Send a chat completion request to an OpenAI-compatible endpoint.

    Args:
        base_url: Provider base URL (e.g. "https://api.openai.com").
        api_key: Raw API key (will NOT be logged).
        model: Model ID string.
        messages: List of {"role": str, "content": str} dicts.
        temperature: Sampling temperature.
        max_tokens: Max tokens to generate.
        response_format: Optional {"type": "json_object"} or
            {"type": "json_schema", "json_schema": {...}}.
        stream: If True, request streaming response.
        timeout_s: Override default read timeout.

    Returns:
        On success: dict with keys: model, choices ([{message: {role, content}, finish_reason}]),
                    usage ({prompt_tokens, completion_tokens, total_tokens}),
                    raw_shape ("openai_chat").
        On failure: ProviderError.
    """
    # Build request URL
    endpoint = f"{base_url.rstrip('/')}/v1/chat/completions"

    # Build payload
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if response_format:
        payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    read_timeout = timeout_s or _READ_TIMEOUT_S
    t0 = time.time()

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=_CONNECT_TIMEOUT_S,
                read=read_timeout,
                pool=_TOTAL_TIMEOUT_S,
            ),
            follow_redirects=False,
        ) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)

        elapsed_ms = round((time.time() - t0) * 1000, 1)

        if resp.status_code == 200:
            data = resp.json()
            if not isinstance(data, dict):
                return ProviderError(
                    error_type=ProviderErrorType.malformed_output,
                    detail="response is not a JSON object",
                    status_code=200,
                    raw_body_snippet=str(data)[:200],
                )

            # Normalize to a standard shape
            choices = data.get("choices") or []
            usage = data.get("usage") or {}
            normalized: dict[str, Any] = {
                "model": data.get("model", model),
                "choices": [
                    {
                        "message": c.get("message", {}),
                        "finish_reason": c.get("finish_reason", "stop"),
                    }
                    for c in choices
                ],
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                "raw_shape": "openai_chat",
                "elapsed_ms": elapsed_ms,
            }
            return normalized

        else:
            body = resp.text[:200]
            return classify_http_error(resp.status_code, body)

    except httpx.TimeoutException:
        return ProviderError(
            error_type=ProviderErrorType.transient_network,
            detail=f"request timed out after {read_timeout}s",
            retryable=True,
        )
    except httpx.ConnectError as exc:
        return ProviderError(
            error_type=ProviderErrorType.transient_network,
            detail=f"connection failed: {exc}",
            retryable=True,
        )
    except Exception as exc:
        logger.warning("openai_chat unexpected error: %s", exc)
        return ProviderError(
            error_type=ProviderErrorType.transient_network,
            detail=f"unexpected error: {type(exc).__name__}",
            retryable=False,
        )


async def openai_list_models(
    base_url: str,
    api_key: str,
) -> list[str] | ProviderError:
    """Fetch the model list from an OpenAI-compatible /v1/models endpoint."""
    endpoint = f"{base_url.rstrip('/')}/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=_CONNECT_TIMEOUT_S, read=15),
            follow_redirects=False,
        ) as client:
            resp = await client.get(endpoint, headers=headers)

        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                models = []
                for item in data["data"]:
                    if isinstance(item, dict) and "id" in item:
                        models.append(item["id"])
                return models
            elif isinstance(data, list):
                return [item["id"] if isinstance(item, dict) else str(item) for item in data]
            else:
                return ProviderError(
                    error_type=ProviderErrorType.malformed_output,
                    detail="unexpected /v1/models response shape",
                    status_code=200,
                )
        elif resp.status_code in (404, 405):
            return ProviderError(
                error_type=ProviderErrorType.discovery_unsupported,
                detail="/v1/models not available (404/405)",
                status_code=resp.status_code,
            )
        else:
            return classify_http_error(resp.status_code, resp.text[:200])

    except httpx.TimeoutException:
        return ProviderError(
            error_type=ProviderErrorType.transient_network,
            detail="models list request timed out",
            retryable=True,
        )
    except Exception as exc:
        return ProviderError(
            error_type=ProviderErrorType.transient_network,
            detail=f"models list error: {type(exc).__name__}",
            retryable=False,
        )
