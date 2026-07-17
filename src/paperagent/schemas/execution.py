from __future__ import annotations

from typing import Literal

from pydantic import Field

from paperagent.schemas.base import FrozenModel
from paperagent.schemas.common import HumanAction, NodeErrorRecord


class ExecutionMeta(FrozenModel):
    current_node: str | None = None
    status: Literal["running", "waiting_human", "completed", "blocked", "failed"] = "running"
    llm_call_count: int = Field(default=0, ge=0)
    repair_count: int = Field(default=0, ge=0)
    repair_target: Literal["retrieval", "method"] | None = None
    last_error: NodeErrorRecord | None = None
    human_action_required: HumanAction | None = None
