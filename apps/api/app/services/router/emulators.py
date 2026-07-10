"""Re6.5 Robustness Lab — Provider Emulator configuration.

Defines 12 provider response shapes for emulated testing.
Each emulator config maps to a specific failure mode or response pattern.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EmulatorConfig(BaseModel):
    """Provider emulator configuration for robustness testing."""
    emulator_id: str = ""
    label: str = ""
    response_shape: Literal[
        "openai-json", "reasoning-json", "markdown-json",
        "malformed-once", "malformed-always",
        "auth-429-5xx", "models-unsupported",
        "anthropic-like", "context-too-large",
        "semantic-fail", "all-fallback-fail",
        "weak-instruction", "streaming-chunked",
    ] = "openai-json"
    status_code: int = 200
    response_delay_ms: int = 0
    response_template: dict | str = Field(default_factory=dict)
    rate_limit_retry_after: int = 0
    inject_semantic_error: str = ""
    trigger_condition: str = ""  # e.g. "every_request", "on_repair"
    description: str = ""


# Core 4 emulators (80% coverage of failure modes)
CORE_EMULATORS: list[EmulatorConfig] = [
    EmulatorConfig(
        emulator_id="em-openai-json",
        label="OpenAI Compatible — Valid JSON",
        response_shape="openai-json",
        status_code=200,
        response_template={"verdict": "accept", "score": 8, "reason": "valid"},
        description="Baseline: valid JSON response, no errors",
    ),
    EmulatorConfig(
        emulator_id="em-malformed-once",
        label="Malformed JSON — Once (repairable)",
        response_shape="malformed-once",
        status_code=200,
        response_template="This is not JSON at all — raw prose output",
        description="First attempt returns non-JSON; repair should fix it",
    ),
    EmulatorConfig(
        emulator_id="em-auth-429",
        label="Auth Error + Rate Limit",
        response_shape="auth-429-5xx",
        status_code=429,
        rate_limit_retry_after=5,
        description="Simulates rate limiting; fallback should kick in",
    ),
    EmulatorConfig(
        emulator_id="em-streaming",
        label="Streaming Chunked Response",
        response_shape="streaming-chunked",
        status_code=200,
        response_template={"verdict": "accept", "score": 7},
        description="Response arrives in multiple SSE chunks",
    ),
]

# Extended emulators (full 12)
EXTENDED_EMULATORS: list[EmulatorConfig] = [
    EmulatorConfig(
        emulator_id="em-reasoning-json",
        label="Reasoning Model — JSON in reasoning field",
        response_shape="reasoning-json",
        status_code=200,
        response_template={"reasoning": "thinking...", "content": '{"verdict": "accept"}'},
        description="Reasoning model that outputs JSON in reasoning field",
    ),
    EmulatorConfig(
        emulator_id="em-markdown-json",
        label="Markdown-fenced JSON",
        response_shape="markdown-json",
        status_code=200,
        response_template="```json\n{\"verdict\": \"accept\"}\n```",
        description="JSON wrapped in markdown fenced block",
    ),
    EmulatorConfig(
        emulator_id="em-malformed-always",
        label="Always Malformed",
        response_shape="malformed-always",
        status_code=200,
        response_template="I cannot provide a structured response",
        description="Never returns valid JSON; forced heuristic fallback",
    ),
    EmulatorConfig(
        emulator_id="em-models-unsupported",
        label="Models Endpoint Unsupported",
        response_shape="models-unsupported",
        status_code=404,
        description="Discovery unsupported; manual model entry required",
    ),
    EmulatorConfig(
        emulator_id="em-anthropic-like",
        label="Anthropic-like Response",
        response_shape="anthropic-like",
        status_code=200,
        response_template={"content": [{"type": "text", "text": '{"verdict": "accept"}'}]},
        description="Anthropic message format with content blocks",
    ),
    EmulatorConfig(
        emulator_id="em-context-too-large",
        label="Context Window Exceeded",
        response_shape="context-too-large",
        status_code=400,
        response_template={"error": "context_length_exceeded"},
        description="Prompt too long; should trigger truncation",
    ),
    EmulatorConfig(
        emulator_id="em-semantic-fail",
        label="Semantic Validation Failure",
        response_shape="semantic-fail",
        status_code=200,
        response_template={"verdict": "bogus_value"},
        inject_semantic_error="invalid_verdict",
        description="Valid JSON but fails semantic check",
    ),
    EmulatorConfig(
        emulator_id="em-all-fallback-fail",
        label="All Providers Unavailable",
        response_shape="all-fallback-fail",
        status_code=503,
        description="Every provider returns error; typed_failure expected",
    ),
]

ALL_EMULATORS = CORE_EMULATORS + EXTENDED_EMULATORS


# Test manifest schema
class RunManifest(BaseModel):
    """Metadata for a robustness evaluation run."""
    run_id: str = ""
    test_level: Literal["L0", "L1", "L2", "L3", "L4"] = "L2"
    started_at: str = ""
    completed_at: str = ""
    environment: dict = Field(default_factory=dict)
    config_versions: dict = Field(default_factory=dict)
    duration_seconds: float = 0.0
    conclusion: str = ""
    total_cases: int = 0
    passed: int = 0
    failed: int = 0
    degraded: int = 0
