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
import threading
import time as _time
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lightweight client-side rate limiter (thread-safe)
# ---------------------------------------------------------------------------
# StepFun caps accounts at 10 RPM.  Without client-side pacing the parallel
# verifier immediately trips 429.  The limiter batches inter-call gaps so we
# stay safely under the cap.  With RPM=10 the interval is 6s: fast enough to
# keep total case time ~8-12 min while avoiding the expensive 429 retry cycle.
_limiter_lock = threading.Lock()
_limiter_state: dict[str, dict[str, float]] = {}


def _rpm_limit_for(bucket: str | None) -> int:
    bucket_key = (bucket or "").strip().upper()
    if bucket_key:
        scoped = _get_env(f"{bucket_key}_RPM_LIMIT", "")
        if scoped:
            try:
                return int(scoped)
            except ValueError:
                return 0
    try:
        return int(_get_env("LLM_RPM_LIMIT", "0"))
    except ValueError:
        return 0


def _rate_limit_pause(bucket: str | None = None) -> None:
    """Block until the minimum inter-call interval has elapsed."""
    rpm = _rpm_limit_for(bucket)
    if rpm <= 0:
        return
    bucket_name = (bucket or "default").lower()
    with _limiter_lock:
        state = _limiter_state.setdefault(
            bucket_name, {"min_interval": 60.0 / rpm, "last_call": 0.0},
        )
        state["min_interval"] = 60.0 / rpm
        now = _time.monotonic()
        wait = state["min_interval"] - (now - state["last_call"])
        if wait > 0.0:
            _time.sleep(wait)
        state["last_call"] = _time.monotonic()


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


def _normalize_openai_base_url(base_url: str) -> str:
    url = (base_url or "").strip().rstrip("/")
    if url.endswith("/v1"):
        return url[:-3]
    return url


def _coerce_text_payload(value: Any) -> str:
    """Flatten string/list/dict provider payloads into plain text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_coerce_text_payload(item) for item in value]
        return "\n".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        for key in ("text", "content", "value", "output_text", "reasoning", "reasoning_content"):
            text = _coerce_text_payload(value.get(key))
            if text:
                return text
        return ""
    return str(value).strip()


# ---------------------------------------------------------------------------
# MiniMax backend
# ---------------------------------------------------------------------------

def _collect_stream(response: Any) -> str:
    """Collect text from an SSE-streamed anthropic-compatible response.

    MiniMax (anthropic-compatible) streams ``content_block_delta`` events
    whose ``delta.text`` fragments must be concatenated to produce the full
    answer.  Falls back to non-SSE JSON parsing if the body is a single
    JSON object (useful for mocked responses in tests).
    """
    text_parts: list[str] = []
    try:
        for line in response.iter_lines():
            if not line:
                continue
            s = line.strip()
            if s.startswith("data: "):
                s = s[6:]
            try:
                evt = json.loads(s)
            except (json.JSONDecodeError, TypeError):
                continue
            if evt.get("type") == "content_block_delta":
                delta = evt.get("delta") or {}
                if delta.get("type") == "text_delta":
                    text_parts.append(delta.get("text", ""))
            elif evt.get("type") == "message_stop":
                break
    except (AttributeError, RuntimeError):
        # iter_lines not available — try treating as a plain JSON response
        try:
            data = response.json()
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
        except Exception:
            pass
    return "".join(text_parts).strip()


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
    rate_limit_bucket: str | None = None,
) -> str:
    """Generic OpenAI-compatible chat call. Returns raw text.

    Retries with exponential backoff on HTTP 429 (rate limit) up to 3 attempts
    so the pipeline survives short bursts past the RPM cap.
    """
    if not api_key:
        raise LLMUnavailable("API key not set")

    import time as _time

    import httpx

    url = f"{_normalize_openai_base_url(base_url)}/v1/chat/completions"
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

    max_retries = 3
    for attempt in range(max_retries):
        _rate_limit_pause(rate_limit_bucket)
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=timeout)
            if r.status_code == 429:
                wait = 2 ** attempt
                logger.warning("rate limited (429) on %s (attempt %d/%d); waiting %ds",
                               model, attempt + 1, max_retries, int(wait))
                _time.sleep(wait)
                continue
            if r.status_code >= 400:
                raise LLMUnavailable(f"HTTP {r.status_code}: {r.text[:200]}")
            data = r.json()
            choices = data.get("choices") or []
            if not choices:
                raise LLMUnavailable("Empty choices from OpenAI-compat API")
            msg = choices[0].get("message") or {}
            content = _coerce_text_payload(msg.get("content"))
            reasoning = _coerce_text_payload(msg.get("reasoning")) or _coerce_text_payload(
                msg.get("reasoning_content"),
            )

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
                    # Re5.X: Only accept reasoning JSON if content is empty.
                    # If content has non-JSON text, the reasoning JSON might
                    # be an intermediate thinking artifact, not the final answer.
                    if not content or not content.strip():
                        return json.dumps(extracted, ensure_ascii=False)
                    # Content exists but isn't JSON — reasoning might still be valid
                    # but we flag it for the caller to decide
                    logger.debug("_chat_openai_compat_once: content exists but non-JSON; "
                               "reasoning JSON may be intermediate artifact")
                    return json.dumps(extracted, ensure_ascii=False)
                fallback = _get_env("STEPFUN_JSON_FALLBACK_MODEL", "").strip()
                if fallback:
                    return _chat_once_json_via_fallback(
                        prompt, system=system, fallback_model=fallback,
                        temperature=temperature, max_tokens=max_tokens, timeout=timeout,
                    )
                return reasoning
            return content
        except LLMUnavailable:
            raise
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"Network error: {exc}") from exc
        except Exception as exc:
            raise LLMUnavailable(f"OpenAI-compat call failed: {exc}") from exc

    raise LLMUnavailable(f"rate limit (429) persisted after {max_retries} retries")


def _chat_once_json_via_fallback(prompt, *, system, fallback_model, temperature,
                                 max_tokens, timeout):
    """Re-issue the same prompt to a small instruct model for shape-safe JSON.

    Retries with backoff on HTTP 429 (rate limit) up to 3 attempts.
    """
    import time as _time

    import httpx

    api_key = _get_env("STEPFUN_API_KEY")
    base_url = _normalize_openai_base_url(
        _get_env("STEPFUN_BASE_URL", "https://api.stepfun.com/step_plan/v1"),
    )
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user",
                 "content": prompt + "\n\n[Reply with ONLY the strict JSON object.]"})
    max_retries = 3
    for attempt in range(max_retries):
        _rate_limit_pause("STEPFUN")
        try:
            r = httpx.post(
                f"{base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"model": fallback_model, "messages": msgs,
                      "temperature": temperature, "max_tokens": max_tokens},
                timeout=timeout,
            )
            if r.status_code == 429:
                wait = 60.0 / max(_rpm_limit_for("STEPFUN") or 10, 1)
                logger.warning("fallback model %s rate limited (429) attempt %d/%d; waiting %ds",
                               fallback_model, attempt + 1, max_retries, int(wait))
                _time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            return (content or "").strip()
        except Exception as exc:  # noqa: BLE001
            if attempt == max_retries - 1:
                logger.warning("stepfun fallback model %s failed: %s", fallback_model, exc)
                return prompt  # last resort; caller will later fail validation
            _time.sleep(2 ** attempt)
    return prompt  # last resort


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
    """Deepseek call — tries primary provider, falls back only on failure.

    Re5.X: Cross-provider fallback only when the primary provider raises
    an exception (network error, 429, auth failure) or returns empty.
    If the provider returns content that isn't valid JSON, we DON'T retry
    another provider — that's the job of call_json's 3-phase repair pipeline.
    This avoids multiplying LLM latency by the number of registered providers.
    """
    from apps.api.app.services.llm_provider_registry import get_provider_registry

    registry = get_provider_registry()
    providers = registry.get_ordered_providers()

    last_raw: str = ""
    last_error: str = ""

    for idx, provider_cfg in enumerate(providers):
        try:
            raw = _chat_openai_compat_once(
                prompt, system=system, model=provider_cfg.model,
                api_key=provider_cfg.api_key,
                base_url=_normalize_openai_base_url(provider_cfg.base_url),
                temperature=temperature, max_tokens=max_tokens,
                timeout=timeout,
                rate_limit_bucket=provider_cfg.name.upper(),
            )
            # Provider returned something — return it immediately.
            # Whether it's valid JSON is call_json's problem (3-phase repair).
            # Only fall through to next provider if this one returned empty.
            if raw and raw.strip():
                if idx > 0:
                    logger.info("_chat_deepseek: primary failed, used fallback %s", provider_cfg.name)
                return raw
            last_error = f"{provider_cfg.name}: empty response"
        except Exception as exc:
            last_error = f"{provider_cfg.name}: {type(exc).__name__}: {exc}"
            logger.debug("_chat_deepseek: %s failed: %s, trying next", provider_cfg.name, exc)
            continue

    if last_raw:
        return last_raw
    raise LLMUnavailable(f"all providers failed; last_error={last_error}")


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
    """StepFun primary provider (step-3.7-flash, reasoner model).

    The model may emit a ``reasoning`` thinking transcript and put the real
    JSON payload in ``content`` (or ``reasoner`` mode).  Recovery chain:

      1. Call normally; if ``content`` carries a JSON object → return.
      2. Scan ``reasoning`` for a balanced JSON blob → return.
      3. Reinforce the system prompt with an explicit "MUST output JSON"
         instruction and retry once.
      4. Last resort: return the raw content; caller decides.

    The old instruct-model fallback (step-1v-32k) has been removed per user
    directive — re-add only if cost reduction becomes necessary.
    """
    api_key = _get_env("STEPFUN_API_KEY")
    base_url = _normalize_openai_base_url(
        _get_env("STEPFUN_BASE_URL", "https://api.stepfun.com/step_plan/v1"),
    )
    model = _get_env("STEPFUN_MODEL", "step-3.7-flash")
    if not api_key:
        raise LLMUnavailable("STEPFUN_API_KEY 未设置")

    # — attempt 1: normal call —
    raw = _chat_openai_compat_once(
        prompt, system=system, model=model, api_key=api_key,
        base_url=base_url, temperature=temperature,
        max_tokens=max_tokens, timeout=timeout, rate_limit_bucket="STEPFUN",
    )
    if raw:
        return raw

    # — attempt 2: reinforce prompt —
    if system:
        reinforced = (
            system.strip()
            + "\n\n[OUTPUT CONTRACT] After your step-by-step analysis, "
            "your ENTIRE final message must be exactly ONE valid JSON "
            "object — no prose, no fences, no text outside the JSON."
        )
    else:
        reinforced = (
            "[OUTPUT CONTRACT] Your ENTIRE final message must be exactly "
            "ONE valid JSON object — no prose, no fences."
        )
    try:
        raw2 = _chat_openai_compat_once(
            prompt, system=reinforced, model=model, api_key=api_key,
            base_url=base_url, temperature=temperature,
            max_tokens=max_tokens, timeout=timeout, rate_limit_bucket="STEPFUN",
        )
        if raw2:
            return raw2
    except Exception as exc:
        logger.debug("stepfun reinforce attempt failed: %s", exc)

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


def _chat_opencode(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout: float = 60.0,
) -> str:
    """Open Code Zen (opencode.ai/zen/v1) provider.

    Uses the OpenAI-compatible surface at ``OPENCODE_BASE_URL``.  The default
    model is ``big-pickle``.  This provider does NOT use the stepfun-specific
    fallback path because it writes JSON directly to ``content``.
    """
    api_key = _get_env("OPENCODE_API_KEY")
    # base_url may or may not include a trailing /v1 — strip it so
    # _chat_openai_compat_once can append /v1/chat/completions unambiguously.
    raw_base = _get_env("OPENCODE_BASE_URL", "https://opencode.ai/zen").rstrip("/")
    base_url = _normalize_openai_base_url(raw_base)
    model = _get_env("OPENCODE_MODEL", "big-pickle")
    if not api_key:
        raise LLMUnavailable("OPENCODE_API_KEY not set")
    return _chat_openai_compat_once(
        prompt, system=system, model=model, api_key=api_key,
        base_url=base_url, temperature=temperature, max_tokens=max_tokens,
        timeout=timeout, rate_limit_bucket="OPENCODE",
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
    base_url = _normalize_openai_base_url(_get_env("VOAPI_BASE_URL", "https://demo.voapi.top"))
    model = _get_env("VOAPI_MODEL", "gpt-5.4-medium")

    return _chat_openai_compat_once(
        prompt, system=system, model=model, api_key=api_key,
        base_url=base_url, temperature=temperature, max_tokens=max_tokens,
        timeout=timeout, rate_limit_bucket="VOAPI",
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
