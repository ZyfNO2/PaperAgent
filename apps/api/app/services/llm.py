"""LLM client — multi-provider (MiniMax / Deepseek / VOAPI-GPT).

Provider selection:
  - env LLM_PROVIDER  ("minimax" | "deepseek" | "voapi", default "minimax")
  - per-call `provider=` overrides env

MiniMax: anthropic-compatible, SSE stream.
Deepseek: OpenAI-compatible, JSON mode, flash→pro fallback.
VOAPI: OpenAI-compatible proxy (gpt-5.4-medium etc.).

Env vars:
  MINIMAX_API_KEY / MINIMAX_BASE_URL / MINIMAX_MODEL
  DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_FLASH_MODEL / DEEPSEEK_PRO_MODEL
  VOAPI_API_KEY / VOAPI_BASE_URL / VOAPI_MODEL
  LLM_JSON_RETRY_COUNT (default 1)
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


def _collect_stream(r: Any) -> str:
    """Read an Anthropic-compatible SSE stream."""
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


def _get_env(key: str, default: str = "") -> str:
    """Read env at call-time so monkeypatch.setenv works in tests."""
    return os.environ.get(key, default).strip()


# ---------------------------------------------------------------------------
# MiniMax backend
# ---------------------------------------------------------------------------

def _chat_minimax(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout: float = 60.0,
    stream: bool = True,
) -> str:
    """Call MiniMax M3 (anthropic-compatible). Returns raw text."""
    api_key = _get_env("MINIMAX_API_KEY")
    base_url = _get_env("MINIMAX_BASE_URL", "https://api.minimaxi.com/anthropic").rstrip("/")
    model = _get_env("MINIMAX_MODEL", "MiniMax-M3")

    if not api_key:
        raise LLMUnavailable("MINIMAX_API_KEY 未设置")

    import httpx

    url = f"{base_url}/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model,
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
            try:
                with httpx.stream("POST", url, headers=headers, json=body, timeout=timeout) as r:
                    if r.status_code >= 400:
                        raise LLMUnavailable(f"HTTP {r.status_code}: {r.text[:200] if r.text else ''}")
                    return _collect_stream(r)
            except (AttributeError, RuntimeError):
                # Fallback when httpx.stream is mocked/unavailable (e.g. tests).
                stream = False
        if not stream:
            r = httpx.post(url, headers=headers, json=body, timeout=timeout)
            if r.status_code >= 400:
                raise LLMUnavailable(f"HTTP {r.status_code}: {r.text[:200]}")
            data = r.json()
            text_parts = []
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            return "".join(text_parts).strip()
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"网络错误: {exc}") from exc
    except LLMUnavailable:
        raise
    except Exception as exc:
        raise LLMUnavailable(f"LLM 调用失败: {exc}") from exc


# ---------------------------------------------------------------------------
# OpenAI-compatible backend (Deepseek, VOAPI, etc.)
# ---------------------------------------------------------------------------

def _chat_openai_compat_once(
    prompt: str,
    *,
    system: str | None = None,
    model: str,
    api_key: str,
    base_url: str,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout: float = 60.0,
) -> str:
    """Generic OpenAI-compatible chat call. Returns raw text."""
    if not api_key:
        raise LLMUnavailable("API key not set")

    import httpx

    url = f"{base_url}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    try:
        r = httpx.post(url, headers=headers, json=body, timeout=timeout)
        if r.status_code >= 400:
            raise LLMUnavailable(f"HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        choices = data.get("choices") or []
        if not choices:
            raise LLMUnavailable("Empty choices from OpenAI-compat API")
        msg = choices[0].get("message") or {}
        content = (msg.get("content") or "").strip()
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"Network error: {exc}") from exc
    except LLMUnavailable:
        raise
    except Exception as exc:
        raise LLMUnavailable(f"OpenAI-compat call failed: {exc}") from exc
    return content


# ---------------------------------------------------------------------------
# Deepseek provider
# ---------------------------------------------------------------------------

def _chat_deepseek(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout: float = 60.0,
) -> str:
    """Deepseek with flash→pro fallback on JSON parse failure."""
    api_key = _get_env("DEEPSEEK_API_KEY")
    base_url = _get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    flash_model = _get_env("DEEPSEEK_FLASH_MODEL", "deepseek-chat")
    pro_model = _get_env("DEEPSEEK_PRO_MODEL", "deepseek-reasoner")

    raw = _chat_openai_compat_once(
        prompt, system=system, model=flash_model, api_key=api_key,
        base_url=base_url, temperature=temperature, max_tokens=max_tokens, timeout=timeout,
    )
    cleaned = _strip_code_fence(raw)
    try:
        json.loads(cleaned)
        return raw
    except json.JSONDecodeError:
        pass

    if pro_model:
        raw = _chat_openai_compat_once(
            prompt, system=system, model=pro_model, api_key=api_key,
            base_url=base_url, temperature=temperature, max_tokens=max_tokens * 2, timeout=timeout,
        )
    return raw


# ---------------------------------------------------------------------------
# StepFun provider (Re1.1: separate adapter — do NOT assume OpenAI-compat)
# ---------------------------------------------------------------------------

def _chat_stepfun(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout: float = 60.0,
) -> str:
    """StepFun lightweight provider (low-cost execution / connectivity tests).

    Uses StepFun's OpenAI-compatible `/v1/chat/completions` surface when the
    env base points there. Request + response bodies are redacted by the caller.

    Env: STEPFUN_API_KEY / STEPFUN_BASE_URL / STEPFUN_MODEL
    """
    api_key = _get_env("STEPFUN_API_KEY")
    base_url = _get_env("STEPFUN_BASE_URL",
                        "https://api.stepfun.com").rstrip("/")
    # Default: step-3.7-flash (reasoning model — when max_tokens is big enough
    # it thinks in the `reasoning` field and puts clean JSON in `content`).
    # step-1v-32k is non-reasoning but much weaker on nuanced classification.
    model = _get_env("STEPFUN_MODEL", "step-3.7-flash")

    if not api_key:
        raise LLMUnavailable("STEPFUN_API_KEY 未设置")

    # StepFun advertises an OpenAI-compatible chat surface. Imported lazily so
    # the failure mode is explicit if the endpoint diverges.
    return _chat_openai_compat_once(
        prompt,
        system=system,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )

def _chat_voapi(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout: float = 120.0,
) -> str:
    """VOAPI OpenAI-compatible proxy (GPT-5.4-medium etc.)."""
    api_key = _get_env("VOAPI_API_KEY")
    base_url = _get_env("VOAPI_BASE_URL", "https://demo.voapi.top").rstrip("/")
    model = _get_env("VOAPI_MODEL", "gpt-5.4-medium")

    return _chat_openai_compat_once(
        prompt, system=system, model=model, api_key=api_key,
        base_url=base_url, temperature=temperature, max_tokens=max_tokens, timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chat_json(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout: float = 60.0,
    profile: str | None = None,
    provider: str | None = None,
    fallback_profiles: list[str] | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    """Call LLM, expect strict JSON dict.

    provider: "minimax" (anthropic), "deepseek" / "voapi" (openai-compat).
    """
    prov = (provider or _get_env("LLM_PROVIDER", "minimax")).lower()

    if _get_env("MINIMAX_DISABLED", "true").lower() == "true" and prov == "minimax":
        raise LLMUnavailable(
            "MINIMAX_DISABLED=true and provider resolved to minimax; "
            "set LLM_PROFILE=fast_json (DeepSeek) or another non-disabled provider"
        )

    if prov == "voapi":
        raw = _chat_voapi(prompt, system=system, temperature=temperature,
                          max_tokens=max_tokens, timeout=timeout)
    elif prov == "deepseek":
        raw = _chat_deepseek(prompt, system=system, temperature=temperature,
                             max_tokens=max_tokens, timeout=timeout)
    else:
        raw = _chat_minimax(prompt, system=system, temperature=temperature,
                            max_tokens=max_tokens, timeout=timeout, stream=stream)

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
    provider: str | None = None,
) -> list[Any]:
    """Call LLM, expect strict JSON list."""
    prov = (provider or _get_env("LLM_PROVIDER", "minimax")).lower()

    if _get_env("MINIMAX_DISABLED", "true").lower() == "true" and prov == "minimax":
        raise LLMUnavailable(
            "MINIMAX_DISABLED=true and provider resolved to minimax; "
            "set LLM_PROFILE=fast_json (DeepSeek) or another non-disabled provider"
        )

    if prov == "voapi":
        raw = _chat_voapi(prompt, system=system, temperature=temperature,
                          max_tokens=max_tokens, timeout=timeout)
    elif prov == "deepseek":
        raw = _chat_deepseek(prompt, system=system, temperature=temperature,
                             max_tokens=max_tokens, timeout=timeout)
    else:
        raw = _chat_minimax(prompt, system=system, temperature=temperature,
                            max_tokens=max_tokens, timeout=timeout, stream=False)

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
