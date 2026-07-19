from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from paperagent.schemas.base import FrozenModel


class RunBudgets(FrozenModel):
    max_llm_calls: int = Field(default=6, ge=1, le=20)
    max_retrieval_rounds: int = Field(default=2, ge=1, le=5)
    max_method_repairs: int = Field(default=1, ge=0, le=3)
    max_queries_per_round: int = Field(default=5, ge=1, le=20)
    max_evidence_items: int = Field(default=30, ge=1, le=200)


class RunContext(FrozenModel):
    schema_version: Literal["0.1"] = "0.1"
    engine_version: Literal["v0.1"] = "v0.1"
    run_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    created_at: datetime
    model_profile: str = Field(min_length=1)
    network_policy: Literal["offline", "allow_search"]
    budgets: RunBudgets


class TokenUsage(FrozenModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class NodeErrorRecord(FrozenModel):
    code: str
    message: str
    node: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ToolErrorRecord(FrozenModel):
    code: str
    message: str
    provider: str
    query_id: str | None = None
    retryable: bool = False
    attempt: int = Field(default=1, ge=1)


class HumanAction(FrozenModel):
    action_id: str
    question: str
    source: Literal["planning", "quality"]


class Message(FrozenModel):
    role: Literal["system", "user", "assistant"]
    content: str
