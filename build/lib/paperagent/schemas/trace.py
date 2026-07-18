from __future__ import annotations

from datetime import datetime
from typing import Literal

from paperagent.schemas.base import FrozenModel
from paperagent.schemas.common import TokenUsage


class TraceEvent(FrozenModel):
    schema_version: Literal["0.1"] = "0.1"
    event_id: str
    run_id: str
    span_id: str
    parent_span_id: str | None = None
    event_type: str
    node: str
    timestamp: datetime
    status: Literal["started", "completed", "failed", "decided"]
    input_hash: str | None = None
    output_hash: str | None = None
    prompt_version: str | None = None
    fixture_key: str | None = None
    model_name: str | None = None
    token_usage: TokenUsage | None = None
    duration_ms: int | None = None
    route: str | None = None
    error_code: str | None = None
