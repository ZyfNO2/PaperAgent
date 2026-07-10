"""Protocol adapter: Anthropic-like message completion.

Converts a standard request dict into an Anthropic Messages API request
and normalises the response to the same shape as OpenAI-compatible responses.

Re6.1 Provider Core — adapters only do protocol translation.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx  # type: ignore[import-untyped]

from ..errors import ProviderError, ProviderErrorType, classify_http_error

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT_S = 10
_READ_TIMEOUT_S = 60


def _convert_messages(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    """Convert OpenAI-style messages to Anthropic-style.

    Returns (anthropic_messages, system_prompt).
    """
    system_prompt: str | None = None
    anthropic_msgs: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            system_prompt = content if isinstance(content, str) else str(content)
        elif role == "assistant":
            anthropic_msgs.append({"role": "assistant", "content": [{"type": "text", "text": str(content)}]})
        else:
            anthropic_msgs.append({"role": "user", "content": [{"type": "text", "text": str(content)}]})

    return anthropic_msgs, system_prompt


async def anthropic_chat(
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
    """Send a chat completion to an Anthropic-like endpoint.

    Converts OpenAI-style messages to Anthropic Messages API format,
    then normalises the response back to the standard shape.
    """
    endpoint = f"{base_url.rstrip('/')}/v1/messages"

    anthropic_msgs, system_prompt = _convert_messages(messages)

    payload: dict[str, Any] = {
        "model": model,
        "messages": anthropic_msgs,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if system_prompt:
        payload["system"] = system_prompt
    if stream:
        payload["stream"] = stream

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    read_timeout = timeout_s or _READ_TIMEOUT_S
    t0 = time.time()

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=_CONNECT_TIMEOUT_S, read=read_timeout),
            follow_redirects=False,
        ) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)

        elapsed_ms = round((time.time() - t0) * 1000, 1)

        if resp.status_code == 200:
            data = resp.json()
            if not isinstance(data, dict):
                return ProviderError(
                    error_type=ProviderErrorType.malformed_output,
                    detail="Anthropic response is not a JSON object",
                    status_code=200,
                )

            # Extract content from Anthropic response blocks
            content_blocks = data.get("content") or []
            text_parts = []
            reasoning_parts = []
            for block in content_blocks:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") in ("thinking", "reasoning"):
                        reasoning_parts.append(block.get("thinking", block.get("text", "")))

            full_text = "\n".join(text_parts)
            reasoning_text = "\n".join(reasoning_parts) if reasoning_parts else None

            usage = data.get("usage") or {}
            normalized: dict[str, Any] = {
                "model": data.get("model", model),
                "choices": [
                    {
                        "message": {"role": "assistant", "content": full_text},
                        "finish_reason": data.get("stop_reason", "end_turn"),
                    }
                ],
                "usage": {
                    "prompt_tokens": usage.get("input_tokens", 0),
                    "completion_tokens": usage.get("output_tokens", 0),
                    "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                },
                "raw_shape": "anthropic_message",
                "elapsed_ms": elapsed_ms,
            }
            if reasoning_text:
                normalized["reasoning"] = reasoning_text
            return normalized

        else:
            body = resp.text[:200]
            # Anthropic sometimes returns JSON errors
            err_detail = body
            try:
                err_data = json.loads(body)
                if isinstance(err_data, dict):
                    err_detail = err_data.get("error", {}).get("message", body)
            except (json.JSONDecodeError, AttributeError):
                pass
            return classify_http_error(resp.status_code, err_detail)

    except httpx.TimeoutException:
        return ProviderError(
            error_type=ProviderErrorType.transient_network,
            detail="Anthropic request timed out",
            retryable=True,
        )
    except httpx.ConnectError as exc:
        return ProviderError(
            error_type=ProviderErrorType.transient_network,
            detail=f"connection failed: {exc}",
            retryable=True,
        )
    except Exception as exc:
        logger.warning("anthropic_chat unexpected: %s", exc)
        return ProviderError(
            error_type=ProviderErrorType.transient_network,
            detail=f"unexpected: {type(exc).__name__}",
            retryable=False,
        )
