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


def chat_json(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """调 MiniMax M3 (anthropic-compatible), 期望返回严格 JSON dict.

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

    if not isinstance(result, dict):
        raise LLMUnavailable("LLM 返回的不是 dict")
    return result
