from __future__ import annotations

from typing import Any, Literal

from paperagent.runtime import RuntimeServices
from paperagent.schemas import TokenUsage, TraceEvent
from paperagent.state import PaperAgentState
from paperagent.telemetry.hashing import hash_payload

TraceStatus = Literal["started", "completed", "failed", "decided"]


def make_event(
    services: RuntimeServices,
    state: PaperAgentState,
    *,
    node: str,
    event_type: str,
    status: TraceStatus,
    input_payload: Any | None = None,
    output_payload: Any | None = None,
    prompt_version: str | None = None,
    fixture_key: str | None = None,
    model_name: str | None = None,
    token_usage: TokenUsage | None = None,
    duration_ms: int | None = None,
    route: str | None = None,
    error_code: str | None = None,
    span_id: str | None = None,
) -> TraceEvent:
    run = state.get("run")
    return TraceEvent(
        event_id=services.ids.new_id("event"),
        run_id=run.run_id if run else "uninitialized",
        span_id=span_id or services.ids.new_id("span"),
        event_type=event_type,
        node=node,
        timestamp=services.clock.now(),
        status=status,
        input_hash=hash_payload(input_payload) if input_payload is not None else None,
        output_hash=hash_payload(output_payload) if output_payload is not None else None,
        prompt_version=prompt_version,
        fixture_key=fixture_key,
        model_name=model_name,
        token_usage=token_usage,
        duration_ms=duration_ms,
        route=route,
        error_code=error_code,
    )
