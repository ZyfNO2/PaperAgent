from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_version: str = "v0.1"
    scenario: str = "happy_path"
    max_llm_retries: int = Field(default=1, ge=0, le=3)
    search_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    recursion_limit: int = Field(default=32, ge=8, le=128)
