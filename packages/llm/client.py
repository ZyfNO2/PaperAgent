"""Shared LLM client (LiteLLM + MiniMax M3) for TopicPilot-CN.

MVP 范围：
- 单 LLM 客户端接口 ``chat(messages, response_format, **kw)``
- 默认从 ``.env`` 读 ``MINIMAX_API_KEY / MINIMAX_BASE_URL / MINIMAX_MODEL``
- 支持 ``response_format=json`` 走 JSON 模式，提示 LLM 输出严格 JSON
- 不接 Langfuse / OpenTelemetry（Phase 04 之后再加）

调用方式：

    from packages.llm import chat
    text = chat([{"role":"user","content":"..."}])
    data = chat([...], response_format="json")
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import litellm
from dotenv import load_dotenv

load_dotenv()


# ------------------- 配置 ------------------- #

DEFAULT_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M3")
DEFAULT_API_BASE = os.environ.get(
    "MINIMAX_BASE_URL", "https://api.minimaxi.com/anthropic"
)
DEFAULT_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
DEFAULT_MAX_TOKENS = int(os.environ.get("MINIMAX_MAX_TOKENS", "4096"))


# ------------------- 客户端 ------------------- #


class LLMUnavailable(RuntimeError):
    """LLM 调用本身不可用（缺 key、网络断开、模型名错）。"""


def _strip_code_fence(s: str) -> str:
    """剥掉 ```json ... ``` 包裹。"""

    s = s.strip()
    if s.startswith("```"):
        m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", s, re.DOTALL)
        if m:
            return m.group(1).strip()
        # 退化：去掉首尾三反引号行
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def chat(
    messages: list[dict[str, str]],
    *,
    response_format: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> str:
    """调 LLM，返回文本。

    Parameters
    ----------
    messages : list of {"role":..., "content":...}
    response_format : None | "json"
        ``"json"`` 时在 prompt 末尾追加 JSON 指令并尝试解析；
        失败则抛出 ``ValueError``。
    """

    if not DEFAULT_API_KEY:
        raise LLMUnavailable(
            "MINIMAX_API_KEY 未设置。请在 .env 里填上 MiniMax M3 的 API key。"
        )

    msgs = list(messages)
    if response_format == "json":
        msgs = msgs + [
            {
                "role": "system",
                "content": "严格输出 JSON，不要解释、不要 markdown 包裹、不要多余文字。",
            }
        ]

    try:
        resp = litellm.completion(
            model=f"minimax/{model or DEFAULT_MODEL}",
            api_key=DEFAULT_API_KEY,
            api_base=f"{model and os.environ.get('MINIMAX_BASE_URL', DEFAULT_API_BASE) or DEFAULT_API_BASE}/v1/messages",
            custom_llm_provider="anthropic",
            messages=msgs,
            max_tokens=max_tokens or DEFAULT_MAX_TOKENS,
            temperature=temperature,
        )
    except Exception as exc:
        raise LLMUnavailable(f"LLM 调用失败: {exc}") from exc

    text = resp.choices[0].message.content or ""
    return text


def chat_json(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> Any:
    """调 LLM 并返回解析后的 JSON。

    解析失败抛 ``ValueError``。
    """

    raw = chat(
        messages,
        response_format="json",
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    cleaned = _strip_code_fence(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM 返回的 JSON 无法解析: {exc}; raw={raw[:300]!r}"
        ) from exc
