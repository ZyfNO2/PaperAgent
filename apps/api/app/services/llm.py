"""MiniMax M3 LLM 客户端 (LiteLLM 风格) + heuristic fallback.

读 .env: MINIMAX_API_KEY / MINIMAX_BASE_URL / MINIMAX_MODEL。
缺 key → raise LLMUnavailable, 让上层 fallback 到启发式。
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "").strip()
MINIMAX_BASE_URL = os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com/anthropic").rstrip("/")
MINIMAX_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
MINIMAX_MAX_TOKENS = int(os.environ.get("MINIMAX_MAX_TOKENS", "2048"))


class LLMUnavailable(RuntimeError):
    """LLM 不可用: 缺 key / 网络断开 / 解析失败."""


def _strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", s, re.DOTALL)
        if m:
            return m.group(1).strip()
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def _collect_stream(r: httpx.Response) -> str:
    """Read an Anthropic-compatible SSE stream. Each event is a JSON line:
    `event: message_start` / `content_block_start` / `content_block_delta` /
    `content_block_stop` / `message_delta` / `message_stop`. We collect all
    `content_block_delta` text deltas in order, ignoring non-text blocks.
    """
    chunks: list[str] = []
    for line in r.iter_lines():
        if not line:
            continue
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                evt = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if evt.get("type") == "content_block_delta":
                delta = evt.get("delta") or {}
                if delta.get("type") == "text_delta":
                    chunks.append(delta.get("text", ""))
    return "".join(chunks)


def chat_json(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout: float = 60.0,
    profile: str | None = None,  # S66.6: kept for caller compat, no-op in HEAD
    provider: str | None = None,  # S66.6: kept for caller compat, no-op in HEAD
    fallback_profiles: list[str] | None = None,  # S66.6: kept for caller compat
    stream: bool = True,
) -> dict[str, Any]:
    """调 MiniMax M3 (anthropic-compatible), 期望返回严格 JSON dict.

    Set `stream=True` (default) to consume the response as Server-Sent Events.
    We accumulate text deltas in order; this avoids the message-level max_tokens
    truncation that causes half-JSON returns. Send the same `max_tokens` as an
    upper bound, but the response is whatever the model decides to emit.

    Raises:
        LLMUnavailable: 缺 key / 网络错误 / 解析失败.
    """

    if not MINIMAX_API_KEY:
        raise LLMUnavailable("MINIMAX_API_KEY 未设置")

    import httpx

    url = f"{MINIMAX_BASE_URL}/v1/messages"
    headers = {
        "x-api-key": MINIMAX_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body: dict[str, Any] = {
        "model": MINIMAX_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    if stream:
        body["stream"] = True

    try:
        if stream:
            with httpx.stream("POST", url, headers=headers, json=body, timeout=timeout) as r:
                if r.status_code >= 400:
                    raise LLMUnavailable(f"HTTP {r.status_code}: {r.text[:200] if r.text else ''}")
                raw = _collect_stream(r)
        else:
            r = httpx.post(url, headers=headers, json=body, timeout=timeout)
            if r.status_code >= 400:
                raise LLMUnavailable(f"HTTP {r.status_code}: {r.text[:200]}")
            data = r.json()
            text_parts = []
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            raw = "".join(text_parts).strip()
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"网络错误: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise LLMUnavailable(f"LLM 调用失败: {exc}") from exc

    if not raw:
        raise LLMUnavailable("LLM 返回空内容")

    cleaned = _strip_code_fence(raw)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(f"JSON 解析失败: {exc}; raw={raw[:200]!r}") from exc

    if not isinstance(result, dict):
        raise LLMUnavailable("LLM 返回的不是 dict")
    return result


def chat_json_array(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout: float = 30.0,
) -> list[Any]:
    """调 MiniMax M3, 期望返回严格 JSON list (如 rerank 分数数组).

    Raises:
        LLMUnavailable: 缺 key / 网络错误 / 解析失败.
    """

    if not MINIMAX_API_KEY:
        raise LLMUnavailable("MINIMAX_API_KEY 未设置")

    import httpx

    url = f"{MINIMAX_BASE_URL}/v1/messages"
    headers = {
        "x-api-key": MINIMAX_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": MINIMAX_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system

    try:
        r = httpx.post(url, headers=headers, json=body, timeout=timeout)
        if r.status_code >= 400:
            raise LLMUnavailable(f"HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"网络错误: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise LLMUnavailable(f"LLM 调用失败: {exc}") from exc

    text_parts = []
    for block in data.get("content", []):
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    raw = "".join(text_parts).strip()
    if not raw:
        raise LLMUnavailable("LLM 返回空内容")

    cleaned = _strip_code_fence(raw)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(f"JSON 解析失败: {exc}; raw={raw[:200]!r}") from exc

    if not isinstance(result, list):
        raise LLMUnavailable(f"LLM 返回的不是 list (got {type(result).__name__})")
    return result
