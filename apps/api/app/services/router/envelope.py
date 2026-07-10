"""ResponseEnvelope + TokenUsage for Re6.2 Router Unification.

Every provider adapter (OpenAI-compatible, Anthropic-like) normalises its
response into this unified envelope BEFORE returning to business nodes.

Business nodes ONLY read ResponseEnvelope — never raw provider responses.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Normalised token count."""
    input_tokens: int = 0
    output_tokens: int = 0


class ResponseEnvelope(BaseModel):
    """Unified provider response.

    All provider adapters MUST normalise their raw response into this shape.
    Business nodes read content (and optionally reasoning) — never the raw
    provider-specific JSON.
    """
    provider_id: str = ""               # Which provider served this response
    model_id: str = ""                  # Which model_id was used
    request_id: str = ""                # Unique per-call ID for traceability
    content: str = ""                   # Primary text output
    reasoning: str | None = None        # Extracted reasoning/thinking (if any)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    finish_reason: str = "stop"
    usage: TokenUsage = Field(default_factory=TokenUsage)
    raw_shape: Literal["openai_chat", "anthropic_message", "custom"] = "custom"

    @classmethod
    def from_openai(cls, raw: dict[str, Any], provider_id: str = "") -> "ResponseEnvelope":
        """Construct from a normalised OpenAI-compatible response."""
        choices = raw.get("choices") or []
        content = ""
        finish_reason = "stop"
        tool_calls = []
        if choices:
            first = choices[0]
            msg = first.get("message") or {}
            content = msg.get("content") or ""
            finish_reason = first.get("finish_reason", "stop")
            tool_calls = msg.get("tool_calls") or []

        usage_raw = raw.get("usage") or {}
        usage = TokenUsage(
            input_tokens=usage_raw.get("prompt_tokens", 0),
            output_tokens=usage_raw.get("completion_tokens", 0),
        )

        return cls(
            provider_id=provider_id,
            model_id=raw.get("model", ""),
            request_id=raw.get("id", ""),
            content=content,
            reasoning=raw.get("reasoning"),
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            raw_shape="openai_chat",
        )

    @classmethod
    def from_anthropic(cls, raw: dict[str, Any], provider_id: str = "") -> "ResponseEnvelope":
        """Construct from a normalised Anthropic message response."""
        content = ""
        reasoning = raw.get("reasoning")
        tool_calls = raw.get("tool_calls") or []

        choices = raw.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            content = msg.get("content") or ""

        usage_raw = raw.get("usage") or {}
        usage = TokenUsage(
            input_tokens=usage_raw.get("prompt_tokens", 0),
            output_tokens=usage_raw.get("completion_tokens", 0),
        )

        return cls(
            provider_id=provider_id,
            model_id=raw.get("model", ""),
            content=content,
            reasoning=reasoning,
            tool_calls=tool_calls,
            finish_reason=choices[0].get("finish_reason", "end_turn") if choices else "end_turn",
            usage=usage,
            raw_shape="anthropic_message",
        )

    def has_valid_json_content(self) -> bool:
        """Check if content is non-empty and looks like JSON."""
        if not self.content.strip():
            return False
        import json
        try:
            json.loads(self.content.strip())
            return True
        except (json.JSONDecodeError, ValueError):
            # Try extracting from markdown fenced block
            import re
            m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", self.content, re.DOTALL)
            if m:
                try:
                    json.loads(m.group(1))
                    return True
                except (json.JSONDecodeError, ValueError):
                    pass
            return False

    def extract_json(self) -> Any | None:
        """Extract JSON from content (tries direct parse, then fenced block)."""
        import json
        import re
        content = self.content.strip()
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            pass
        # Try fenced block
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except (json.JSONDecodeError, ValueError):
                pass
        return None
