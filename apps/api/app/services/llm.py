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


def _extract_json_from_text(text: str) -> Any | None:
    """Pull the first/last balanced JSON object-or-array out of `text`.

    Reasoner models (e.g. StepFun step-3.7-flash) emit reasoning prose and
    stash the JSON payload inside the same field. Look back-to-front so the
    final answer wins over any example/transcript JSON earlier in the stream.
    """
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Backward scan → first balanced {…} or […] we can parse
    for match in list(re.finditer(r"[{[]", text))[::-1]:
        start = match.start()
        opener = text[start]
        closer = "}" if opener == "{" else "]"
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        pass
                    break
    return None


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
    }
    # Do NOT set response_format=json_object: StepFun step-3.7-flash treats the
    # flag as a container instruction and emits ``content`` = ``{}`` with the
    # real JSON buried in ``reasoning``.  By leaving the field out, the model
    # writes clean JSON directly into ``content`` (or ``reasoning`` when in
    # reasoner mode), which our reasoning-scan recovery picks up.

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
        reasoning = (msg.get("reasoning") or "").strip() or (msg.get(
            "reasoning_content") or "").strip()

        # StepFun step-3.7-flash with ``response_format=json_object`` sends
        # ``content`` as ``{}``/``{"":""}`` and puts the real JSON under
        # ``reasoning``.  When ``content`` does not parse as JSON, prefer a
        # ``reasoning``-embedded blob.
        import json
        def _json_value(text: str):
            text = (text or "").strip()
            try:
                return json.loads(text) if text else None
            except json.JSONDecodeError:
                return None

        if _json_value(content) is not None:
            return content
        if reasoning:
            extracted = _extract_json_from_text(reasoning)
            if extracted is not None:
                return json.dumps(extracted, ensure_ascii=False)
            # reasoner-only output that contains no balanced JSON at all; the
            # most common case is step-3.7-flash emitting a thinking loop that
            # never materialises the payload.  Fall back to a non-reasoning
            # instruct model that reliably writes JSON to ``content``.
            fallback = _get_env("STEPFUN_JSON_FALLBACK_MODEL", "").strip()
            if fallback:
                return _chat_once_json_via_fallback(
                    prompt, system=system, fallback_model=fallback,
                    temperature=temperature, max_tokens=max_tokens, timeout=timeout,
                )
            return reasoning
        return content
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"Network error: {exc}") from exc
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"Network error: {exc}") from exc
    except LLMUnavailable:
        raise
    except Exception as exc:
        raise LLMUnavailable(f"OpenAI-compat call failed: {exc}") from exc


def _chat_once_json_via_fallback(prompt, *, system, fallback_model, temperature,
                                 max_tokens, timeout):
    """Re-issue the same prompt to a small instruct model for shape-safe JSON."""
    api_key = _get_env("STEPFUN_API_KEY")
    base_url = _get_env("STEPFUN_BASE_URL", "https://api.stepfun.com").rstrip("/")
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user",
                 "content": prompt + "\n\n[Reply with ONLY the strict JSON object.]"})
    try:
        r = httpx.post(
            f"{base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": fallback_model, "messages": msgs,
                  "temperature": temperature, "max_tokens": max_tokens},
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        return (content or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("stepfun fallback model %s failed: %s", fallback_model, exc)
        return prompt  # last resort; caller will later fail validation


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
    """StepFun primary provider.

    Uses StepFun's OpenAI-compatible `/v1/chat/completions` surface. The
    default model is step-3.7-flash (reasoner).  When step-3.7-flash returns an
    empty or unparseable content AND a JSON fallback model is configured, the
    call is retried against that fallback so JSON-producing nodes stay stable.
    """
    api_key = _get_env("STEPFUN_API_KEY")
    base_url = _get_env("STEPFUN_BASE_URL",
                        "https://api.stepfun.com").rstrip("/")
    model = _get_env("STEPFUN_MODEL", "step-3.7-flash")
    if not api_key:
        raise LLMUnavailable("STEPFUN_API_KEY 未设置")

    raw = _chat_openai_compat_once(
        prompt, system=system, model=model, api_key=api_key,
        base_url=base_url, temperature=temperature, max_tokens=max_tokens, timeout=timeout,
    )
    # The reasoner should emit at least one JSON object; if ``raw`` is empty,
    # unparseable, or only contains a bare array of strings, fall back to a
    # structured-JSON-capable instruct model so downstream callers get
    # usable shape.
    if raw and _contains_json_object(raw):
        return raw
    fallback = _get_env("STEPFUN_JSON_FALLBACK_MODEL", "step-1v-32k").strip()
    if fallback and fallback.lower() != model.lower():
        try:
            return _chat_openai_compat_once(
                prompt, system=system, model=fallback, api_key=api_key,
                base_url=base_url, temperature=temperature,
                max_tokens=max_tokens, timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("stepfun json fallback %s failed: %s", fallback, exc)
            return raw
    return raw


def _contains_json_object(raw: str) -> bool:
    """True if ``raw`` parses to JSON whose tree contains at least one object.

    Used to conclude whether StepFun's step-3.7-flash produced a structured
    answer (which we keep) or a bare keyword list / transcript (which we
    treat as a model failure and fall back to a JSON-friendlier model).
    """
    import json
    text = (raw or "").strip()
    if not text:
        return False
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try the last balanced {…} / […] slice.
        import re
        matched = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
        if not matched:
            return False
        try:
            parsed = json.loads(matched.group(0))
        except json.JSONDecodeError:
            return False
    stack = [parsed]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            return True
        if isinstance(cur, list):
            stack.extend(cur)
    return False


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
